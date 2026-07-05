"""
Leitura de OCs a partir de uma pasta local (ou de rede), em vez de conectar
diretamente a uma caixa de e-mail.

Na pratica, essa pasta pode ser alimentada de varias formas sem exigir
nenhuma credencial de Azure/Graph API: uma regra do Outlook que salva
automaticamente os anexos de um remetente em uma pasta do OneDrive/rede,
um scanner de mesa que salva PDFs recebidos, ou a propria Madu arrastando
os anexos manualmente. O pipeline so precisa saber o caminho da pasta.

Cada PDF processado com sucesso e movido para uma subpasta "processados/"
dentro da pasta de entrada, para que a pasta de entrada sempre reflita
apenas os arquivos que ainda faltam processar. Um PDF que falha repetidas
vezes (ver LIMITE_FALHAS_QUARENTENA em pipeline.py) e movido para uma
subpasta "falhas/" em vez de ficar tentando para sempre a cada execucao.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

NOME_SUBPASTA_PROCESSADOS = "processados"
NOME_SUBPASTA_FALHAS = "falhas"
SUBPASTAS_IGNORADAS = {NOME_SUBPASTA_PROCESSADOS, NOME_SUBPASTA_FALHAS}


class FolderWatcherError(Exception):
    """Erro de configuracao da pasta de entrada (nao existe, nao e diretorio, etc.)."""


def coletar_pdfs(pasta_entrada: str | Path) -> list[Path]:
    """Lista os PDFs pendentes de processamento em uma pasta de entrada.

    Ignora as subpastas de processados/falhas, para nao reprocessar
    arquivos ja movidos por uma execucao anterior do pipeline.
    """

    pasta_entrada = Path(pasta_entrada)
    if not pasta_entrada.exists():
        raise FolderWatcherError(
            f"Pasta de entrada nao encontrada: {pasta_entrada}. Configure "
            "PASTA_ENTRADA_OC no .env apontando para uma pasta valida (ver .env.example)."
        )
    if not pasta_entrada.is_dir():
        raise FolderWatcherError(f"Caminho informado nao e uma pasta: {pasta_entrada}")

    return sorted(
        caminho
        for caminho in pasta_entrada.glob("*.pdf")
        if caminho.parent.name not in SUBPASTAS_IGNORADAS
    )


def _mover_para_subpasta(caminho_pdf: str | Path, nome_subpasta: str) -> Path:
    caminho_pdf = Path(caminho_pdf)
    destino_dir = caminho_pdf.parent / nome_subpasta
    destino_dir.mkdir(exist_ok=True)

    destino = destino_dir / caminho_pdf.name
    if destino.exists():
        sufixo = int(caminho_pdf.stat().st_mtime)
        destino = destino_dir / f"{caminho_pdf.stem}_{sufixo}{caminho_pdf.suffix}"

    shutil.move(str(caminho_pdf), str(destino))
    return destino


def marcar_como_processado(caminho_pdf: str | Path) -> Path:
    """Move um PDF ja processado para a subpasta 'processados/', evitando reprocessamento."""

    destino = _mover_para_subpasta(caminho_pdf, NOME_SUBPASTA_PROCESSADOS)
    logger.info("Arquivo movido para %s", destino)
    return destino


def mover_para_falhas(caminho_pdf: str | Path) -> Path:
    """Move um PDF que falhou repetidas vezes para a subpasta 'falhas/'.

    Evita que um arquivo permanentemente problematico (PDF corrompido,
    layout que o modelo nunca consegue interpretar) fique sendo tentado
    para sempre a cada execucao do pipeline. Nao exclui o arquivo, apenas
    tira ele da fila de pendentes - continua disponivel para inspecao manual.
    """

    destino = _mover_para_subpasta(caminho_pdf, NOME_SUBPASTA_FALHAS)
    logger.warning("Arquivo movido para quarentena (falhas repetidas): %s", destino)
    return destino
