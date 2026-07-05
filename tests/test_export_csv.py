import csv
from pathlib import Path

import database
from export_csv import exportar_csv
from schema import Cliente, Fornecedor, ItemOC, OrdemDeCompra


def test_exportar_csv_gera_arquivo_com_cabecalho_e_dados(tmp_path: Path):
    db_path = tmp_path / "teste.db"
    conn = database.conectar(db_path)
    database.inicializar_schema(conn)

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
    )
    database.salvar_ordem_de_compra(conn, oc)
    conn.close()

    query_path = tmp_path / "consulta.sql"
    query_path.write_text(
        "SELECT numero_oc, valor_total, tipo_faturamento FROM ordens_compra",
        encoding="utf-8",
    )
    saida_path = tmp_path / "saida.csv"

    caminho = exportar_csv(query_path, saida_path, db_path)

    assert caminho == saida_path
    with saida_path.open(newline="", encoding="utf-8") as arquivo:
        linhas = list(csv.reader(arquivo))

    assert linhas[0] == ["numero_oc", "valor_total", "tipo_faturamento"]
    assert linhas[1] == ["999", "100.0", "FATURAR E REPOR"]
