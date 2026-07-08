"""
Gera PDFs sinteticos de Ordens de Compra (OC) com 4 layouts diferentes,
simulando os formatos reais que a MDR/Mederi recebe de hospitais parceiros.

Todos os dados (hospitais, pacientes, CNPJs, valores) sao FICTICIOS.
Usado apenas para demonstrar que o pipeline de extracao funciona
independente do layout do documento de origem.

Os CNPJs dos hospitais sao ficticios mas com digito verificador VALIDO (ver
validadores.cnpj_valido) em 3 dos 4 layouts - de proposito, para o alerta
"CNPJ invalido" (sql/queries/cnpj_invalido.sql) nao acender pra praticamente
toda OC gerada, o que aconteceu quando o volume de PDFs cresceu com --extra.
O CNPJ do Hospital Boa Esperanca (layout_mv2000) continua invalido de
proposito, para o alerta continuar tendo pelo menos um caso real pra mostrar.

Rodado sem argumentos, gera so os 4 PDFs base de sempre (mesmo nome/conteudo
de sempre - tests/test_pdf_reader.py depende disso). Para testar o pipeline
com mais volume, `--extra N` gera N PDFs adicionais reaproveitando os mesmos
4 layouts (variando numero de OC, data e itens); `--duplicatas K` faz K
desses extras repetirem numero_oc+hospital de um PDF ja gerado (base ou
extra), de proposito, para verificar se o gatilho de "possivel_duplicata"
aciona (ver database.py:_marcar_possiveis_duplicatas - duas ordens_compra
com mesmo numero_oc e cliente, em arquivos diferentes):

    python demo_data/generate_demo_pdfs.py --extra 35 --duplicatas 6
"""

import argparse
import os
import random

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT_DIR = os.path.join(os.path.dirname(__file__), "pdfs")
os.makedirs(OUT_DIR, exist_ok=True)


def layout_hospital_classico(
    path,
    numero_oc="481290",
    data_emissao="12/05/2026 09:42",
    itens=(("1", "331200", "1", "UN", "STENT CORONARIO FARMACOLOGICO 3.0X18MM [SC30018X]", "1.450,00", "1.450,00"),
           ("2", "331987", "2", "UN", "CATETER BALAO ANGIOPLASTIA NC 2.5X15MM [CB2515X]", "310,00", "620,00")),
    valor_total="2.070,00",
    paciente="HELENA CARDOSO MOREIRA",
    aviso_cirurgia="502981",
    data_cirurgia="15/05/2026",
    convenio="UNIMED FORTALEZA",
    carteira="04471002298",
    cirurgiao="PAULO ROBERTO LIMA",
):
    """Layout tipo 'Hospital X - Ordem de Compra' (ex: HOSPITAL SAO RAFAEL)."""
    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter
    y = h - 50

    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "HOSPITAL SANTA CECILIA")
    c.setFont("Helvetica", 8)
    y -= 12
    c.drawString(40, y, "AVENIDA DAS FLORES, 900 - CENTRO - FORTALEZA - CEARA")
    y -= 10
    c.drawString(40, y, "CEP 60000-000 | Tel.: 85 3200-0000")
    y -= 10
    c.drawString(40, y, "CNPJ: 11.222.333/0001-81 | Inscricao Estadual: Isento")

    c.setFont("Helvetica-Bold", 11)
    y -= 20
    c.drawString(40, y, f"ORDEM DE COMPRA Nº {numero_oc}")
    c.setFont("Helvetica", 8)
    y -= 12
    c.drawString(40, y, f"Emitido por: FSANTOS   Em: {data_emissao}")

    y -= 20
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, y, "FORNECEDOR")
    c.setFont("Helvetica", 8)
    y -= 12
    c.drawString(40, y, "Nome: 43305 - MEDERI DISTRIBUICAO E IMPORTACAO DE PRODUTOS PARA SAUDE SA")
    y -= 10
    c.drawString(40, y, "CNPJ: 29.329.985/0006-90   Inscricao Estadual: 623292003118")
    y -= 10
    c.drawString(40, y, "Endereco: Rua Parana, s/n - Santana de Parnaiba - SP - CEP 06530-025")

    y -= 20
    c.setFont("Helvetica-Bold", 8)
    headers = ["Item", "Codigo", "Qtd", "UN", "Descricao", "Vl Unit", "Vl Total"]
    xs = [40, 75, 115, 140, 165, 400, 460]
    for x, htxt in zip(xs, headers):
        c.drawString(x, y, htxt)
    y -= 4
    c.line(40, y, 540, y)
    y -= 12
    c.setFont("Helvetica", 8)
    for item, cod, qtd, un, desc, vu, vt in itens:
        c.drawString(40, y, item)
        c.drawString(75, y, cod)
        c.drawString(115, y, qtd)
        c.drawString(140, y, un)
        c.drawString(165, y, desc[:48])
        c.drawString(400, y, vu)
        c.drawString(460, y, vt)
        y -= 14

    y -= 10
    c.line(40, y, 540, y)
    y -= 16
    c.setFont("Helvetica-Bold", 9)
    c.drawString(400, y, f"Valor Total do Pedido: R$ {valor_total}")
    y -= 14
    c.setFont("Helvetica", 8)
    c.drawString(40, y, "Cond. de Pagamento: 30 DIAS - DATA EMISSAO DA NF")
    c.drawString(300, y, "Frete: CIF")

    y -= 20
    c.setFont("Helvetica-Bold", 8)
    c.drawString(40, y, "Observacao:")
    y -= 12
    c.setFont("Helvetica", 8)
    c.drawString(40, y, f"PACIENTE:{paciente}-AVISO CIRURGIA:{aviso_cirurgia}-DATA DE REALIZACAO:{data_cirurgia}")
    y -= 10
    c.drawString(40, y, f"-CONVENIO:{convenio}-CARTEIRA:{carteira}-CIRURGIAO:{cirurgiao}.")

    c.save()


