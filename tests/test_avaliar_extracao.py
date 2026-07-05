import avaliar_extracao
from avaliar_extracao import CampoEsperado, _campo_bate, _resolver_caminho, avaliar_arquivo
from llm_extractor import ExtractionError
from schema import Cliente, DadosClinicos, Fornecedor, ItemOC, OrdemDeCompra


def _oc_exemplo() -> OrdemDeCompra:
    return OrdemDeCompra(
        numero_oc="481290",
        cliente=Cliente(nome="Hospital Santa Cecilia"),
        fornecedor=Fornecedor(nome="Mederi Distribuicao"),
        itens=[
            ItemOC(descricao="Stent coronario 3.0x18mm", quantidade=1, valor_unitario=1450.0, valor_total=1450.0)
        ],
        valor_total=2070.0,
        dados_clinicos=DadosClinicos(paciente="Helena Cardoso Moreira"),
    )


def test_resolver_caminho_atributo_simples():
    oc = _oc_exemplo()
    assert _resolver_caminho(oc, "numero_oc") == "481290"
    assert _resolver_caminho(oc, "cliente.nome") == "Hospital Santa Cecilia"


def test_resolver_caminho_lista_indice():
    oc = _oc_exemplo()
    assert _resolver_caminho(oc, "itens.0.descricao") == "Stent coronario 3.0x18mm"


def test_resolver_caminho_indice_fora_do_alcance_retorna_none():
    oc = _oc_exemplo()
    assert _resolver_caminho(oc, "itens.5.descricao") is None


def test_resolver_caminho_atributo_ausente_retorna_none():
    oc = _oc_exemplo()
    oc.dados_clinicos = None
    assert _resolver_caminho(oc, "dados_clinicos.paciente") is None


def test_campo_bate_string_substring():
    assert _campo_bate("santa cecilia", "Hospital Santa Cecilia", exato=False) is True
    assert _campo_bate("outro hospital", "Hospital Santa Cecilia", exato=False) is False


def test_campo_bate_string_exato():
    assert _campo_bate("481290", "481290", exato=True) is True
    assert _campo_bate("481290", "4812900", exato=True) is False


def test_campo_bate_float_tolerancia():
    assert _campo_bate(2070.0, 2070.001, exato=False) is True
    assert _campo_bate(2070.0, 2071.0, exato=False) is False


def test_campo_bate_none_espera_ausencia():
    assert _campo_bate(None, None, exato=False) is True
    assert _campo_bate(None, "algo", exato=False) is False


def test_avaliar_arquivo_conta_acertos_e_falhas(monkeypatch):
    monkeypatch.setattr(avaliar_extracao, "extrair_texto", lambda caminho: type("T", (), {"texto": "texto"})())
    monkeypatch.setattr(avaliar_extracao, "extrair_ordem_de_compra", lambda texto, arquivo_origem: _oc_exemplo())

    campos = [
        CampoEsperado("numero_oc", "481290", exato=True),
        CampoEsperado("valor_total", 9999.0),  # propositalmente errado
    ]

    resultado = avaliar_arquivo("arquivo.pdf", campos)

    assert resultado["erro"] is None
    assert resultado["acertos"] == 1
    assert resultado["total"] == 2
    assert resultado["falhas"] == [("valor_total", 9999.0, 2070.0)]


def test_avaliar_arquivo_erro_extracao_reportado(monkeypatch):
    monkeypatch.setattr(avaliar_extracao, "extrair_texto", lambda caminho: type("T", (), {"texto": "texto"})())

    def _levanta_erro(texto, arquivo_origem):
        raise ExtractionError("falha simulada")

    monkeypatch.setattr(avaliar_extracao, "extrair_ordem_de_compra", _levanta_erro)

    resultado = avaliar_arquivo("arquivo.pdf", [CampoEsperado("numero_oc", "481290", exato=True)])

    assert resultado["erro"] == "falha simulada"
    assert resultado["acertos"] == 0
