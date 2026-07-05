from pathlib import Path

import database
from schema import Cliente, DadosClinicos, Fornecedor, ItemOC, OrdemDeCompra


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
        arquivo_origem=arquivo,
        confianca_extracao=0.9,
    )


def test_inicializar_schema_cria_tabelas(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    tabelas = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    esperado = {"clientes", "fornecedores", "ordens_compra", "itens_oc", "dados_clinicos", "log_extracao"}
    assert esperado.issubset(tabelas)
    conn.close()


def test_inicializar_schema_migra_banco_antigo_sem_perder_dados(tmp_path: Path):
    """Simula um banco criado antes da coluna alerta_valor_divergente existir:
    inicializar_schema deve adicionar a coluna via ALTER TABLE, sem apagar
    nenhum dado ja gravado."""

    conn = database.conectar(tmp_path / "teste.db")
    conn.executescript("""
        CREATE TABLE clientes (id INTEGER PRIMARY KEY, nome TEXT NOT NULL, cnpj TEXT, cidade TEXT, uf TEXT);
        CREATE TABLE fornecedores (id INTEGER PRIMARY KEY, nome TEXT NOT NULL, cnpj TEXT);
        CREATE TABLE ordens_compra (
            id INTEGER PRIMARY KEY, numero_oc TEXT NOT NULL, data_emissao TEXT,
            cliente_id INTEGER, fornecedor_id INTEGER, valor_total REAL
        );
        CREATE TABLE itens_oc (id INTEGER PRIMARY KEY, ordem_compra_id INTEGER);
        CREATE TABLE dados_clinicos (id INTEGER PRIMARY KEY, ordem_compra_id INTEGER);
        CREATE TABLE log_extracao (id INTEGER PRIMARY KEY, arquivo TEXT);
        INSERT INTO clientes (id, nome) VALUES (1, 'Hospital Antigo');
        INSERT INTO fornecedores (id, nome) VALUES (1, 'Mederi');
        INSERT INTO ordens_compra (id, numero_oc, cliente_id, fornecedor_id, valor_total)
        VALUES (1, '999', 1, 1, 500.0);
    """)
    conn.commit()

    database.inicializar_schema(conn)

    ordem = conn.execute("SELECT * FROM ordens_compra WHERE id = 1").fetchone()
    assert ordem["numero_oc"] == "999"  # dado antigo preservado
    assert ordem["valor_total"] == 500.0
    assert ordem["alerta_valor_divergente"] == 0  # coluna nova, com valor padrao
    assert ordem["tipo_faturamento"] is None
    assert ordem["status_extracao"] == "ok"
    conn.close()


def test_salvar_ordem_de_compra_persiste_itens_e_dados_clinicos(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    oc_id = database.salvar_ordem_de_compra(conn, _oc_exemplo())

    ordem = conn.execute("SELECT * FROM ordens_compra WHERE id = ?", (oc_id,)).fetchone()
    assert ordem["numero_oc"] == "12345"
    assert ordem["valor_total"] == 1450.0
    assert ordem["tipo_faturamento"] == "FATURAR E REPOR"

    itens = conn.execute("SELECT * FROM itens_oc WHERE ordem_compra_id = ?", (oc_id,)).fetchall()
    assert len(itens) == 1
    assert itens[0]["descricao"] == "Stent coronario 3.0x18mm"

    clinico = conn.execute(
        "SELECT * FROM dados_clinicos WHERE ordem_compra_id = ?", (oc_id,)
    ).fetchone()
    assert clinico["paciente"] == "Paciente Teste"
    conn.close()


def test_salvar_ordem_de_compra_e_idempotente(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    oc = _oc_exemplo()
    id_1 = database.salvar_ordem_de_compra(conn, oc)
    id_2 = database.salvar_ordem_de_compra(conn, oc)

    assert id_1 == id_2
    total = conn.execute("SELECT COUNT(*) AS n FROM ordens_compra").fetchone()["n"]
    assert total == 1
    conn.close()


def test_registrar_log_extracao(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    database.registrar_log_extracao(conn, "arquivo.pdf", status="ok", confianca=0.87)
    logs = conn.execute("SELECT * FROM log_extracao").fetchall()
    assert len(logs) == 1
    assert logs[0]["status"] == "ok"
    conn.close()


def test_salvar_ordem_de_compra_status_ok_por_padrao(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    oc_id = database.salvar_ordem_de_compra(conn, _oc_exemplo())

    ordem = conn.execute("SELECT status_extracao FROM ordens_compra WHERE id = ?", (oc_id,)).fetchone()
    assert ordem["status_extracao"] == "ok"
    conn.close()


def test_salvar_ordem_de_compra_mesmo_numero_arquivos_diferentes_marca_duplicata(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    id_1 = database.salvar_ordem_de_compra(conn, _oc_exemplo(arquivo="arquivo_a.pdf"))
    id_2 = database.salvar_ordem_de_compra(conn, _oc_exemplo(arquivo="arquivo_b.pdf"))

    assert id_1 != id_2
    total = conn.execute("SELECT COUNT(*) AS n FROM ordens_compra").fetchone()["n"]
    assert total == 2  # nenhum registro e excluido, so sinalizado

    status = {
        row["id"]: row["status_extracao"]
        for row in conn.execute("SELECT id, status_extracao FROM ordens_compra").fetchall()
    }
    assert status[id_1] == "possivel_duplicata"
    assert status[id_2] == "possivel_duplicata"
    conn.close()


def test_salvar_ordem_de_compra_numeros_diferentes_nao_marca_duplicata(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    database.salvar_ordem_de_compra(conn, _oc_exemplo(numero_oc="111", arquivo="a.pdf"))
    database.salvar_ordem_de_compra(conn, _oc_exemplo(numero_oc="222", arquivo="b.pdf"))

    status = [row["status_extracao"] for row in conn.execute("SELECT status_extracao FROM ordens_compra").fetchall()]
    assert status == ["ok", "ok"]
    conn.close()


def test_salvar_ordem_de_compra_sem_divergencia_nao_marca_alerta_valor(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    oc_id = database.salvar_ordem_de_compra(conn, _oc_exemplo())  # itens somam exatamente o valor_total

    ordem = conn.execute("SELECT alerta_valor_divergente FROM ordens_compra WHERE id = ?", (oc_id,)).fetchone()
    assert ordem["alerta_valor_divergente"] == 0
    conn.close()


def test_salvar_ordem_de_compra_com_divergencia_marca_alerta_valor(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    oc = _oc_exemplo()
    oc.valor_total = 9999.0  # nao bate com a soma dos itens (1450.0)

    oc_id = database.salvar_ordem_de_compra(conn, oc)

    ordem = conn.execute("SELECT alerta_valor_divergente FROM ordens_compra WHERE id = ?", (oc_id,)).fetchone()
    assert ordem["alerta_valor_divergente"] == 1
    conn.close()


def test_salvar_ordem_de_compra_valor_bate_considerando_frete(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    oc = _oc_exemplo()
    oc.valor_frete = 50.0
    oc.valor_total = 1500.0  # 1450 (itens) + 50 (frete) = 1500

    oc_id = database.salvar_ordem_de_compra(conn, oc)

    ordem = conn.execute("SELECT alerta_valor_divergente FROM ordens_compra WHERE id = ?", (oc_id,)).fetchone()
    assert ordem["alerta_valor_divergente"] == 0
    conn.close()


def test_salvar_ordem_de_compra_confianca_baixa_marca_alerta(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    oc = _oc_exemplo()
    oc.confianca_extracao = 0.4  # abaixo do limite padrao (0.7)

    oc_id = database.salvar_ordem_de_compra(conn, oc)

    ordem = conn.execute("SELECT alerta_baixa_confianca FROM ordens_compra WHERE id = ?", (oc_id,)).fetchone()
    assert ordem["alerta_baixa_confianca"] == 1
    conn.close()


def test_salvar_ordem_de_compra_confianca_alta_nao_marca_alerta(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    oc = _oc_exemplo()
    oc.confianca_extracao = 0.95

    oc_id = database.salvar_ordem_de_compra(conn, oc)

    ordem = conn.execute("SELECT alerta_baixa_confianca FROM ordens_compra WHERE id = ?", (oc_id,)).fetchone()
    assert ordem["alerta_baixa_confianca"] == 0
    conn.close()


def test_salvar_ordem_de_compra_sem_confianca_nao_marca_alerta(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    oc = _oc_exemplo()
    oc.confianca_extracao = None

    oc_id = database.salvar_ordem_de_compra(conn, oc)

    ordem = conn.execute("SELECT alerta_baixa_confianca FROM ordens_compra WHERE id = ?", (oc_id,)).fetchone()
    assert ordem["alerta_baixa_confianca"] == 0
    conn.close()


def test_salvar_ordem_de_compra_cnpj_invalido_marca_alerta(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    oc_id = database.salvar_ordem_de_compra(conn, _oc_exemplo())  # CNPJs ficticios do exemplo nao passam no digito verificador

    ordem = conn.execute("SELECT alerta_cnpj_invalido FROM ordens_compra WHERE id = ?", (oc_id,)).fetchone()
    assert ordem["alerta_cnpj_invalido"] == 1
    conn.close()


def test_salvar_ordem_de_compra_cnpj_valido_nao_marca_alerta(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    oc = _oc_exemplo()
    oc.cliente = Cliente(nome="Hospital Exemplo", cnpj="11.222.333/0000-09")
    oc.fornecedor = Fornecedor(nome="Mederi Distribuicao", cnpj="11.222.333/0000-09")

    oc_id = database.salvar_ordem_de_compra(conn, oc)

    ordem = conn.execute("SELECT alerta_cnpj_invalido FROM ordens_compra WHERE id = ?", (oc_id,)).fetchone()
    assert ordem["alerta_cnpj_invalido"] == 0
    conn.close()


def test_salvar_ordem_de_compra_sem_cnpj_nao_marca_alerta(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    oc = _oc_exemplo()
    oc.cliente = Cliente(nome="Hospital Sem CNPJ")
    oc.fornecedor = Fornecedor(nome="Mederi Distribuicao")

    oc_id = database.salvar_ordem_de_compra(conn, oc)

    ordem = conn.execute("SELECT alerta_cnpj_invalido FROM ordens_compra WHERE id = ?", (oc_id,)).fetchone()
    assert ordem["alerta_cnpj_invalido"] == 0
    conn.close()


def test_fazer_backup_retorna_none_se_banco_nao_existe(tmp_path: Path):
    assert database.fazer_backup(tmp_path / "nao_existe.db") is None


def test_fazer_backup_cria_copia(tmp_path: Path):
    db_path = tmp_path / "teste.db"
    conn = database.conectar(db_path)
    database.inicializar_schema(conn)
    conn.close()

    destino = database.fazer_backup(db_path)

    assert destino is not None
    assert destino.exists()
    assert destino.parent.name == "backups"


def test_fazer_backup_mantem_apenas_ultimos_n(tmp_path: Path, monkeypatch):
    from datetime import datetime as datetime_real

    db_path = tmp_path / "teste.db"
    conn = database.conectar(db_path)
    database.inicializar_schema(conn)
    conn.close()

    contador = {"n": 0}

    class _DatetimeFalso:
        @staticmethod
        def now():
            contador["n"] += 1
            return datetime_real(2026, 1, 1, 0, 0, contador["n"] % 60)

    monkeypatch.setattr(database, "datetime", _DatetimeFalso)

    for _ in range(5):
        database.fazer_backup(db_path, manter_ultimos=3)

    backups = sorted((tmp_path / "backups").glob("teste_*.db"))
    assert len(backups) == 3


def test_contar_falhas_arquivo(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    database.registrar_log_extracao(conn, "arquivo.pdf", status="erro_extracao", erro="falha 1")
    database.registrar_log_extracao(conn, "arquivo.pdf", status="erro_leitura", erro="falha 2")
    database.registrar_log_extracao(conn, "arquivo.pdf", status="ok")
    database.registrar_log_extracao(conn, "outro.pdf", status="erro_extracao", erro="falha em outro arquivo")

    assert database.contar_falhas_arquivo(conn, "arquivo.pdf") == 2
    assert database.contar_falhas_arquivo(conn, "outro.pdf") == 1
    assert database.contar_falhas_arquivo(conn, "nunca_falhou.pdf") == 0
    conn.close()


def test_salvar_ordem_de_compra_mesmo_numero_clientes_diferentes_nao_marca_duplicata(tmp_path: Path):
    conn = database.conectar(tmp_path / "teste.db")
    database.inicializar_schema(conn)

    oc_cliente_a = _oc_exemplo(arquivo="a.pdf")
    oc_cliente_b = _oc_exemplo(arquivo="b.pdf")
    oc_cliente_b.cliente = Cliente(nome="Outro Hospital", cnpj="99.999.999/0001-99")

    database.salvar_ordem_de_compra(conn, oc_cliente_a)
    database.salvar_ordem_de_compra(conn, oc_cliente_b)

    status = [row["status_extracao"] for row in conn.execute("SELECT status_extracao FROM ordens_compra").fetchall()]
    assert status == ["ok", "ok"]
    conn.close()
