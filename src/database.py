"""
Camada de persistencia: conecta ao Postgres do Supabase (sql/schema_postgres.sql)
e carrega objetos OrdemDeCompra validados (schema.py) nas tabelas correspondentes.

Ate a Fase 2 da migracao para backend real, este modulo usava SQLite local
(sql/schema.sql). Agora conecta via psycopg a um projeto Supabase - dois
projetos SEPARADOS para demo e producao (nunca o mesmo projeto, ver
docs/arquitetura_webapp.md), selecionados por DATABASE_URL_DEMO /
DATABASE_URL_PRODUCAO no .env.

Diferente do SQLite, o schema Postgres NAO e aplicado automaticamente por
este modulo: como CREATE POLICY (RLS) nao e idempotente, o schema e aplicado
uma unica vez, manualmente, no SQL Editor do Supabase
(sql/schema_postgres.sql). inicializar_schema() aqui so confirma que as
tabelas esperadas existem, com um erro claro se nao existirem.
"""

from __future__ import annotations

import logging
import os

import psycopg
from psycopg.rows import dict_row

from schema import OrdemDeCompra
from validadores import cnpj_valido

logger = logging.getLogger(__name__)

# Dois projetos Supabase separados para nao misturar dado real com dado de
# demonstracao (auth.users e RLS ficariam misturados num projeto so). demo e
# o projeto criado na Fase 1; producao ainda nao existe ate a TI aprovar o
# App Registration/infra da empresa - ver docs/arquitetura_webapp.md.
#
# Lidas como funcao (nao uma constante de modulo) de proposito: pipeline.py e
# report_generator.py chamam load_dotenv() dentro de main()/no topo do
# arquivo, mas so DEPOIS que "import database" ja rodou o corpo deste modulo.
# Se DSN_DEMO/DSN_PADRAO fossem constantes fixadas na importacao, elas nunca
# veriam o valor real do .env (mesmo bug ja corrigido antes em
# llm_extractor.MODELO_PADRAO/modelo_configurado()).
def dsn_demo() -> str:
    return os.environ.get("DATABASE_URL_DEMO", "")


def dsn_producao() -> str:
    return os.environ.get("DATABASE_URL_PRODUCAO", "")

LIMITE_CONFIANCA_BAIXA = float(os.environ.get("LIMITE_CONFIANCA_BAIXA", "0.7"))

# Tabelas que sql/schema_postgres.sql cria - conferido por inicializar_schema().
TABELAS_ESPERADAS = {
    "clientes",
    "fornecedores",
    "ordens_compra",
    "itens_oc",
    "dados_clinicos",
    "log_extracao",
    "perfis",
    "log_acesso",
}


def conectar(dsn: str) -> psycopg.Connection:
    """Abre uma conexao com o Postgres do Supabase. dsn e a string de conexao
    completa (DATABASE_URL_DEMO ou DATABASE_URL_PRODUCAO do .env) - use o
    connection pooler (session pooler), nao a conexao direta, que exige IPv6
    e costuma falhar em redes domesticas/corporativas comuns."""

    if not dsn:
        raise RuntimeError(
            "String de conexao Postgres vazia. Configure DATABASE_URL_DEMO "
            "(ou DATABASE_URL_PRODUCAO) no .env - ver docs/arquitetura_webapp.md."
        )
    # connect_timeout evita que uma conexao trave indefinidamente (ex: pool de
    # conexoes do Supabase temporariamente sem slot livre) - falha rapido com
    # um erro claro em vez de travar o pipeline/testes sem explicacao.
    return psycopg.connect(dsn, row_factory=dict_row, autocommit=False, connect_timeout=15)


def inicializar_schema(conn: psycopg.Connection) -> None:
    """Confirma que o schema Postgres ja foi aplicado no projeto Supabase.

    Diferente do antigo schema SQLite, este modulo NAO aplica o DDL
    automaticamente - CREATE POLICY (RLS) nao e idempotente, entao
    sql/schema_postgres.sql deve ser rodado manualmente, uma vez, no SQL
    Editor do Supabase. Isso so verifica e avisa com um erro claro se alguma
    tabela esperada estiver faltando."""

    cur = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    )
    existentes = {row["table_name"] for row in cur.fetchall()}
    faltando = TABELAS_ESPERADAS - existentes
    if faltando:
        raise RuntimeError(
            f"Tabelas ausentes no banco Postgres: {', '.join(sorted(faltando))}. "
            "Rode sql/schema_postgres.sql no SQL Editor do projeto Supabase antes "
            "de usar o pipeline."
        )


def _obter_ou_criar_cliente(conn: psycopg.Connection, oc: OrdemDeCompra) -> int:
    cliente = oc.cliente
    cur = conn.execute(
        "SELECT id FROM clientes WHERE nome = %s AND COALESCE(cnpj, '') = COALESCE(%s, '')",
        (cliente.nome, cliente.cnpj),
    )
    linha = cur.fetchone()
    if linha:
        return linha["id"]

    cur = conn.execute(
        "INSERT INTO clientes (nome, cnpj, cidade, uf) VALUES (%s, %s, %s, %s) RETURNING id",
        (cliente.nome, cliente.cnpj, cliente.cidade, cliente.uf),
    )
    return cur.fetchone()["id"]


