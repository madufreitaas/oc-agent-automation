"""
Exporta o resultado de uma consulta SQL do banco de OCs (Postgres/Supabase)
para um arquivo CSV, usando so csv da biblioteca padrao do Python.

Uso:
    python src/export_csv.py
    python src/export_csv.py --query sql/queries/itens_mais_recorrentes.sql --saida output/csv/itens.csv
"""

from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path

from dotenv import load_dotenv

import database

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
QUERY_PADRAO = RAIZ_PROJETO / "sql" / "queries" / "exportar_csv_ordens_compra.sql"
SAIDA_PADRAO = RAIZ_PROJETO / "output" / "csv" / "ordens_compra.csv"


def gerar_csv_string(caminho_query: str | Path, dsn: str) -> str:
    """Roda a consulta SQL informada e retorna o resultado como texto CSV (com cabecalho).

    Reaproveitada tanto por exportar_csv (grava em arquivo) quanto por
    report_generator.py (embute o CSV nos botoes de download do relatorio HTML).
    """

    conn = database.conectar(dsn)
    sql = Path(caminho_query).read_text(encoding="utf-8")
    cursor = conn.execute(sql)

    colunas = [descricao[0] for descricao in cursor.description]
    # cursor.fetchall() devolve dicts (row_factory=dict_row, ver database.conectar) -
    # csv.writer.writerows precisa de sequencias na ordem das colunas, nao dicts
    # (iterar um dict devolveria as chaves, nao os valores).
    linhas = [[row[coluna] for coluna in colunas] for row in cursor.fetchall()]
    conn.close()

    buffer = io.StringIO()
    escritor = csv.writer(buffer, lineterminator="\n")
    escritor.writerow(colunas)
    escritor.writerows(linhas)
    return buffer.getvalue()


def exportar_csv(
    caminho_query: str | Path = QUERY_PADRAO,
    caminho_saida: str | Path = SAIDA_PADRAO,
    dsn: str = "",
) -> Path:
    """Roda a consulta SQL informada e grava o resultado como arquivo CSV."""

    texto_csv = gerar_csv_string(caminho_query, dsn)

    caminho_saida = Path(caminho_saida)
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    caminho_saida.write_text(texto_csv, encoding="utf-8", newline="")

    return caminho_saida


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Exporta uma consulta SQL do banco de OCs para CSV")
    parser.add_argument("--query", default=str(QUERY_PADRAO), help="Caminho do arquivo .sql")
    parser.add_argument("--saida", default=str(SAIDA_PADRAO), help="Caminho do CSV de saida")
    parser.add_argument(
        "--dsn",
        default=None,
        help="String de conexao Postgres. Se omitido, usa DATABASE_URL_DEMO do .env.",
    )
    args = parser.parse_args()

    caminho = exportar_csv(args.query, args.saida, args.dsn or database.dsn_demo())
    print(f"CSV gerado em {caminho}")


if __name__ == "__main__":
    main()
