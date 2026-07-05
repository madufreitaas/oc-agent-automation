"""
Harness de avaliacao da extracao via LLM.

Diferente dos testes em tests/ (que usam um cliente Claude simulado e nunca
chamam a API de verdade), este script roda a extracao real contra os 4 PDFs
sinteticos em demo_data/pdfs/ e compara o resultado, campo a campo, com o
gabarito abaixo - os valores exatos usados para gerar esses PDFs, definidos
em demo_data/generate_demo_pdfs.py.

Serve para responder objetivamente "a extracao esta funcionando direito?",
detectar regressao quando o prompt ou o schema mudam, e comparar a qualidade
entre modelos/provedores diferentes.

Chama a API de verdade a cada execucao (custa tempo e credito), por isso nao
roda junto com a suite de testes automatica (pytest). Uso:

    python scripts/avaliar_extracao.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from llm_extractor import ExtractionError, extrair_ordem_de_compra  # noqa: E402
from pdf_reader import extrair_texto  # noqa: E402

DEMO_PDFS_DIR = Path(__file__).resolve().parent.parent / "demo_data" / "pdfs"


@dataclass
class CampoEsperado:
    caminho: str  # caminho pontuado no objeto OrdemDeCompra, ex: "itens.0.descricao"
    valor: object  # valor esperado (None = espera-se ausencia do campo)
    exato: bool = False  # False: string comparada por substring, case-insensitive


GABARITO: dict[str, list[CampoEsperado]] = {
    "oc_hospital_santa_cecilia_481290.pdf": [
        CampoEsperado("numero_oc", "481290", exato=True),
        CampoEsperado("data_emissao", "2026-05-12", exato=True),
        CampoEsperado("cliente.nome", "santa cecilia"),
        CampoEsperado("fornecedor.nome", "mederi"),
        CampoEsperado("valor_total", 2070.0),
        CampoEsperado("condicao_pagamento_dias", 30, exato=True),
        CampoEsperado("layout_origem", "hospital_classico", exato=True),
        CampoEsperado("itens.0.descricao", "stent coronario"),
        CampoEsperado("itens.0.quantidade", 1.0),
        CampoEsperado("itens.0.valor_total", 1450.0),
        CampoEsperado("itens.1.descricao", "cateter balao angioplastia"),
        CampoEsperado("itens.1.quantidade", 2.0),
        CampoEsperado("itens.1.valor_total", 620.0),
        CampoEsperado("dados_clinicos.paciente", "helena cardoso moreira"),
        CampoEsperado("dados_clinicos.convenio", "unimed fortaleza"),
        CampoEsperado("dados_clinicos.carteirinha", "04471002298", exato=True),
        CampoEsperado("dados_clinicos.cirurgiao", "paulo roberto lima"),
        CampoEsperado("dados_clinicos.aviso_cirurgia", "502981", exato=True),
    ],
    "oc_rede_hospital_vita_nova_204471.pdf": [
        CampoEsperado("numero_oc", "204471", exato=True),
        CampoEsperado("data_emissao", "2026-05-05", exato=True),
        CampoEsperado("cliente.nome", "vita nova"),
        CampoEsperado("fornecedor.nome", "mdr"),
        CampoEsperado("valor_total", 2110.0),
        CampoEsperado("condicao_pagamento_dias", 30, exato=True),
        CampoEsperado("layout_origem", "totvs_tabela", exato=True),
        CampoEsperado("tipo_faturamento", "faturar e repor"),
        CampoEsperado("itens.0.descricao", "cateter balao dilatacao"),
        CampoEsperado("itens.0.valor_total", 320.0),
        CampoEsperado("itens.1.descricao", "stent farmacologico xpedition"),
        CampoEsperado("itens.1.valor_total", 1600.0),
        CampoEsperado("itens.2.descricao", "introdutor vascular"),
        CampoEsperado("itens.2.quantidade", 2.0),
        CampoEsperado("itens.2.valor_total", 190.0),
    ],
    "oc_hospital_boa_esperanca_391847.pdf": [
        CampoEsperado("numero_oc", "391847", exato=True),
        CampoEsperado("data_emissao", "2026-05-20", exato=True),
        CampoEsperado("cliente.nome", "boa esperanca"),
        CampoEsperado("fornecedor.nome", "mdr"),
        CampoEsperado("valor_total", 980.0),
        CampoEsperado("condicao_pagamento_dias", 60, exato=True),
        CampoEsperado("layout_origem", "mv2000", exato=True),
        CampoEsperado("itens.0.descricao", "canula bloqueio nervos perifericos"),
        CampoEsperado("itens.0.valor_total", 980.0),
        CampoEsperado("dados_clinicos.paciente", "ricardo nunes barbosa"),
        CampoEsperado("dados_clinicos.convenio", "bradesco saude"),
        CampoEsperado("dados_clinicos.carteirinha", "01198827734", exato=True),
        CampoEsperado("dados_clinicos.cirurgiao", "fernanda albuquerque dias"),
        CampoEsperado("dados_clinicos.aviso_cirurgia", "277104", exato=True),
    ],
    "oc_hospitais_reunidos_litoral_88104.pdf": [
        CampoEsperado("numero_oc", "88104", exato=True),
        CampoEsperado("data_emissao", "2026-05-04", exato=True),
        CampoEsperado("cliente.nome", "hospitais reunidos do litoral"),
        CampoEsperado("fornecedor.nome", "mederi"),
        CampoEsperado("valor_total", 410.0),
        CampoEsperado("condicao_pagamento_dias", 30, exato=True),
        CampoEsperado("layout_origem", "grade_hospitalar", exato=True),
        CampoEsperado("tipo_faturamento", "faturar e repor"),
        CampoEsperado("itens.0.descricao", "cateter balao dilatacao euphora"),
        CampoEsperado("itens.0.valor_total", 410.0),
        CampoEsperado("dados_clinicos.paciente", "camila duarte rocha"),
        CampoEsperado("dados_clinicos.convenio", "particular"),
        CampoEsperado("dados_clinicos.cirurgiao", "tiago nascimento rezende"),
        CampoEsperado("dados_clinicos.setor", "hemodinamica"),
    ],
}


def _resolver_caminho(objeto, caminho: str):
    valor = objeto
    for parte in caminho.split("."):
        if valor is None:
            return None
        if parte.isdigit():
            indice = int(parte)
            valor = valor[indice] if 0 <= indice < len(valor) else None
        else:
            valor = getattr(valor, parte, None)
    return valor


def _campo_bate(esperado: object, obtido: object, exato: bool) -> bool:
    if esperado is None:
        return obtido is None

    if isinstance(esperado, str):
        if obtido is None:
            return False
        texto_obtido = str(obtido).lower()
        return texto_obtido == esperado.lower() if exato else esperado.lower() in texto_obtido

    if isinstance(esperado, float):
        try:
            return obtido is not None and abs(float(obtido) - esperado) < 0.01
        except (TypeError, ValueError):
            return False

    return obtido == esperado


def avaliar_arquivo(nome_arquivo: str, campos_esperados: list[CampoEsperado]) -> dict:
    caminho_pdf = DEMO_PDFS_DIR / nome_arquivo
    resultado = {"arquivo": nome_arquivo, "erro": None, "acertos": 0, "total": len(campos_esperados), "falhas": []}

    try:
        texto = extrair_texto(caminho_pdf).texto
        oc = extrair_ordem_de_compra(texto, arquivo_origem=nome_arquivo)
    except ExtractionError as exc:
        resultado["erro"] = str(exc)
        return resultado

    for campo in campos_esperados:
        obtido = _resolver_caminho(oc, campo.caminho)
        if _campo_bate(campo.valor, obtido, campo.exato):
            resultado["acertos"] += 1
        else:
            resultado["falhas"].append((campo.caminho, campo.valor, obtido))

    return resultado


def main() -> None:
    load_dotenv()

    from llm_extractor import modelo_configurado  # noqa: E402 (le OPENROUTER_MODEL apos load_dotenv)

    resultados = [avaliar_arquivo(arquivo, campos) for arquivo, campos in GABARITO.items()]

    total_acertos = 0
    total_campos = 0

    print("=" * 70)
    print(f"Modelo avaliado: {modelo_configurado()}")
    for resultado in resultados:
        print(f"\n{resultado['arquivo']}")
        if resultado["erro"]:
            print(f"  ERRO NA EXTRACAO: {resultado['erro']}")
            continue

        acertos, total = resultado["acertos"], resultado["total"]
        total_acertos += acertos
        total_campos += total
        pct = (acertos / total * 100) if total else 0.0
        print(f"  {acertos}/{total} campos corretos ({pct:.0f}%)")
        for caminho, esperado, obtido in resultado["falhas"]:
            print(f"    - {caminho}: esperado={esperado!r} obtido={obtido!r}")

    print("\n" + "=" * 70)
    if total_campos:
        pct_geral = total_acertos / total_campos * 100
        print(f"RESULTADO GERAL: {total_acertos}/{total_campos} campos corretos ({pct_geral:.0f}%)")
    else:
        print("RESULTADO GERAL: nenhum arquivo pode ser avaliado (todas as extracoes falharam).")


if __name__ == "__main__":
    main()