def _obter_ou_criar_fornecedor(conn: psycopg.Connection, oc: OrdemDeCompra) -> int:
    fornecedor = oc.fornecedor
    cur = conn.execute(
        "SELECT id FROM fornecedores WHERE nome = %s AND COALESCE(cnpj, '') = COALESCE(%s, '')",
        (fornecedor.nome, fornecedor.cnpj),
    )
    linha = cur.fetchone()
    if linha:
        return linha["id"]

    cur = conn.execute(
        "INSERT INTO fornecedores (nome, cnpj) VALUES (%s, %s) RETURNING id",
        (fornecedor.nome, fornecedor.cnpj),
    )
    return cur.fetchone()["id"]


def _marcar_possiveis_duplicatas(
    conn: psycopg.Connection, ordem_compra_id: int, numero_oc: str, cliente_id: int
) -> None:
    """Sinaliza (nunca exclui) OCs com o mesmo numero e cliente salvas em
    arquivos diferentes - provavel duplicidade (ex: o mesmo PDF salvo duas
    vezes pela automacao com nomes de arquivo diferentes).

    A decisao de excluir ou nao uma duplicata fica sempre com um humano,
    revisando a Central de alertas do painel: este pipeline nunca apaga uma
    ordem_compra sozinho.
    """

    outras = conn.execute(
        "SELECT id FROM ordens_compra WHERE numero_oc = %s AND cliente_id = %s AND id != %s",
        (numero_oc, cliente_id, ordem_compra_id),
    ).fetchall()

    if not outras:
        return

    ids_grupo = [ordem_compra_id] + [row["id"] for row in outras]
    placeholders = ",".join(["%s"] * len(ids_grupo))
    conn.execute(
        f"UPDATE ordens_compra SET status_extracao = 'possivel_duplicata' WHERE id IN ({placeholders})",
        ids_grupo,
    )
    logger.warning(
        "Possivel duplicidade: OC %s (cliente_id=%s) tem %d registro(s) em arquivos diferentes",
        numero_oc,
        cliente_id,
        len(ids_grupo),
    )


TOLERANCIA_VALOR = 0.02  # diferenca em reais tolerada antes de sinalizar divergencia


def _valor_diverge(oc: OrdemDeCompra) -> bool:
    """Confere se a soma dos itens (com ou sem frete) bate com o valor_total
    declarado no documento, dentro de uma tolerancia. Nao corrige nada,
    apenas informa se vale a pena revisar manualmente."""

    if oc.valor_total is None or not oc.itens:
        return False

    soma_itens = sum(item.valor_total for item in oc.itens)
    frete = oc.valor_frete or 0.0

    bate_sem_frete = abs(soma_itens - oc.valor_total) <= TOLERANCIA_VALOR
    bate_com_frete = abs(soma_itens + frete - oc.valor_total) <= TOLERANCIA_VALOR

    return not (bate_sem_frete or bate_com_frete)


def _marcar_divergencia_valor(conn: psycopg.Connection, ordem_compra_id: int, oc: OrdemDeCompra) -> None:
    diverge = _valor_diverge(oc)
    conn.execute(
        "UPDATE ordens_compra SET alerta_valor_divergente = %s WHERE id = %s",
        (diverge, ordem_compra_id),
    )
    if diverge:
        soma_itens = sum(item.valor_total for item in oc.itens)
        logger.warning(
            "Divergencia de valor na OC %s: soma dos itens = %.2f, valor_total declarado = %.2f",
            oc.numero_oc,
            soma_itens,
            oc.valor_total,
        )


def _marcar_baixa_confianca(conn: psycopg.Connection, ordem_compra_id: int, oc: OrdemDeCompra) -> None:
    """Sinaliza quando o proprio modelo relatou confianca baixa na extracao
    (ver o criterio explicito em PROMPT_SISTEMA, em llm_extractor.py)."""

    baixa = oc.confianca_extracao is not None and oc.confianca_extracao < LIMITE_CONFIANCA_BAIXA
    conn.execute(
        "UPDATE ordens_compra SET alerta_baixa_confianca = %s WHERE id = %s",
        (baixa, ordem_compra_id),
    )
    if baixa:
        logger.warning(
            "Confianca baixa na OC %s: %.2f (limite: %.2f)",
            oc.numero_oc,
            oc.confianca_extracao,
            LIMITE_CONFIANCA_BAIXA,
        )


