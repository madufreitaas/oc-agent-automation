import pytest
from pydantic import ValidationError

from schema import Cliente, DadosClinicos, Fornecedor, ItemOC, LayoutOrigem, OrdemDeCompra


def test_ordem_de_compra_minima_valida():
    oc = OrdemDeCompra(
        numero_oc="481290",
        cliente=Cliente(nome="Hospital Santa Cecilia"),
        fornecedor=Fornecedor(nome="Mederi Distribuicao"),
    )
    assert oc.numero_oc == "481290"
    assert oc.itens == []
    assert oc.layout_origem == LayoutOrigem.DESCONHECIDO


def test_ordem_de_compra_completa():
    oc = OrdemDeCompra(
        numero_oc="204471",
        data_emissao="2026-05-05",
        cliente=Cliente(nome="Hospital Vita Nova", cnpj="55.666.777/0001-88", cidade="Sao Paulo", uf="SP"),
        fornecedor=Fornecedor(nome="MDR Distribuicao", cnpj="29.329.985/0007-70"),
        itens=[
            ItemOC(
                codigo_produto="18820",
                descricao="Cateter balao dilatacao NC Trek 3x15mm",
                quantidade=1,
                unidade="UN",
                valor_unitario=320.0,
                valor_total=320.0,
            )
        ],
        condicao_pagamento_dias=30,
        valor_frete=0.0,
        valor_total=320.0,
        tipo_faturamento="FATURAR E REPOR",
        dados_clinicos=DadosClinicos(paciente="Fulano de Tal", convenio="Unimed"),
        layout_origem=LayoutOrigem.TOTVS_TABELA,
        confianca_extracao=0.95,
    )
    assert len(oc.itens) == 1
    assert oc.dados_clinicos.paciente == "Fulano de Tal"
    assert oc.tipo_faturamento == "FATURAR E REPOR"


def test_tipo_faturamento_e_opcional():
    oc = OrdemDeCompra(
        numero_oc="1",
        cliente=Cliente(nome="X"),
        fornecedor=Fornecedor(nome="Y"),
    )
    assert oc.tipo_faturamento is None


def test_confianca_extracao_fora_do_intervalo_falha():
    with pytest.raises(ValidationError):
        OrdemDeCompra(
            numero_oc="1",
            cliente=Cliente(nome="X"),
            fornecedor=Fornecedor(nome="Y"),
            confianca_extracao=1.5,
        )


def test_item_sem_descricao_falha():
    with pytest.raises(ValidationError):
        ItemOC(quantidade=1, valor_unitario=10.0, valor_total=10.0)