def layout_totvs_tabela(
    path,
    numero_oc="204471",
    data_emissao="05/05/2026",
    itens=(("0001", "18820", "CATETER BALAO DILATACAO NC TREK 3X15MM", "REF;9910-15", "1,0000", "320,00", "320,00"),
           ("0002", "19044", "STENT FARMACOLOGICO XPEDITION 2.75X24MM", "REF;7741-24", "1,0000", "1.600,00", "1.600,00"),
           ("0003", "20315", "INTRODUTOR VASCULAR 6F", "REF;IV-06", "2,0000", "95,00", "190,00")),
    valor_total="2.110,00",
    comprador="Marcia Ferreira Souza",
):
    """Layout tipo TOTVS 'Pedido de Compra' (tabela larga, ex: REDE D'OR)."""
    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter
    y = h - 40

    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, f"Pedido de Compra P12: {numero_oc}")
    c.setFont("Helvetica", 8)
    c.drawString(300, y, f"Data Emissao: {data_emissao}   Pg:1")

    y -= 20
    c.setFont("Helvetica", 8)
    c.drawString(40, y, "Empresa: HOSPITAL VITA NOVA S.A.")
    c.drawString(300, y, "Razao Social: MDR DISTRIB E IMPORT DE PROD PARA A SAUDE SA")
    y -= 10
    c.drawString(40, y, "Endereco: AV. CENTRAL, 1200")
    c.drawString(300, y, "Endereco: Estrada dos Orquidofilos, 1981")
    y -= 10
    c.drawString(40, y, "CEP: 04100000  Cidade: SAO PAULO")
    c.drawString(300, y, "CNPJ/CPF: 29.329.985/0007-70")
    y -= 10
    c.drawString(40, y, "CNPJ/CPF: 55.666.777/0001-81")
    c.drawString(300, y, "Email: vendadireta@mdrsaude.com.br")

    y -= 24
    c.setFont("Helvetica-Bold", 7)
    headers = ["Item", "Produto", "Descricao", "Referencia", "Qtd", "Vl Unit", "Vl Total"]
    xs = [40, 70, 110, 300, 380, 420, 480]
    for x, htxt in zip(xs, headers):
        c.drawString(x, y, htxt)
    y -= 4
    c.line(40, y, 545, y)
    y -= 12
    c.setFont("Helvetica", 7)
    for item, cod, desc, ref, qtd, vu, vt in itens:
        c.drawString(40, y, item)
        c.drawString(70, y, cod)
        c.drawString(110, y, desc[:42])
        c.drawString(300, y, ref)
        c.drawString(380, y, qtd)
        c.drawString(420, y, vu)
        c.drawString(480, y, vt)
        y -= 12

    y -= 16
    c.setFont("Helvetica-Bold", 8)
    c.drawString(400, y, f"Total geral: {valor_total}")
    y -= 12
    c.setFont("Helvetica", 8)
    c.drawString(40, y, "Condicao de pagamento: 30 DIAS")
    y -= 12
    c.drawString(40, y, f"Comprador responsavel: {comprador}")
    y -= 16
    c.setFont("Helvetica-Bold", 8)
    c.drawString(40, y, "Observacoes:")
    y -= 10
    c.setFont("Helvetica", 8)
    c.drawString(40, y, "FATURAR E REPOR, ESTOQUE CONSIGNADO, MDR.")

    c.save()