def _marcar_cnpj_invalido(conn: psycopg.Connection, ordem_compra_id: int, oc: OrdemDeCompra) -> None:
    """Confere o digito verificador do CNPJ do cliente e do fornecedor
    (validadores.cnpj_valido - verificacao deterministica, independente do
    LLM). CNPJ ausente (None) nao e sinalizado, so CNPJ presente e invalido."""

    invalido = not cnpj_valido(oc.cliente.cnpj) or not cnpj_valido(oc.fornecedor.cnpj)
    conn.execute(
        "UPDATE ordens_compra SET alerta_cnpj_invalido = %s WHERE id = %s",
        (invalido, ordem_compra_id),
    )
    if invalido:
        logger.warning(
            "CNPJ invalido detectado na OC %s (cliente=%s, fornecedor=%s)",
            oc.numero_oc,
            oc.cliente.cnpj,
            oc.fornecedor.cnpj,
        )


def salvar_ordem_de_compra(conn: psycopg.Connection, oc: OrdemDeCompra) -> int:
    """Insere uma OrdemDeCompra validada no banco (idempotente por numero_oc + arquivo_origem)."""

    cliente_id = _obter_ou_criar_cliente(conn, oc)
    fornecedor_id = _obter_ou_criar_fornecedor(conn, oc)

    cur = conn.execute(
        """
        INSERT INTO ordens_compra (
            numero_oc, data_emissao, cliente_id, fornecedor_id,
            condicao_pagamento_dias, valor_frete, valor_total, tipo_faturamento,
            layout_origem, arquivo_origem, confianca_extracao
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (numero_oc, arquivo_origem) DO UPDATE SET
            data_emissao = EXCLUDED.data_emissao,
            cliente_id = EXCLUDED.cliente_id,
            fornecedor_id = EXCLUDED.fornecedor_id,
            condicao_pagamento_dias = EXCLUDED.condicao_pagamento_dias,
            valor_frete = EXCLUDED.valor_frete,
            valor_total = EXCLUDED.valor_total,
            tipo_faturamento = EXCLUDED.tipo_faturamento,
            layout_origem = EXCLUDED.layout_origem,
            confianca_extracao = EXCLUDED.confianca_extracao
        RETURNING id
        """,
        (
            oc.numero_oc,
            oc.data_emissao.isoformat() if oc.data_emissao else None,
            cliente_id,
            fornecedor_id,
            oc.condicao_pagamento_dias,
            oc.valor_frete,
            oc.valor_total,
            oc.tipo_faturamento,
            oc.layout_origem.value,
            oc.arquivo_origem,
            oc.confianca_extracao,
        ),
    )
    ordem_compra_id = cur.fetchone()["id"]

    conn.execute("DELETE FROM itens_oc WHERE ordem_compra_id = %s", (ordem_compra_id,))
    for item in oc.itens:
        conn.execute(
            """
            INSERT INTO itens_oc (
                ordem_compra_id, codigo_produto, descricao, quantidade,
                unidade, valor_unitario, valor_total, lote, referencia
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                ordem_compra_id,
                item.codigo_produto,
                item.descricao,
                item.quantidade,
                item.unidade,
                item.valor_unitario,
                item.valor_total,
                item.lote,
                item.referencia,
            ),
        )

    if oc.dados_clinicos:
        dc = oc.dados_clinicos
        conn.execute(
            """
            INSERT INTO dados_clinicos (
                ordem_compra_id, paciente, convenio, carteirinha,
                cirurgiao, data_realizacao, aviso_cirurgia, setor
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ordem_compra_id) DO UPDATE SET
                paciente = EXCLUDED.paciente,
                convenio = EXCLUDED.convenio,
                carteirinha = EXCLUDED.carteirinha,
                cirurgiao = EXCLUDED.cirurgiao,
                data_realizacao = EXCLUDED.data_realizacao,
                aviso_cirurgia = EXCLUDED.aviso_cirurgia,
                setor = EXCLUDED.setor
            """,
            (
                ordem_compra_id,
                dc.paciente,
                dc.convenio,
                dc.carteirinha,
                dc.cirurgiao,
                dc.data_realizacao.isoformat() if dc.data_realizacao else None,
                dc.aviso_cirurgia,
                dc.setor,
            ),
        )

    _marcar_possiveis_duplicatas(conn, ordem_compra_id, oc.numero_oc, cliente_id)
    _marcar_divergencia_valor(conn, ordem_compra_id, oc)
    _marcar_baixa_confianca(conn, ordem_compra_id, oc)
    _marcar_cnpj_invalido(conn, ordem_compra_id, oc)

    conn.commit()
    return ordem_compra_id


def registrar_log_extracao(
    conn: psycopg.Connection,
    arquivo: str,
    status: str,
    confianca: float | None = None,
    erro: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO log_extracao (arquivo, status, confianca, erro) VALUES (%s, %s, %s, %s)",
        (arquivo, status, confianca, erro),
    )
    conn.commit()


def contar_falhas_arquivo(conn: psycopg.Connection, arquivo: str) -> int:
    """Conta quantas tentativas de extracao desse arquivo falharam ate agora
    (usado para decidir se um arquivo deve ir para a pasta de quarentena)."""

    linha = conn.execute(
        "SELECT COUNT(*) AS n FROM log_extracao WHERE arquivo = %s AND status LIKE %s",
        (arquivo, "erro%"),
    ).fetchone()
    return linha["n"]
