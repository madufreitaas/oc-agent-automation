import pytest

import database
from schema import Cliente, DadosClinicos, Fornecedor, ItemOC, OrdemDeCompra

# Prefixo reservado para arquivo_origem/arquivo criados por estes testes, para
# a fixture "conn" conseguir limpar so o que e dado de teste, nunca dado real
# ou de demonstracao ja gravado no projeto Supabase demo.
PREFIXO_TESTE = "teste_database_"


@pytest.fixture
def conn():
    """Conecta ao projeto Supabase demo (DATABASE_URL_DEMO no .env). Pula o
    teste (nao falha) se a variavel nao estiver configurada - estes testes
    exigem o projeto Supabase real, diferente dos testes mockados de
    llm_extractor.py. Limpa qualquer dado de teste (prefixo PREFIXO_TESTE) ao
    final, para nao acumular lixo no banco compartilhado."""

    dsn = database.dsn_demo()
    if not dsn:
        pytest.skip("DATABASE_URL_DEMO nao configurada - ver docs/arquitetura_webapp.md")

    conexao = database.conectar(dsn)
    database.inicializar_schema(conexao)
    yield conexao

    conexao.rollback()  # descarta qualquer transacao pendente antes de limpar
    conexao.execute(
        "DELETE FROM ordens_compra WHERE arquivo_origem LIKE %s", (f"{PREFIXO_TESTE}%",)
    )
    conexao.execute("DELETE FROM log_extracao WHERE arquivo LIKE %s", (f"{PREFIXO_TESTE}%",))
    conexao.execute("DELETE FROM clientes WHERE id NOT IN (SELECT DISTINCT cliente_id FROM ordens_compra)")
    conexao.execute(
        "DELETE FROM fornecedores WHERE id NOT IN (SELECT DISTINCT fornecedor_id FROM ordens_compra)"
    )
    conexao.commit()
    conexao.close()


def _arquivo(nome: str) -> str:
    return f"{PREFIXO_TESTE}{nome}"


def _oc_exemplo(numero_oc: str = "12345", arquivo: str = "exemplo.pdf") -> OrdemDeCompra:
    return OrdemDeCompra(
        numero_oc=numero_oc,
        data_emissao="2026-05-12",
        cliente=Cliente(nome="Hospital Exemplo", cnpj="11.111.111/0001-11", cidade="Recife", uf="PE"),
        fornecedor=Fornecedor(nome="Mederi Distribuicao", cnpj="29.329.985/0006-90"),
        itens=[
            ItemOC(
                codigo_produto="000123",
                descricao="Stent coronario 3.0x18mm",
                quantidade=1,
                unidade="UN",
                valor_unitario=1450.0,
                valor_total=1450.0,
            )
        ],
        condicao_pagamento_dias=30,
        valor_frete=0.0,
        valor_total=1450.0,
        tipo_faturamento="FATURAR E REPOR",
        dados_clinicos=DadosClinicos(paciente="Paciente Teste", convenio="Unimed"),
        arquivo_origem=_arquivo(arquivo),
        confianca_extracao=0.9,
    )


def test_inicializar_schema_confirma_tabelas_existentes(conn):
    # Nao deve levantar excecao - todas as tabelas de sql/schema_postgres.sql
    # ja foram criadas manualmente no projeto Supabase (ver Fase 1).
    database.inicializar_schema(conn)


def test_inicializar_schema_falha_com_mensagem_clara_se_tabela_faltar(monkeypatch, conn):
    monkeypatch.setattr(database, "TABELAS_ESPERADAS", database.TABELAS_ESPERADAS | {"tabela_inexistente"})
    with pytest.raises(RuntimeError, match="tabela_inexistente"):
        database.inicializar_schema(conn)


def test_salvar_ordem_de_compra_persiste_itens_e_dados_clinicos(conn):
    oc_id = database.salvar_ordem_de_compra(conn, _oc_exemplo())

    ordem = conn.execute("SELECT * FROM ordens_compra WHERE id = %s", (oc_id,)).fetchone()
    assert ordem["numero_oc"] == "12345"
    assert ordem["valor_total"] == 1450.0
    assert ordem["tipo_faturamento"] == "FATURAR E REPOR"

    itens = conn.execute("SELECT * FROM itens_oc WHERE ordem_compra_id = %s", (oc_id,)).fetchall()
    assert len(itens) == 1
    assert itens[0]["descricao"] == "Stent coronario 3.0x18mm"

    clinico = conn.execute(
        "SELECT * FROM dados_clinicos WHERE ordem_compra_id = %s", (oc_id,)
    ).fetchone()
    assert clinico["paciente"] == "Paciente Teste"


