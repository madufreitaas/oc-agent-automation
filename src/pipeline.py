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

Se houver mais PDFs pendentes do que LIMITE_ARQUIVOS_POR_EXECUCAO, o
excedente fica para a proxima execucao (util para nao estourar limite de taxa
da API se a pasta acumular muitos arquivos).

Ate LIMITE_CONCORRENCIA PDFs sao extraidos em paralelo (ThreadPoolExecutor) -
o gargalo e a espera pela resposta da LLM (rede), nao CPU, entao isso reduz o
tempo total sem aumentar o numero de chamadas/tokens gastos. Cada worker
thread usa sua propria conexao Postgres (psycopg.Connection nao e
thread-safe para uso concorrente); o resto do fluxo por arquivo (mover para
processados/falhas, contar falhas) continua sequencial na thread principal.

Cada modo grava por padrao em um projeto Postgres/Supabase diferente (dois
projetos SEPARADOS, para nao misturar dado real com dado de demonstracao):
modo demo usa DATABASE_URL_DEMO, modo producao usa DATABASE_URL_PRODUCAO (ver
.env e docs/arquitetura_webapp.md). Backup do banco agora e responsabilidade
do proprio Supabase (nao ha mais copia de arquivo local a fazer).
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
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

# Quantos PDFs sao extraidos em paralelo (chamada a LLM via OpenRouter e o
# maior gargalo do pipeline - rede, nao CPU - entao rodar N de cada vez
# reduz o tempo total por um fator proximo de N, sem aumentar o custo em
# tokens: e o mesmo numero de chamadas, so nao mais uma esperando a outra).
# Nao aumente demais - passar do limite de taxa (rate limit) do seu plano
# na OpenRouter gera 429 e retry, o que ai sim desperdica tokens.
LIMITE_CONCORRENCIA = max(1, int(os.environ.get("LIMITE_CONCORRENCIA", "5")))


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
    dsn: str | None = None,
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

    dsn = dsn or (database.dsn_demo() if modo == "demo" else database.dsn_producao())
    conn = database.conectar(dsn)
    database.inicializar_schema(conn)

    # Cada PDF e extraido (chamada a LLM) e gravado (commit proprio, ver
    # database.salvar_ordem_de_compra/registrar_log_extracao) de forma
    # independente - psycopg.Connection nao e thread-safe para uso
    # concorrente, entao cada worker thread do pool abre e reaproveita a
    # propria conexao (uma por thread, nao uma por PDF) via threading.local.
    conexoes_por_thread = threading.local()
    conexoes_abertas = []

    def _conexao_da_thread() -> psycopg.Connection:
        conexao = getattr(conexoes_por_thread, "conexao", None)
        if conexao is None:
            conexao = database.conectar(dsn)
            conexoes_por_thread.conexao = conexao
            conexoes_abertas.append(conexao)
        return conexao

    def _tarefa(caminho_pdf: Path) -> bool:
        return processar_pdf(_conexao_da_thread(), caminho_pdf)

    sucesso = 0
    falhas = 0
    concorrencia = min(LIMITE_CONCORRENCIA, len(pdfs)) or 1
    with ThreadPoolExecutor(max_workers=concorrencia) as executor:
        for caminho_pdf, deu_certo in zip(pdfs, executor.map(_tarefa, pdfs)):
            if deu_certo:
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

    for conexao in conexoes_abertas:
        conexao.close()
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
        "--dsn",
        default=None,
        help=(
            "String de conexao Postgres. Se omitido, usa DATABASE_URL_DEMO em "
            "modo demo ou DATABASE_URL_PRODUCAO em modo producao (.env), para "
            "nao misturar dado real com dado de demonstracao."
        ),
    )
    args = parser.parse_args()

    executar_pipeline(modo=args.modo, dsn=args.dsn, pasta_entrada=args.pasta)


if __name__ == "__main__":
    main()