def layout_mv2000(
    path,
    numero_oc="391847",
    data_emissao="20/05/2026 11:15",
    item_desc="77213 CANULA BLOQUEIO NERVOS PERIFERICOS 80MMX20G REF 99213",
    valor_unit="980,0000",
    valor_total="980,00",
    paciente="Ricardo Nunes Barbosa",
    aviso_cirurgia="277104",
    data_cirurgia="19/05/2026 08:30:00",
    convenio="Bradesco Saude",
    carteira="01198827734",
    cirurgiao="Fernanda Albuquerque Dias",
):
    """Layout tipo sistema hospitalar MV2000 'Relatorio de Ordem de Compra'."""
    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter
    y = h - 40

    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "MV 2000 - SISTEMA DE COMPRAS")
    y -= 12
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "HOSPITAL BOA ESPERANCA S/A")
    y -= 12
    c.setFont("Helvetica", 8)
    c.drawString(40, y, "Relatorio de Ordem de Compra")
    c.drawString(350, y, f"Emitido por: RCASTRO  Em: {data_emissao}")

    y -= 20
    c.drawString(40, y, f"Ord. Compra: {numero_oc}     Situacao: AUTORIZADA")
    y -= 12
    c.drawString(40, y, "Comprador: HOSPITAL BOA ESPERANCA S/A")
    y -= 10
    c.drawString(40, y, "CNPJ: 66.777.888/0001-22   Cidade: BELO HORIZONTE   UF: MG")
    y -= 10
    c.drawString(40, y, "Cod. Condicao de Pgto: 60 DIAS")

    y -= 20
    c.drawString(40, y, "Fornecedor: MDR - MDR DISTRIBUICAO E IMPORTACAO DE PRODUTO")
    y -= 10
    c.drawString(40, y, "CNPJ/CPF: 29.329.985/0007-70   Insc Est.: Isento")
    y -= 10
    c.drawString(40, y, "Endereco: ORQUIDOFILOS DE 1593 A 2477 - AGUA ESPRAIADA - EMBU DAS ARTES - SP")

    y -= 22
    c.setFont("Helvetica-Bold", 8)
    c.drawString(40, y, "Produto")
    c.drawString(280, y, "Unidade")
    c.drawString(340, y, "Qtd")
    c.drawString(390, y, "Vl.Unit.")
    c.drawString(460, y, "Vl Total")
    y -= 4
    c.line(40, y, 540, y)
    y -= 14
    c.setFont("Helvetica", 8)
    c.drawString(40, y, item_desc)
    c.drawString(280, y, "UNIDADE")
    c.drawString(340, y, "1,0000")
    c.drawString(390, y, valor_unit)
    c.drawString(460, y, valor_total)

    y -= 24
    c.setFont("Helvetica-Bold", 9)
    c.drawString(400, y, f"Valor Total (=): {valor_total}")

    y -= 20
    c.setFont("Helvetica", 8)
    c.drawString(40, y, f"Paciente:{paciente}-Aviso cirurgia:{aviso_cirurgia}-Data de realizacao:{data_cirurgia}-")
    y -= 10
    c.drawString(40, y, f"Convenio:{convenio}-Carteira:{carteira}-Cirurgiao:{cirurgiao}.")

    c.save()


