"""
Extracao de texto bruto de PDFs de Ordem de Compra.

Usa pdfplumber como caminho principal (PDFs com texto selecionavel, o caso
comum de OCs geradas por sistema). Quando uma pagina nao retorna texto
(PDF escaneado/imagem), cai para OCR via pytesseract + pdf2image.

A saida e sempre texto puro por arquivo - a interpretacao do conteudo
(layout, campos) fica a cargo de llm_extractor.py.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)


@dataclass
class TextoExtraido:
    arquivo_origem: str
    texto: str
    paginas: int
    usou_ocr: bool


class PDFReadError(Exception):
    """Erro ao extrair texto de um PDF (arquivo corrompido, sem paginas, etc.)."""


def extrair_texto(caminho_pdf: str | Path) -> TextoExtraido:
    """Extrai o texto de todas as paginas de um PDF de OC.

    Tenta extracao direta primeiro (pdfplumber). Se uma pagina nao produzir
    nenhum texto, assume que e uma pagina escaneada e usa OCR como fallback
    para aquela pagina especifica.
    """

    caminho_pdf = Path(caminho_pdf)
    if not caminho_pdf.exists():
        raise PDFReadError(f"Arquivo nao encontrado: {caminho_pdf}")

    paginas_texto: list[str] = []
    usou_ocr = False

    with pdfplumber.open(caminho_pdf) as pdf:
        if len(pdf.pages) == 0:
            raise PDFReadError(f"PDF sem paginas: {caminho_pdf}")

        for indice, pagina in enumerate(pdf.pages):
            texto_pagina = pagina.extract_text() or ""
            if texto_pagina.strip():
                paginas_texto.append(texto_pagina)
                continue

            logger.info(
                "Pagina %d de %s sem texto extraivel, tentando OCR", indice + 1, caminho_pdf.name
            )
            texto_ocr = _ocr_pagina(caminho_pdf, indice)
            paginas_texto.append(texto_ocr)
            usou_ocr = True

    texto_completo = "\n\n".join(paginas_texto)
    if not texto_completo.strip():
        raise PDFReadError(f"Nenhum texto extraido de {caminho_pdf} (nem via OCR)")

    return TextoExtraido(
        arquivo_origem=caminho_pdf.name,
        texto=texto_completo,
        paginas=len(paginas_texto),
        usou_ocr=usou_ocr,
    )


def _ocr_pagina(caminho_pdf: Path, indice_pagina: int) -> str:
    """Executa OCR em uma unica pagina de um PDF, via pdf2image + pytesseract.

    Import tardio: pdf2image/pytesseract exigem dependencias externas
    (poppler, tesseract) que so precisam existir quando o OCR e realmente
    acionado (PDFs escaneados), nao no caminho comum de PDFs com texto.
    """

    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError as exc:
        raise PDFReadError(
            "PDF parece ser escaneado (sem texto extraivel) mas o suporte a OCR "
            "nao esta instalado. Instale pytesseract, pdf2image, e os binarios "
            "poppler e tesseract-ocr para habilitar este fallback."
        ) from exc

    imagens = convert_from_path(
        str(caminho_pdf), first_page=indice_pagina + 1, last_page=indice_pagina + 1
    )
    if not imagens:
        return ""
    return pytesseract.image_to_string(imagens[0], lang="por")
