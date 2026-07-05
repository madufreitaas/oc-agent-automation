"""
Orquestrador do pipeline: ingestao -> extracao -> banco de dados.

Dois modos, controlados pela variavel de ambiente MODO_EXECUCAO (ou
--modo na CLI):

- demo (padrao): le os PDFs sinteticos de demo_data/pdfs/, sem precisar de
  nenhuma credencial. E o modo usado ao clonar o repo e rodar direto.
- producao: le os PDFs de uma pasta configuravel (PASTA_ENTRADA_OC no .env,
  ou --pasta na CLI), onde os anexos de OC ja tenham sido salvos por fora
  do pipeline (regra do Outlook, pasta de rede, upload manual etc). Exige
  OPENROUTER_API_KEY configurada (ver .env.example).

Em ambos os modos, a extracao de cada PDF usa o mesmo caminho:
pdf_reader -> llm_extractor -> database. No modo producao, cada PDF
processado com sucesso e movido para uma subpasta "processados/" dentro da
pasta de entrada (ver folder_watcher.py), para nao ser reprocessado na
proxima execucao. Um arquivo que falha repetidamente (LIMITE_FALHAS_QUARENTENA
tentativas) e movido para uma subpasta "falhas/" em vez de ficar sendo
tentado para sempre.

Antes de cada execucao, o banco e copiado para output/database/backups/
(database.fazer_backup) e, se houver mais PDFs pendentes do que
LIMITE_ARQUIVOS_POR_EXECUCAO, o excedente fica para a proxima execucao (util
para nao estourar limite de taxa da API se a pasta acumular muitos arquivos).

Cada modo grava por padrao em um banco SQLite diferente (para nao misturar
dado real com dado de demonstracao): modo demo usa
output/database/oc_agent_demo.db, modo producao usa
output/database/oc_agent.db. Use --db para sobrepor esse caminho.
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
from pathlib import Path

from dotenv import load_dotenv

import database
import folder_watcher
import pdf_reader
from llm_extractor import ExtractionError, extrair_ordem_de_compra
from pdf_reader import PDFReadError

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
DEMO_PDFS_DIR = RAIZ_PROJETO / "demo_data" / "pdfs"
LOG_DIR = RAIZ_PROJETO / "output" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            LOG_DIR / "pipeline.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        ),
    ],
)
logger = logging.getLogger(__name__)

# Depois de N falhas acumuladas, um arquivo vai para a pasta de quarentena
# (folder_watcher.mover_para_falhas) em vez de ser tentado para sempre.
LIMITE_FALHAS_QUARENTENA = int(os.environ.get("LIMITE_FALHAS_QUARENTENA", "3"))

# Se N ou mais arquivos falharem em uma unica execucao, registra um alerta
# bem visivel no log (o relatorio HTML tambem mostra esse alerta como banner).
LIMITE_ALERTA_FALHAS = int(os.environ.get("LIMITE_ALERTA_FALHAS", "3"))

# Numero maximo de arquivos processados em uma unica execucao (0 = sem
# limite). Protege contra estourar limite de taxa da API se a pasta de
# entrada acumular muitos PDFs de uma vez; o restante fica pendente para a
# proxima execucao agendada.
LIMITE_ARQUIVOS_POR_EXECUCAO = int(os.environ.get("LIMITE_ARQUIVOS_POR_EXECUCAO", "0"))


def _coletar_pdfs_demo() -> list[Path]:
    return sorted(DEMO_PDFS_DIR.glob("*.pdf"))


def _coletar_pdfs_producao(pasta_entrada: str | None = None) -> list[Path]:
    pasta_entrada = pasta_entrada or os.environ.get("PASTA_ENTRADA_OC")
    if not pasta_entrada:
        raise ValueError(
            "Pasta de entrada nao configurada. Defina PASTA_ENTRADA_OC no .env "
            "ou passe --pasta na linha de comando."
        )
    return folder_watcher.coletar_pdfs(pasta_entrada)


def processar_pdf(conn, caminho_pdf: Path) -> bool:
    """Processa um unico PDF (texto -> LLM -> banco). Retorna True se ok."""

    try:
        extraido = pdf_reader.extrair_texto(caminho_pdf)
    except PDFReadError as exc:
        logger.error("Falha na leitura de %s: %s", caminho_pdf.name, exc)
        database.registrar_log_extracao(conn, caminho_pdf.name, status="erro_leitura", erro=str(exc))
        return False

    try:
        oc = extrair_ordem_de_compra(extraido.texto, arquivo_origem=caminho_pdf.name)
    except ExtractionError as exc:
        logger.error("Falha na extracao de %s: %s", caminho_pdf.name, exc)
        database.registrar_log_extracao(conn, caminho_pdf.name, status="erro_extracao", erro=str(exc))
        return False

    database.salvar_ordem_de_compra(conn, oc)
    database.registrar_log_extracao(
        conn, caminho_pdf.name, status="ok", confianca=oc.confianca_extracao
    )
    logger.info(
        "OC %s (%s) processada com sucesso - %d item(ns)",
        oc.numero_oc,
        caminho_pdf.name,
        len(oc.itens),
    )
    return True


def executar_pipeline(
    modo: str = "demo",
    db_path: str | Path = database.DB_PADRAO_PATH,
    pasta_entrada: str | None = None,
) -> dict:
    """Executa o pipeline completo e retorna um resumo (total, sucesso, falhas)."""

    if modo == "demo":
        pdfs = _coletar_pdfs_demo()
    elif modo == "producao":
        pdfs = _coletar_pdfs_producao(pasta_entrada)
    else:
        raise ValueError(f"Modo desconhecido: {modo!r} (use 'demo' ou 'producao')")

    if not pdfs:
        logger.warning("Nenhum PDF encontrado para processar (modo=%s)", modo)
    elif LIMITE_ARQUIVOS_POR_EXECUCAO > 0 and len(pdfs) > LIMITE_ARQUIVOS_POR_EXECUCAO:
        logger.info(
            "Limitando esta execucao a %d de %d arquivo(s) pendentes (LIMITE_ARQUIVOS_POR_EXECUCAO)",
            LIMITE_ARQUIVOS_POR_EXECUCAO,
            len(pdfs),
        )
        pdfs = pdfs[:LIMITE_ARQUIVOS_POR_EXECUCAO]

    database.fazer_backup(db_path)

    conn = database.conectar(db_path)
    database.inicializar_schema(conn)

    sucesso = 0
    falhas = 0
    for caminho_pdf in pdfs:
        if processar_pdf(conn, caminho_pdf):
            sucesso += 1
            if modo == "producao":
                folder_watcher.marcar_como_processado(caminho_pdf)
        else:
            falhas += 1
            if modo == "producao":
                total_falhas_arquivo = database.contar_falhas_arquivo(conn, caminho_pdf.name)
                if total_falhas_arquivo >= LIMITE_FALHAS_QUARENTENA:
                    folder_watcher.mover_para_falhas(caminho_pdf)
                    logger.warning(
                        "%s movido para quarentena apos %d falha(s) de extracao",
                        caminho_pdf.name,
                        total_falhas_arquivo,
                    )

    conn.close()

    resumo = {"modo": modo, "total": len(pdfs), "sucesso": sucesso, "falhas": falhas}
    logger.info("Pipeline concluido: %s", resumo)

    if falhas >= LIMITE_ALERTA_FALHAS:
        logger.error(
            "ALERTA: %d arquivo(s) falharam nesta execucao (limite: %d). "
            "Verifique a secao de log de extracao no relatorio.",
            falhas,
            LIMITE_ALERTA_FALHAS,
        )

    return resumo


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Pipeline de extracao de Ordens de Compra")
    parser.add_argument(
        "--modo",
        choices=["demo", "producao"],
        default=os.environ.get("MODO_EXECUCAO", "demo"),
        help="demo: usa PDFs sinteticos locais. producao: le PDFs de uma pasta configurada.",
    )
    parser.add_argument(
        "--pasta",
        default=None,
        help="Pasta de entrada para o modo producao (sobrepoe PASTA_ENTRADA_OC do .env).",
    )
    parser.add_argument(
        "--db",
        default=None,
        help=(
            "Caminho do arquivo SQLite de saida. Se omitido, usa "
            f"{database.DB_DEMO_PATH.name} em modo demo ou {database.DB_PADRAO_PATH.name} "
            "em modo producao, para nao misturar dado real com dado de demonstracao."
        ),
    )
    args = parser.parse_args()

    db_path = args.db or (
        database.DB_DEMO_PATH if args.modo == "demo" else database.DB_PADRAO_PATH
    )
    executar_pipeline(modo=args.modo, db_path=db_path, pasta_entrada=args.pasta)


if __name__ == "__main__":
    main()
