"""
Gera PDFs sinteticos de Ordens de Compra (OC) com 4 layouts diferentes,
simulando os formatos reais que a MDR/Mederi recebe de hospitais parceiros.

Todos os dados (hospitais, pacientes, CNPJs, valores) sao FICTICIOS.
Usado apenas para demonstrar que o pipeline de extracao funciona
independente do layout do documento de origem.
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

OUT_DIR = os.path.join(os.path.dirname(__file__), "pdfs")
os.makedirs(OUT_DIR, exist_ok=True)


def layout_hospital_classico(path):
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
    c.drawString(40, y, "CNPJ: 11.222.333/0001-44 | Inscricao Estadual: Isento")

    c.setFont("Helvetica-Bold", 11)
    y -= 20
    c.drawString(40, y, "ORDEM DE COMPRA Nº 481290")
    c.setFont("Helvetica", 8)
    y -= 12
    c.drawString(40, y, "Emitido por: FSANTOS   Em: 12/05/2026 09:42")

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
    rows = [
        ("1", "331200", "1", "UN", "STENT CORONARIO FARMACOLOGICO 3.0X18MM [SC30018X]", "1.450,00", "1.450,00"),
        ("2", "331987", "2", "UN", "CATETER BALAO ANGIOPLASTIA NC 2.5X15MM [CB2515X]", "310,00", "620,00"),
    ]
    for item, cod, qtd, un, desc, vu, vt in rows:
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
    c.drawString(400, y, "Valor Total do Pedido: R$ 2.070,00")
    y -= 14
    c.setFont("Helvetica", 8)
    c.drawString(40, y, "Cond. de Pagamento: 30 DIAS - DATA EMISSAO DA NF")
    c.drawString(300, y, "Frete: CIF")

    y -= 20
    c.setFont("Helvetica-Bold", 8)
    c.drawString(40, y, "Observacao:")
    y -= 12
    c.setFont("Helvetica", 8)
    c.drawString(40, y, "PACIENTE:HELENA CARDOSO MOREIRA-AVISO CIRURGIA:502981-DATA DE REALIZACAO:15/05/2026")
    y -= 10
    c.drawString(40, y, "-CONVENIO:UNIMED FORTALEZA-CARTEIRA:04471002298-CIRURGIAO:PAULO ROBERTO LIMA.")

    c.save()


def layout_totvs_tabela(path):
    """Layout tipo TOTVS 'Pedido de Compra' (tabela larga, ex: REDE D'OR)."""
    c = canvas.Canvas(path, pagesize=letter)
    w, h = letter
    y = h - 40

    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Pedido de Compra P12: 204471")
    c.setFont("Helvetica", 8)
    c.drawString(300, y, "Data Emissao: 05/05/2026   Pg:1")

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
    c.drawString(40, y, "CNPJ/CPF: 55.666.777/0001-88")
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
    rows = [
        ("0001", "18820", "CATETER BALAO DILATACAO NC TREK 3X15MM", "REF;9910-15", "1,0000", "320,00", "320,00"),
        ("0002", "19044", "STENT FARMACOLOGICO XPEDITION 2.75X24MM", "REF;7741-24", "1,0000", "1.600,00", "1.600,00"),
        ("0003", "20315", "INTRODUTOR VASCULAR 6F", "REF;IV-06", "2,0000", "95,00", "190,00"),
    ]
    for item, cod, desc, ref, qtd, vu, vt in rows:
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
    c.drawString(400, y, "Total geral: 2.110,00")
    y -= 12
    c.setFont("Helvetica", 8)
    c.drawString(40, y, "Condicao de pagamento: 30 DIAS")
    y -= 12
    c.drawString(40, y, "Comprador responsavel: Marcia Ferreira Souza")
    y -= 16
    c.setFont("Helvetica-Bold", 8)
    c.drawString(40, y, "Observacoes:")
    y -= 10
    c.setFont("Helvetica", 8)
    c.drawString(40, y, "FATURAR E REPOR, ESTOQUE CONSIGNADO, MDR.")

    c.save()


def layout_mv2000(path):
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
    c.drawString(350, y, "Emitido por: RCASTRO  Em: 20/05/2026 11:15")

    y -= 20
    c.drawString(40, y, "Ord. Compra: 391847     Situacao: AUTORIZADA")
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
    c.drawString(40, y, "77213 CANULA BLOQUEIO NERVOS PERIFERICOS 80MMX20G REF 99213")
    c.drawString(280, y, "UNIDADE")
    c.drawString(340, y, "1,0000")
    c.drawString(390, y, "980,0000")
    c.drawString(460, y, "980,00")

    y -= 24
    c.setFont("Helvetica-Bold", 9)
    c.drawString(400, y, "Valor Total (=): 980,00")

    y -= 20
    c.setFont("Helvetica", 8)
    c.drawString(40, y, "Paciente:Ricardo Nunes Barbosa-Aviso cirurgia:277104-Data de realizacao:19/05/2026 08:30:00-")
    y -= 10
    c.drawString(40, y, "Convenio:Bradesco Saude-Carteira:01198827734-Cirurgiao:Fernanda Albuquerque Dias.")

    c.save()


def layout_samer_gavea(path):
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
    c.drawString(400, y, "Numero    88.104")
    y -= 10
    c.drawString(40, y, "22040-000  Niteroi  RJ")
    c.drawString(400, y, "Data      04/05/2026 14:20")
    y -= 10
    c.drawString(40, y, "CNPJ 44.555.666/0001-77")
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
    c.drawString(40, y, "1     10/05/2026  551034 - CATETER BALAO DILATACAO EUPHORA NC 3.0X20MM")
    y -= 10
    c.drawString(40, y, "                   Lote_Forn 240099   Ref NCEUP3020X   Marca MEDTRONIC")
    c.drawString(330, y, "1,00   un   410,00     410,00")

    y -= 20
    c.setFont("Helvetica-Bold", 8)
    c.drawString(400, y, "Total Geral   410,00")

    y -= 16
    c.setFont("Helvetica", 8)
    c.drawString(40, y, "Condicao de Pgto  30 dias      Tipo Frete  Cif - Frete por conta do Fornecedor")

    y -= 16
    c.setFont("Helvetica-Bold", 8)
    c.drawString(40, y, "Observacao")
    y -= 10
    c.setFont("Helvetica", 8)
    c.drawString(40, y, "FATURAR E REPOR - Paciente: Camila Duarte Rocha")
    y -= 10
    c.drawString(40, y, "Convenio Particular  Medico cirurgico: Tiago Nascimento Rezende  CRM: 552310")
    y -= 10
    c.drawString(40, y, "Dt atend: 04/05/2026 09:00:00  Setor: Hemodinamica")

    c.save()


if __name__ == "__main__":
    layout_hospital_classico(os.path.join(OUT_DIR, "oc_hospital_santa_cecilia_481290.pdf"))
    layout_totvs_tabela(os.path.join(OUT_DIR, "oc_rede_hospital_vita_nova_204471.pdf"))
    layout_mv2000(os.path.join(OUT_DIR, "oc_hospital_boa_esperanca_391847.pdf"))
    layout_samer_gavea(os.path.join(OUT_DIR, "oc_hospitais_reunidos_litoral_88104.pdf"))
    print(f"4 PDFs sinteticos gerados em {OUT_DIR}")