def test_salvar_ordem_de_compra_e_idempotente(conn):
    oc = _oc_exemplo()
    id_1 = database.salvar_ordem_de_compra(conn, oc)
    id_2 = database.salvar_ordem_de_compra(conn, oc)

    assert id_1 == id_2
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM ordens_compra WHERE arquivo_origem = %s", (oc.arquivo_origem,)
    ).fetchone()["n"]
    assert total == 1


def test_registrar_log_extracao(conn):
    database.registrar_log_extracao(conn, _arquivo("arquivo.pdf"), status="ok", confianca=0.87)
    logs = conn.execute(
        "SELECT * FROM log_extracao WHERE arquivo = %s", (_arquivo("arquivo.pdf"),)
    ).fetchall()
    assert len(logs) == 1
    assert logs[0]["status"] == "ok"


def test_salvar_ordem_de_compra_status_ok_por_padrao(conn):
    oc_id = database.salvar_ordem_de_compra(conn, _oc_exemplo())

    ordem = conn.execute("SELECT status_extracao FROM ordens_compra WHERE id = %s", (oc_id,)).fetchone()
    assert ordem["status_extracao"] == "ok"


def test_salvar_ordem_de_compra_mesmo_numero_arquivos_diferentes_marca_duplicata(conn):
    id_1 = database.salvar_ordem_de_compra(conn, _oc_exemplo(arquivo="arquivo_a.pdf"))
    id_2 = database.salvar_ordem_de_compra(conn, _oc_exemplo(arquivo="arquivo_b.pdf"))

    assert id_1 != id_2
    status = {
        row["id"]: row["status_extracao"]
        for row in conn.execute(
            "SELECT id, status_extracao FROM ordens_compra WHERE id IN (%s, %s)", (id_1, id_2)
        ).fetchall()
    }
    assert status[id_1] == "possivel_duplicata"
    assert status[id_2] == "possivel_duplicata"


def test_salvar_ordem_de_compra_numeros_diferentes_nao_marca_duplicata(conn):
    id_1 = database.salvar_ordem_de_compra(conn, _oc_exemplo(numero_oc="111", arquivo="a.pdf"))
    id_2 = database.salvar_ordem_de_compra(conn, _oc_exemplo(numero_oc="222", arquivo="b.pdf"))

    status = [
        row["status_extracao"]
        for row in conn.execute(
            "SELECT status_extracao FROM ordens_compra WHERE id IN (%s, %s)", (id_1, id_2)
        ).fetchall()
    ]
    assert status == ["ok", "ok"]


def test_salvar_ordem_de_compra_sem_divergencia_nao_marca_alerta_valor(conn):
    oc_id = database.salvar_ordem_de_compra(conn, _oc_exemplo())  # itens somam exatamente o valor_total

    ordem = conn.execute("SELECT alerta_valor_divergente FROM ordens_compra WHERE id = %s", (oc_id,)).fetchone()
    assert ordem["alerta_valor_divergente"] is False


def test_salvar_ordem_de_compra_com_divergencia_marca_alerta_valor(conn):
    oc = _oc_exemplo()
    oc.valor_total = 9999.0  # nao bate com a soma dos itens (1450.0)

    oc_id = database.salvar_ordem_de_compra(conn, oc)

    ordem = conn.execute("SELECT alerta_valor_divergente FROM ordens_compra WHERE id = %s", (oc_id,)).fetchone()
    assert ordem["alerta_valor_divergente"] is True


def test_salvar_ordem_de_compra_valor_bate_considerando_frete(conn):
    oc = _oc_exemplo()
    oc.valor_frete = 50.0
    oc.valor_total = 1500.0  # 1450 (itens) + 50 (frete) = 1500

    oc_id = database.salvar_ordem_de_compra(conn, oc)

    ordem = conn.execute("SELECT alerta_valor_divergente FROM ordens_compra WHERE id = %s", (oc_id,)).fetchone()
    assert ordem["alerta_valor_divergente"] is False


