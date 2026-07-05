"""
Gera copias "redigidas" de PDFs reais de OC, mascarando qualquer dado
clinico (paciente, convenio, carteirinha, cirurgiao, CRM, data de
realizacao, aviso de cirurgia, setor) antes de testar o pipeline com
documentos reais.

Uso:
    python scripts/redigir_dados_clinicos.py entrada_real entrada_real_redigida

Le cada PDF da pasta de entrada com o mesmo extrator de texto usado pelo
pipeline (pdf_reader.py), aplica uma redacao baseada em regex sobre os
rotulos de dado clinico conhecidos, e grava uma copia como um novo PDF na
pasta de saida. O PDF gerado nao preserva o layout visual original, apenas
o texto ja redigido - o que basta para testar a extracao dos campos
comerciais (numero da OC, itens, valores) sem que nenhum dado real de
paciente saia da maquina local.

Este script e uma redacao best-effort baseada em padroes de texto, nao uma
garantia formal de anonimizacao. Revise o PDF gerado antes de confiar nele
para qualquer uso alem de teste local.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from pdf_reader import extrair_texto  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

MASCARA = "[DADO CLINICO REMOVIDO]"

# Rotulos conhecidos de dado clinico (mesmos campos de DadosClinicos em
# schema.py). Ordenados do mais longo para o mais curto, para o regex
# preferir a variante mais especifica (ex: "medico cirurgico" antes de um
# rotulo generico que por acaso seja prefixo dele).
RUBROS_CLINICOS = sorted(
    [
        "paciente",
        "convenio",
        "convênio",
        "carteirinha",
        "carteira",
        "cirurgiao",
        "cirurgião",
        "medico cirurgico",
        "médico cirurgico",
        "crm",
        "aviso de cirurgia",
        "aviso cirurgia",
        "data de realizacao",
        "data de realização",
        "dt atend",
        "setor",
    ],
    key=len,
    reverse=True,
)

PADRAO_ROTULO = re.compile(
    r"^(\s*)(" + "|".join(re.escape(r) for r in RUBROS_CLINICOS) + r")(\s*:?\s*)(.*)$",
    re.IGNORECASE,
)


def _redigir_segmento(segmento: str) -> str:
    m = PADRAO_ROTULO.match(segmento)
    if not m:
        return segmento
    prefixo_espacos, rotulo, separador, _valor = m.groups()
    return f"{prefixo_espacos}{rotulo}{separador}{MASCARA}"


def _redigir_linha(linha: str) -> str:
    """Redige uma linha, respeitando os dois estilos de separador vistos nos
    layouts reais: segmentos separados por hifen, e campos separados por
    2+ espacos dentro de um mesmo segmento (sem hifen)."""

    partes_hifen = linha.split("-")
    partes_redigidas = []
    for parte in partes_hifen:
        subpartes = re.split(r"(\s{2,})", parte)
        subpartes_redigidas = [
            _redigir_segmento(sub) if sub.strip() else sub for sub in subpartes
        ]
        partes_redigidas.append("".join(subpartes_redigidas))
    return "-".join(partes_redigidas)


def redigir_texto(texto: str) -> str:
    return "\n".join(_redigir_linha(linha) for linha in texto.splitlines())


def gerar_pdf_redigido(texto_redigido: str, caminho_saida: Path) -> None:
    c = canvas.Canvas(str(caminho_saida), pagesize=letter)
    _, altura = letter
    y = altura - 50
    c.setFont("Helvetica", 8)
    for linha in texto_redigido.splitlines():
        if y < 40:
            c.showPage()
            c.setFont("Helvetica", 8)
            y = altura - 50
        c.drawString(40, y, linha[:120])
        y -= 11
    c.save()


def redigir_pasta(pasta_entrada: Path, pasta_saida: Path) -> None:
    pasta_saida.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(pasta_entrada.glob("*.pdf"))
    if not pdfs:
        print(f"Nenhum PDF encontrado em {pasta_entrada}")
        return

    for caminho_pdf in pdfs:
        extraido = extrair_texto(caminho_pdf)
        texto_redigido = redigir_texto(extraido.texto)
        caminho_saida = pasta_saida / f"redigido_{caminho_pdf.name}"
        gerar_pdf_redigido(texto_redigido, caminho_saida)
        print(f"{caminho_pdf.name} -> {caminho_saida.name}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python scripts/redigir_dados_clinicos.py <pasta_entrada> <pasta_saida>")
        sys.exit(1)

    redigir_pasta(Path(sys.argv[1]), Path(sys.argv[2]))