def layout_samer_gavea(
    path,
    numero_oc="88.104",
    data_emissao="04/05/2026 14:20",
    item_desc="1     10/05/2026  551034 - CATETER BALAO DILATACAO EUPHORA NC 3.0X20MM",
    item_linha2="                   Lote_Forn 240099   Ref NCEUP3020X   Marca MEDTRONIC",
    item_valores="1,00   un   410,00     410,00",
    valor_total="410,00",
    paciente="Camila Duarte Rocha",
    cirurgiao="Tiago Nascimento Rezende",
    crm="552310",
    data_atendimento="04/05/2026 09:00:00",
):
    """Layout tipo hospital com grade de bordas simples (ex: SAMER / Hosp. Integrados)."""
    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter
    y = h - 40

    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Hospitais Reunidos do Litoral Sa")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(400, y, "Ordem de Compra")
    y -= 12
    c.setFont("Helvetica", 8)
    c.drawString(40, y, "Rua das Palmeiras, 88 - Bairro Centro")
    c.drawString(400, y, f"Numero    {numero_oc}")
    y -= 10
    c.drawString(40, y, "22040-000  Niteroi  RJ")
    c.drawString(400, y, f"Data      {data_emissao}")
    y -= 10
    c.drawString(40, y, "CNPJ 44.555.666/0001-81")
    c.drawString(400, y, "Comprador Comprador TOTVS")

    y -= 20
    c.drawString(40, y, "Fornecedor MEDERI DISTRIBUICAO E IMPORTACAO DE PRODUTOS PARA SAUDE SA")
    y -= 10
    c.drawString(40, y, "Endereco Rua Parana   Cidade Santana de Parnaiba  CEP 06530025  UF SP")
    y -= 10
    c.drawString(40, y, "CNPJ/CPF 29.329.985/0006-90")

    y -= 20
    c.setFont("Helvetica-Bold", 8)
    c.drawString(40, y, "Item  Entrega     Cod.-Descricao")
    c.drawString(330, y, "Qtde   UM   Vl.Unit.   Vl.Total")
    y -= 4
    c.line(40, y, 540, y)
    y -= 14
    c.setFont("Helvetica", 8)
    c.drawString(40, y, item_desc)
    y -= 10
    c.drawString(40, y, item_linha2)
    c.drawString(330, y, item_valores)

    y -= 20
    c.setFont("Helvetica-Bold", 8)
    c.drawString(400, y, f"Total Geral   {valor_total}")

    y -= 16
    c.setFont("Helvetica", 8)
    c.drawString(40, y, "Condicao de Pgto  30 dias      Tipo Frete  Cif - Frete por conta do Fornecedor")

    y -= 16
    c.setFont("Helvetica-Bold", 8)
    c.drawString(40, y, "Observacao")
    y -= 10
    c.setFont("Helvetica", 8)
    c.drawString(40, y, f"FATURAR E REPOR - Paciente: {paciente}")
    y -= 10
    c.drawString(40, y, f"Convenio Particular  Medico cirurgico: {cirurgiao}  CRM: {crm}")
    y -= 10
    c.drawString(40, y, f"Dt atend: {data_atendimento}  Setor: Hemodinamica")

    c.save()


def gerar_pdfs_base():
    layout_hospital_classico(os.path.join(OUT_DIR, "oc_hospital_santa_cecilia_481290.pdf"))
    layout_totvs_tabela(os.path.join(OUT_DIR, "oc_rede_hospital_vita_nova_204471.pdf"))
    layout_mv2000(os.path.join(OUT_DIR, "oc_hospital_boa_esperanca_391847.pdf"))
    layout_samer_gavea(os.path.join(OUT_DIR, "oc_hospitais_reunidos_litoral_88104.pdf"))
    print(f"4 PDFs sinteticos base gerados em {OUT_DIR}")


