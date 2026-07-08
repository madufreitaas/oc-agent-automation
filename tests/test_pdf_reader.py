from pathlib import Path

import pytest

from pdf_reader import PDFReadError, extrair_texto

DEMO_PDFS_DIR = Path(__file__).resolve().parent.parent / "demo_data" / "pdfs"


def test_extrai_texto_de_todos_os_pdfs_demo():
    # >= 4 (nao ==): generate_demo_pdfs.py --extra/--duplicatas pode ter
    # adicionado PDFs extras nesta pasta para testar o pipeline com mais
    # volume - os 4 base continuam sempre presentes (gerar_pdfs_base()).
    pdfs = sorted(DEMO_PDFS_DIR.glob("*.pdf"))
    assert len(pdfs) >= 4, "esperado pelo menos os 4 PDFs sinteticos base em demo_data/pdfs"

    for caminho in pdfs:
        resultado = extrair_texto(caminho)
        assert resultado.texto.strip()
        assert resultado.paginas >= 1
        assert resultado.usou_ocr is False


def test_extrai_texto_hospital_classico_contem_campos_esperados():
    caminho = DEMO_PDFS_DIR / "oc_hospital_santa_cecilia_481290.pdf"
    resultado = extrair_texto(caminho)
    assert "481290" in resultado.texto
    assert "MEDERI" in resultado.texto.upper()


def test_arquivo_inexistente_levanta_erro():
    with pytest.raises(PDFReadError):
        extrair_texto(DEMO_PDFS_DIR / "nao_existe.pdf")
