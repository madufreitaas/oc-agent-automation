"""
Exporta o resultado de uma consulta SQL do banco de OCs para um arquivo CSV.

Usa apenas sqlite3 e csv da biblioteca padrao do Python, sem depender do
cliente de linha de comando sqlite3 (que nao vem instalado por padrao no
Windows).

Uso:
    python src/export_csv.py
    python src/export_csv.py --query sql/queries/itens_mais_recorrentes.sql --saida output/csv/itens.csv
"""

from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path

import database

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
QUERY_PADRAO = RAIZ_PROJETO / "sql" / "queries" / "exportar_csv_ordens_compra.sql"
SAIDA_PADRAO = RAIZ_PROJETO / "output" / "csv" / "ordens_compra.csv"


def gerar_csv_string(
    caminho_query: str | Path,
    db_path: str | Path = database.DB_PADRAO_PATH,
) -> str:
    """Roda a consulta SQL informada e retorna o resultado como texto CSV (com cabecalho).

    Reaproveitada tanto por exportar_csv (grava em arquivo) quanto por
    report_generator.py (embute o CSV nos botoes de download do relatorio HTML).
    """

    conn = database.conectar(db_path)
    sql = Path(caminho_query).read_text(encoding="utf-8")
    cursor = conn.execute(sql)

    colunas = [descricao[0] for descricao in cursor.description]
    linhas = cursor.fetchall()
    conn.close()

    buffer = io.StringIO()
    escritor = csv.writer(buffer, lineterminator="\n")
    escritor.writerow(colunas)
    escritor.writerows(linhas)
    return buffer.getvalue()


def exportar_csv(
    caminho_query: str | Path = QUERY_PADRAO,
    caminho_saida: str | Path = SAIDA_PADRAO,
    db_path: str | Path = database.DB_PADRAO_PATH,
) -> Path:
    """Roda a consulta SQL informada e grava o resultado como arquivo CSV."""

    texto_csv = gerar_csv_string(caminho_query, db_path)

    caminho_saida = Path(caminho_saida)
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    caminho_saida.write_text(texto_csv, encoding="utf-8", newline="")

    return caminho_saida


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta uma consulta SQL do banco de OCs para CSV")
    parser.add_argument("--query", default=str(QUERY_PADRAO), help="Caminho do arquivo .sql")
    parser.add_argument("--saida", default=str(SAIDA_PADRAO), help="Caminho do CSV de saida")
    parser.add_argument("--db", default=str(database.DB_PADRAO_PATH), help="Caminho do banco SQLite")
    args = parser.parse_args()

    caminho = exportar_csv(args.query, args.saida, args.db)
    print(f"CSV gerado em {caminho}")


if __name__ == "__main__":
    main()