# Pool de itens extras por layout (mesmo estilo/produtos dos originais - so
# para dar variedade de descricao/valor aos PDFs extras), alem dos itens ja
# usados nas 4 funcoes acima.
_ITENS_HOSPITAL_CLASSICO = [
    ("1", "331200", "1", "UN", "STENT CORONARIO FARMACOLOGICO 3.0X18MM [SC30018X]", "1.450,00", "1.450,00"),
    ("2", "331987", "2", "UN", "CATETER BALAO ANGIOPLASTIA NC 2.5X15MM [CB2515X]", "310,00", "620,00"),
    ("3", "331512", "1", "UN", "FIO GUIA CORONARIO 0.014 190CM [FG014190]", "480,00", "480,00"),
    ("4", "332004", "3", "UN", "INTRODUTOR VASCULAR 6F [IV06F]", "95,00", "285,00"),
]
_ITENS_TOTVS = [
    ("0001", "18820", "CATETER BALAO DILATACAO NC TREK 3X15MM", "REF;9910-15", "1,0000", "320,00", "320,00"),
    ("0002", "19044", "STENT FARMACOLOGICO XPEDITION 2.75X24MM", "REF;7741-24", "1,0000", "1.600,00", "1.600,00"),
    ("0003", "20315", "INTRODUTOR VASCULAR 6F", "REF;IV-06", "2,0000", "95,00", "190,00"),
    ("0004", "21187", "FIO GUIA HIDROFILICO 0.035 150CM", "REF;FG035150", "1,0000", "540,00", "540,00"),
]
_ITENS_MV2000 = [
    ("77213 CANULA BLOQUEIO NERVOS PERIFERICOS 80MMX20G REF 99213", "980,0000", "980,00"),
    ("77340 STENT CORONARIO CONVENCIONAL 2.75X13MM REF 99340", "1.180,0000", "1.180,00"),
    ("77455 CATETER BALAO EUPHORA NC 2.5X12MM REF 99455", "395,0000", "395,00"),
]
_PACIENTES = [
    ("HELENA CARDOSO MOREIRA", "PAULO ROBERTO LIMA", "UNIMED FORTALEZA"),
    ("RICARDO NUNES BARBOSA", "FERNANDA ALBUQUERQUE DIAS", "BRADESCO SAUDE"),
    ("CAMILA DUARTE ROCHA", "TIAGO NASCIMENTO REZENDE", "PARTICULAR"),
    ("MARCOS VINICIUS TEIXEIRA", "ANA BEATRIZ MONTEIRO", "SUL AMERICA"),
    ("LUCIANA APARECIDA GOMES", "RODRIGO CESAR FARIAS", "AMIL"),
    ("EDUARDO HENRIQUE SOARES", "PATRICIA REGINA COSTA", "NOTREDAME INTERMEDICA"),
]

_LAYOUTS = [
    ("classico", layout_hospital_classico, _ITENS_HOSPITAL_CLASSICO),
    ("totvs", layout_totvs_tabela, _ITENS_TOTVS),
    ("mv2000", layout_mv2000, _ITENS_MV2000),
    ("samer", layout_samer_gavea, None),
]


def _numero_oc_para(layout_nome, sequencia, rng):
    base = {"classico": 481000, "totvs": 204000, "mv2000": 391000, "samer": 88000}[layout_nome]
    return str(base + sequencia)


