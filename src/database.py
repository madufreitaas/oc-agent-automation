"""
Camada de persistencia: cria o banco SQLite (sql/schema.sql) e carrega
objetos OrdemDeCompra validados (schema.py) nas tabelas correspondentes.
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from schema import OrdemDeCompra
from validadores import cnpj_valido

logger = logging.getLogger(__name__)

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
SCHEMA_SQL_PATH = RAIZ_PROJETO / "sql" / "schema.sql"

# Dois bancos separados para nao misturar dado real com dado de demonstracao:
# DB_PADRAO_PATH e o banco "de verdade" (modo producao), DB_DEMO_PATH e usado
# quando o pipeline roda em modo demo (PDFs sinteticos). pipeline.py e
# report_generator.py escolhem um ou outro automaticamente com base em --modo.
DB_PADRAO_PATH = RAIZ_PROJETO / "output" / "database" / "oc_agent.db"
DB_DEMO_PATH = RAIZ_PROJETO / "output" / "database" / "oc_agent_demo.db"

LIMITE_CONFIANCA_BAIXA = float(os.environ.get("LIMITE_CONFIANCA_BAIXA", "0.7"))


def conectar(db_path: str | Path = DB_PADRAO_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


# Colunas adicionadas em ordens_compra depois da criacao inicial do projeto.
# SQLite nao migra schema automaticamente: "CREATE TABLE IF NOT EXISTS" nao
# altera uma tabela ja existente. Sem isso, um banco criado por uma versao
# mais antiga do codigo (inclusive de producao, com dados reais) quebraria
# ao rodar contra o codigo novo. Cada entrada aqui e adicionada via ALTER
# TABLE somente se ainda nao existir, preservando os dados ja gravados.
COLUNAS_ADICIONAIS_ORDENS_COMPRA = {
    "tipo_faturamento": "TEXT",
    "status_extracao": "TEXT NOT NULL DEFAULT 'ok'",
    "alerta_valor_divergente": "INTEGER NOT NULL DEFAULT 0",
    "alerta_baixa_confianca": "INTEGER NOT NULL DEFAULT 0",
    "alerta_cnpj_invalido": "INTEGER NOT NULL DEFAULT 0",
}


def _migrar_colunas_ausentes(conn: sqlite3.Connection) -> None:
    colunas_existentes = {
        row["name"] for row in conn.execute("PRAGMA table_info(ordens_compra)").fetchall()
    }
    for coluna, definicao in COLUNAS_ADICIONAIS_ORDENS_COMPRA.items():
        if coluna not in colunas_existentes:
            conn.execute(f"ALTER TABLE ordens_compra ADD COLUMN {coluna} {definicao}")
            logger.info("Coluna '%s' adicionada a ordens_compra (migracao de schema)", coluna)


def inicializar_schema(conn: sqlite3.Connection) -> None:
    sql = SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)
    _migrar_colunas_ausentes(conn)
    conn.commit()


def _obter_ou_criar_cliente(conn: sqlite3.Connection, oc: OrdemDeCompra) -> int:
    cliente = oc.cliente
    cur = conn.execute(
        "SELECT id FROM clientes WHERE nome = ? AND IFNULL(cnpj, '') = IFNULL(?, '')",
        (cliente.nome, cliente.cnpj),
    )
    linha = cur.fetchone()
    if linha:
        return linha["id"]

    cur = conn.execute(
        "INSERT INTO clientes (nome, cnpj, cidade, uf) VALUES (?, ?, ?, ?)",
        (cliente.nome, cliente.cnpj, cliente.cidade, cliente.uf),
    )
    return cur.lastrowid


def _obter_ou_criar_fornecedor(conn: sqlite3.Connection, oc: OrdemDeCompra) -> int:
    fornecedor = oc.fornecedor
    cur = conn.execute(
        "SELECT id FROM fornecedores WHERE nome = ? AND IFNULL(cnpj, '') = IFNULL(?, '')",
        (fornecedor.nome, fornecedor.cnpj),
    )
    linha = cur.fetchone()
    if linha:
        return linha["id"]

    cur = conn.execute(
        "INSERT INTO fornecedores (nome, cnpj) VALUES (?, ?)",
        (fornecedor.nome, fornecedor.cnpj),
    )
    return cur.lastrowid


def _marcar_possiveis_duplicatas(conn: sqlite3.Connection, ordem_compra_id: int, numero_oc: str, cliente_id: int) -> None:
    """Sinaliza (nunca exclui) OCs com o mesmo numero e cliente salvas em
    arquivos diferentes - provavel duplicidade (ex: o mesmo PDF salvo duas
    vezes pela automacao com nomes de arquivo diferentes).

    A decisao de excluir ou nao uma duplicata fica sempre com um humano,
    revisando a secao "Possiveis duplicidades" do relatorio: este pipeline
    nunca apaga uma ordem_compra sozinho.
    """

    outras = conn.execute(
        "SELECT id FROM ordens_compra WHERE numero_oc = ? AND cliente_id = ? AND id != ?",
        (numero_oc, cliente_id, ordem_compra_id),
    ).fetchall()

    if not outras:
        return

    ids_grupo = [ordem_compra_id] + [row["id"] for row in outras]
    placeholders = ",".join("?" for _ in ids_grupo)
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


def _marcar_divergencia_valor(conn: sqlite3.Connection, ordem_compra_id: int, oc: OrdemDeCompra) -> None:
    diverge = _valor_diverge(oc)
    conn.execute(
        "UPDATE ordens_compra SET alerta_valor_divergente = ? WHERE id = ?",
        (1 if diverge else 0, ordem_compra_id),
    )
    if diverge:
        soma_itens = sum(item.valor_total for item in oc.itens)
        logger.warning(
            "Divergencia de valor na OC %s: soma dos itens = %.2f, valor_total declarado = %.2f",
            oc.numero_oc,
            soma_itens,
            oc.valor_total,
        )


def _marcar_baixa_confianca(conn: sqlite3.Connection, ordem_compra_id: int, oc: OrdemDeCompra) -> None:
    """Sinaliza quando o proprio modelo relatou confianca baixa na extracao
    (ver o criterio explicito em PROMPT_SISTEMA, em llm_extractor.py)."""

    baixa = oc.confianca_extracao is not None and oc.confianca_extracao < LIMITE_CONFIANCA_BAIXA
    conn.execute(
        "UPDATE ordens_compra SET alerta_baixa_confianca = ? WHERE id = ?",
        (1 if baixa else 0, ordem_compra_id),
    )
    if baixa:
        logger.warning(
            "Confianca baixa na OC %s: %.2f (limite: %.2f)",
            oc.numero_oc,
            oc.confianca_extracao,
            LIMITE_CONFIANCA_BAIXA,
        )


def _marcar_cnpj_invalido(conn: sqlite3.Connection, ordem_compra_id: int, oc: OrdemDeCompra) -> None:
    """Confere o digito verificador do CNPJ do cliente e do fornecedor
    (validadores.cnpj_valido - verificacao deterministica, independente do
    LLM). CNPJ ausente (None) nao e sinalizado, so CNPJ presente e invalido."""

    invalido = not cnpj_valido(oc.cliente.cnpj) or not cnpj_valido(oc.fornecedor.cnpj)
    conn.execute(
        "UPDATE ordens_compra SET alerta_cnpj_invalido = ? WHERE id = ?",
        (1 if invalido else 0, ordem_compra_id),
    )
    if invalido:
        logger.warning(
            "CNPJ invalido detectado na OC %s (cliente=%s, fornecedor=%s)",
            oc.numero_oc,
            oc.cliente.cnpj,
            oc.fornecedor.cnpj,
        )


def salvar_ordem_de_compra(conn: sqlite3.Connection, oc: OrdemDeCompra) -> int:
    """Insere uma OrdemDeCompra validada no banco (idempotente por numero_oc + arquivo_origem)."""

    cliente_id = _obter_ou_criar_cliente(conn, oc)
    fornecedor_id = _obter_ou_criar_fornecedor(conn, oc)

    cur = conn.execute(
        """
        INSERT INTO ordens_compra (
            numero_oc, data_emissao, cliente_id, fornecedor_id,
            condicao_pagamento_dias, valor_frete, valor_total, tipo_faturamento,
            layout_origem, arquivo_origem, confianca_extracao
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (numero_oc, arquivo_origem) DO UPDATE SET
            data_emissao = excluded.data_emissao,
            cliente_id = excluded.cliente_id,
            fornecedor_id = excluded.fornecedor_id,
            condicao_pagamento_dias = excluded.condicao_pagamento_dias,
            valor_frete = excluded.valor_frete,
            valor_total = excluded.valor_total,
            tipo_faturamento = excluded.tipo_faturamento,
            layout_origem = excluded.layout_origem,
            confianca_extracao = excluded.confianca_extracao
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

    if cur.lastrowid:
        ordem_compra_id = cur.lastrowid
    else:
        ordem_compra_id = conn.execute(
            "SELECT id FROM ordens_compra WHERE numero_oc = ? AND arquivo_origem = ?",
            (oc.numero_oc, oc.arquivo_origem),
        ).fetchone()["id"]

    conn.execute("DELETE FROM itens_oc WHERE ordem_compra_id = ?", (ordem_compra_id,))
    for item in oc.itens:
        conn.execute(
            """
            INSERT INTO itens_oc (
                ordem_compra_id, codigo_produto, descricao, quantidade,
                unidade, valor_unitario, valor_total, lote, referencia
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (ordem_compra_id) DO UPDATE SET
                paciente = excluded.paciente,
                convenio = excluded.convenio,
                carteirinha = excluded.carteirinha,
                cirurgiao = excluded.cirurgiao,
                data_realizacao = excluded.data_realizacao,
                aviso_cirurgia = excluded.aviso_cirurgia,
                setor = excluded.setor
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
    conn: sqlite3.Connection,
    arquivo: str,
    status: str,
    confianca: float | None = None,
    erro: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO log_extracao (arquivo, status, confianca, erro) VALUES (?, ?, ?, ?)",
        (arquivo, status, confianca, erro),
    )
    conn.commit()


def contar_falhas_arquivo(conn: sqlite3.Connection, arquivo: str) -> int:
    """Conta quantas tentativas de extracao desse arquivo falharam ate agora
    (usado para decidir se um arquivo deve ir para a pasta de quarentena)."""

    linha = conn.execute(
        "SELECT COUNT(*) AS n FROM log_extracao WHERE arquivo = ? AND status LIKE 'erro%'",
        (arquivo,),
    ).fetchone()
    return linha["n"]


def fazer_backup(db_path: str | Path, manter_ultimos: int = 20) -> Path | None:
    """Copia o banco para uma subpasta 'backups/' com timestamp antes de uma
    execucao do pipeline, mantendo apenas os N backups mais recentes.

    Nao faz nada (retorna None) se o banco ainda nao existir - nao ha o que
    fazer backup na primeira execucao."""

    db_path = Path(db_path)
    if not db_path.exists():
        return None

    pasta_backup = db_path.parent / "backups"
    pasta_backup.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = pasta_backup / f"{db_path.stem}_{timestamp}{db_path.suffix}"
    shutil.copy2(db_path, destino)

    backups = sorted(pasta_backup.glob(f"{db_path.stem}_*{db_path.suffix}"))
    for backup_antigo in backups[:-manter_ultimos]:
        backup_antigo.unlink()

    logger.info("Backup do banco criado em %s", destino)
    return destino