def test_salvar_ordem_de_compra_confianca_baixa_marca_alerta(conn):
    oc = _oc_exemplo()
    oc.confianca_extracao = 0.4  # abaixo do limite padrao (0.7)

    oc_id = database.salvar_ordem_de_compra(conn, oc)

    ordem = conn.execute("SELECT alerta_baixa_confianca FROM ordens_compra WHERE id = %s", (oc_id,)).fetchone()
    assert ordem["alerta_baixa_confianca"] is True


def test_salvar_ordem_de_compra_confianca_alta_nao_marca_alerta(conn):
    oc = _oc_exemplo()
    oc.confianca_extracao = 0.95

    oc_id = database.salvar_ordem_de_compra(conn, oc)

    ordem = conn.execute("SELECT alerta_baixa_confianca FROM ordens_compra WHERE id = %s", (oc_id,)).fetchone()
    assert ordem["alerta_baixa_confianca"] is False


def test_salvar_ordem_de_compra_sem_confianca_nao_marca_alerta(conn):
    oc = _oc_exemplo()
    oc.confianca_extracao = None

    oc_id = database.salvar_ordem_de_compra(conn, oc)

    ordem = conn.execute("SELECT alerta_baixa_confianca FROM ordens_compra WHERE id = %s", (oc_id,)).fetchone()
    assert ordem["alerta_baixa_confianca"] is False


def test_salvar_ordem_de_compra_cnpj_invalido_marca_alerta(conn):
    oc_id = database.salvar_ordem_de_compra(conn, _oc_exemplo())  # CNPJs ficticios do exemplo nao passam no digito verificador

    ordem = conn.execute("SELECT alerta_cnpj_invalido FROM ordens_compra WHERE id = %s", (oc_id,)).fetchone()
    assert ordem["alerta_cnpj_invalido"] is True


def test_salvar_ordem_de_compra_cnpj_valido_nao_marca_alerta(conn):
    oc = _oc_exemplo()
    oc.cliente = Cliente(nome="Hospital Exemplo", cnpj="11.222.333/0000-09")
    oc.fornecedor = Fornecedor(nome="Mederi Distribuicao", cnpj="11.222.333/0000-09")

    oc_id = database.salvar_ordem_de_compra(conn, oc)

    ordem = conn.execute("SELECT alerta_cnpj_invalido FROM ordens_compra WHERE id = %s", (oc_id,)).fetchone()
    assert ordem["alerta_cnpj_invalido"] is False


def test_salvar_ordem_de_compra_sem_cnpj_nao_marca_alerta(conn):
    oc = _oc_exemplo()
    oc.cliente = Cliente(nome="Hospital Sem CNPJ")
    oc.fornecedor = Fornecedor(nome="Mederi Distribuicao")

    oc_id = database.salvar_ordem_de_compra(conn, oc)

    ordem = conn.execute("SELECT alerta_cnpj_invalido FROM ordens_compra WHERE id = %s", (oc_id,)).fetchone()
    assert ordem["alerta_cnpj_invalido"] is False


def test_contar_falhas_arquivo(conn):
    arquivo = _arquivo("arquivo.pdf")
    outro = _arquivo("outro.pdf")
    database.registrar_log_extracao(conn, arquivo, status="erro_extracao", erro="falha 1")
    database.registrar_log_extracao(conn, arquivo, status="erro_leitura", erro="falha 2")
    database.registrar_log_extracao(conn, arquivo, status="ok")
    database.registrar_log_extracao(conn, outro, status="erro_extracao", erro="falha em outro arquivo")

    assert database.contar_falhas_arquivo(conn, arquivo) == 2
    assert database.contar_falhas_arquivo(conn, outro) == 1
    assert database.contar_falhas_arquivo(conn, _arquivo("nunca_falhou.pdf")) == 0


def test_salvar_ordem_de_compra_mesmo_numero_clientes_diferentes_nao_marca_duplicata(conn):
    oc_cliente_a = _oc_exemplo(arquivo="a.pdf")
    oc_cliente_b = _oc_exemplo(arquivo="b.pdf")
    oc_cliente_b.cliente = Cliente(nome="Outro Hospital", cnpj="99.999.999/0001-99")

    id_a = database.salvar_ordem_de_compra(conn, oc_cliente_a)
    id_b = database.salvar_ordem_de_compra(conn, oc_cliente_b)

    status = [
        row["status_extracao"]
        for row in conn.execute(
            "SELECT status_extracao FROM ordens_compra WHERE id IN (%s, %s)", (id_a, id_b)
        ).fetchall()
    ]
    assert status == ["ok", "ok"]