def _gerar_um_extra(layout_nome, funcao, itens_pool, sequencia, rng, forcar_numero_oc=None):
    """Gera um unico PDF extra do layout dado, com dados variados (ou
    identicos a um numero_oc anterior, se forcar_numero_oc for passado - usado
    para criar duplicatas de proposito)."""

    numero_oc = forcar_numero_oc or _numero_oc_para(layout_nome, sequencia, rng)
    dia = rng.randint(1, 28)
    mes = rng.randint(1, 12)
    hora, minuto = rng.randint(7, 18), rng.randint(0, 59)
    data_emissao_completa = f"{dia:02d}/{mes:02d}/2026 {hora:02d}:{minuto:02d}"
    data_emissao_simples = f"{dia:02d}/{mes:02d}/2026"
    paciente, cirurgiao, convenio = rng.choice(_PACIENTES)
    aviso_cirurgia = str(rng.randint(100000, 999999))
    carteira = str(rng.randint(10000000000, 99999999999))
    crm = str(rng.randint(100000, 999999))

    path = os.path.join(OUT_DIR, f"oc_extra_{layout_nome}_{numero_oc}_{sequencia:03d}.pdf")

    if layout_nome == "classico":
        itens = rng.sample(itens_pool, k=rng.randint(1, 2))
        total = sum(float(it[6].replace(".", "").replace(",", ".")) for it in itens)
        funcao(
            path, numero_oc=numero_oc, data_emissao=data_emissao_completa, itens=itens,
            valor_total=f"{total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            paciente=paciente, aviso_cirurgia=aviso_cirurgia, data_cirurgia=data_emissao_simples,
            convenio=convenio, carteira=carteira, cirurgiao=cirurgiao,
        )
    elif layout_nome == "totvs":
        itens = rng.sample(itens_pool, k=rng.randint(1, 3))
        total = sum(float(it[6].replace(".", "").replace(",", ".")) for it in itens)
        funcao(
            path, numero_oc=numero_oc, data_emissao=data_emissao_simples, itens=itens,
            valor_total=f"{total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            comprador=cirurgiao,
        )
    elif layout_nome == "mv2000":
        desc, vu, vt = rng.choice(itens_pool)
        funcao(
            path, numero_oc=numero_oc, data_emissao=data_emissao_completa, item_desc=desc,
            valor_unit=vu, valor_total=vt, paciente=paciente, aviso_cirurgia=aviso_cirurgia,
            data_cirurgia=data_emissao_completa, convenio=convenio, carteira=carteira, cirurgiao=cirurgiao,
        )
    else:  # samer
        funcao(
            path, numero_oc=numero_oc, data_emissao=data_emissao_completa, paciente=paciente,
            cirurgiao=cirurgiao, crm=crm, data_atendimento=data_emissao_completa,
        )

    return numero_oc, os.path.basename(path)


def gerar_pdfs_extra(quantidade_extra: int, quantidade_duplicatas: int, seed: int = 42):
    """Gera `quantidade_extra` PDFs adicionais (mesmos 4 layouts, dados
    variados) para testar o pipeline com mais volume. `quantidade_duplicatas`
    desses extras reusam numero_oc+layout(=mesmo cliente) de um PDF ja gerado
    nesta rodada, de proposito, para exercitar o gatilho de duplicidade."""

    if quantidade_duplicatas > quantidade_extra:
        raise ValueError("quantidade_duplicatas nao pode ser maior que quantidade_extra")

    rng = random.Random(seed)
    gerados = []  # (layout_nome, numero_oc) dos PDFs desta rodada, para sortear duplicatas depois

    n_unicos = quantidade_extra - quantidade_duplicatas
    for i in range(n_unicos):
        layout_nome, funcao, itens_pool = _LAYOUTS[i % len(_LAYOUTS)]
        numero_oc, nome_arquivo = _gerar_um_extra(layout_nome, funcao, itens_pool, sequencia=i + 1, rng=rng)
        gerados.append((layout_nome, numero_oc))
        print(f"  extra {i + 1}/{quantidade_extra}: {nome_arquivo}")

    for j in range(quantidade_duplicatas):
        layout_nome, numero_oc_repetido = rng.choice(gerados)
        funcao = next(f for nome, f, _ in _LAYOUTS if nome == layout_nome)
        itens_pool = next(pool for nome, _, pool in _LAYOUTS if nome == layout_nome)
        sequencia = n_unicos + j + 1
        _, nome_arquivo = _gerar_um_extra(
            layout_nome, funcao, itens_pool, sequencia=sequencia, rng=rng, forcar_numero_oc=numero_oc_repetido,
        )
        print(f"  duplicata {j + 1}/{quantidade_duplicatas}: {nome_arquivo} (numero_oc {numero_oc_repetido} repetido)")

    print(
        f"{quantidade_extra} PDFs extras gerados em {OUT_DIR} "
        f"({quantidade_duplicatas} de proposito duplicados - devem cair em 'Central de alertas' apos o pipeline rodar)."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--extra", type=int, default=0, help="Quantidade de PDFs extras a gerar (alem dos 4 base).")
    parser.add_argument(
        "--duplicatas", type=int, default=0,
        help="Quantos dos --extra devem repetir numero_oc+cliente de outro PDF (para testar o alerta de duplicidade).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Semente do gerador aleatorio (reprodutibilidade).")
    args = parser.parse_args()

    gerar_pdfs_base()
    if args.extra > 0:
        gerar_pdfs_extra(args.extra, args.duplicatas, seed=args.seed)
