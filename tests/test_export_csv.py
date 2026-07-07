import csv
from pathlib import Path

import pytest

import database
from export_csv import exportar_csv
from schema import Cliente, Fornecedor, ItemOC, OrdemDeCompra

PREFIXO_TESTE = "teste_export_csv_"


@pytest.fixture
def dsn():
    valor = database.dsn_demo()
    if not valor:
        pytest.skip("DATABASE_URL_DEMO nao configurada - ver docs/arquitetura_webapp.md")

    yield valor

    conexao = database.conectar(valor)
    conexao.execute("DELETE FROM ordens_compra WHERE arquivo_origem LIKE %s", (f"{PREFIXO_TESTE}%",))
    conexao.execute(
        "DELETE FROM clientes WHERE id NOT IN (SELECT DISTINCT cliente_id FROM ordens_compra)"
    )
    conexao.execute(
        "DELETE FROM fornecedores WHERE id NOT IN (SELECT DISTINCT fornecedor_id FROM ordens_compra)"
    )
    conexao.commit()
    conexao.close()


def test_exportar_csv_gera_arquivo_com_cabecalho_e_dados(tmp_path: Path, dsn):
    conn = database.conectar(dsn)

    oc = OrdemDeCompra(
        numero_oc="999",
        data_emissao="2026-06-01",
        cliente=Cliente(nome="Hospital Teste", cnpj="00.000.000/0001-00"),
        fornecedor=Fornecedor(nome="Mederi Distribuicao"),
        itens=[
            ItemOC(descricao="Item Teste", quantidade=1, valor_unitario=100.0, valor_total=100.0)
        ],
        valor_total=100.0,
        tipo_faturamento="FATURAR E REPOR",
        arquivo_origem=f"{PREFIXO_TESTE}exemplo.pdf",
    )
    database.salvar_ordem_de_compra(conn, oc)
    conn.close()

    query_path = tmp_path / "consulta.sql"
    query_path.write_text(
        "SELECT numero_oc, valor_total, tipo_faturamento FROM ordens_compra WHERE arquivo_origem = "
        f"'{PREFIXO_TESTE}exemplo.pdf'",
        encoding="utf-8",
    )
    saida_path = tmp_path / "saida.csv"

    caminho = exportar_csv(query_path, saida_path, dsn)

    assert caminho == saida_path
    with saida_path.open(newline="", encoding="utf-8") as arquivo:
        linhas = list(csv.reader(arquivo))

    assert linhas[0] == ["numero_oc", "valor_total", "tipo_faturamento"]
    assert linhas[1] == ["999", "100.0", "FATURAR E REPOR"]
