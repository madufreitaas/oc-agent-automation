import json
from types import SimpleNamespace

import pytest

import llm_extractor
from llm_extractor import ExtractionError, extrair_ordem_de_compra


def test_limpar_resposta_json_remove_cercas_markdown():
    bruto = '```json\n{"a": 1}\n```'
    assert llm_extractor._limpar_resposta_json(bruto) == '{"a": 1}'


def test_limpar_resposta_json_sem_cercas_mantem_igual():
    bruto = '{"a": 1}'
    assert llm_extractor._limpar_resposta_json(bruto) == '{"a": 1}'


class _FalsaMensagem:
    def __init__(self, texto: str):
        self.content = texto


class _FalsaEscolha:
    def __init__(self, texto: str):
        self.message = _FalsaMensagem(texto)


class _FalsasCompletions:
    def __init__(self, payload: dict):
        self._payload = payload

    def create(self, **kwargs):
        texto = json.dumps(self._payload, ensure_ascii=False)
        return SimpleNamespace(choices=[_FalsaEscolha(texto)])


class _FalsoClient:
    def __init__(self, payload: dict):
        self.chat = SimpleNamespace(completions=_FalsasCompletions(payload))


def _payload_valido() -> dict:
    return {
        "numero_oc": "481290",
        "cliente": {"nome": "Hospital Santa Cecilia"},
        "fornecedor": {"nome": "Mederi Distribuicao"},
        "itens": [],
        "layout_origem": "hospital_classico",
    }


def test_extrair_ordem_de_compra_com_resposta_valida(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "chave-fake")
    monkeypatch.setattr(llm_extractor, "_client", lambda: _FalsoClient(_payload_valido()))

    oc = extrair_ordem_de_compra("texto qualquer da OC", arquivo_origem="arq.pdf")

    assert oc.numero_oc == "481290"
    assert oc.arquivo_origem == "arq.pdf"


def test_extrair_ordem_de_compra_json_invalido_levanta_erro(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "chave-fake")

    class _ClienteRespostaQuebrada(_FalsoClient):
        def __init__(self):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kw: SimpleNamespace(
                        choices=[_FalsaEscolha("isso nao e json")]
                    )
                )
            )

    monkeypatch.setattr(llm_extractor, "_client", lambda: _ClienteRespostaQuebrada())

    with pytest.raises(ExtractionError):
        extrair_ordem_de_compra("texto qualquer", arquivo_origem="arq.pdf")


def test_extrair_ordem_de_compra_schema_invalido_levanta_erro(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "chave-fake")
    payload_invalido = {"cliente": {"nome": "X"}}  # falta numero_oc e fornecedor
    monkeypatch.setattr(llm_extractor, "_client", lambda: _FalsoClient(payload_invalido))

    with pytest.raises(ExtractionError):
        extrair_ordem_de_compra("texto qualquer", arquivo_origem="arq.pdf")


def test_client_sem_api_key_levanta_erro(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ExtractionError):
        llm_extractor._client()


def _erro_conexao():
    from openai import APIConnectionError

    return APIConnectionError(request=SimpleNamespace())


def test_retry_com_backoff_sucede_apos_falhas_transitorias(monkeypatch):
    monkeypatch.setattr(llm_extractor.time, "sleep", lambda segundos: None)

    chamadas = {"n": 0}

    def func():
        chamadas["n"] += 1
        if chamadas["n"] < 3:
            raise _erro_conexao()
        return "sucesso"

    resultado = llm_extractor._retry_com_backoff(func)

    assert resultado == "sucesso"
    assert chamadas["n"] == 3


def test_retry_com_backoff_esgota_tentativas_e_relanca(monkeypatch):
    monkeypatch.setattr(llm_extractor.time, "sleep", lambda segundos: None)

    chamadas = {"n": 0}

    def func():
        chamadas["n"] += 1
        raise _erro_conexao()

    with pytest.raises(Exception):
        llm_extractor._retry_com_backoff(func, tentativas=3)

    assert chamadas["n"] == 3


def test_retry_com_backoff_nao_retenta_erro_nao_transitorio(monkeypatch):
    monkeypatch.setattr(llm_extractor.time, "sleep", lambda segundos: None)

    chamadas = {"n": 0}

    def func():
        chamadas["n"] += 1
        raise ValueError("erro que nao deveria ser retentado")

    with pytest.raises(ValueError):
        llm_extractor._retry_com_backoff(func)

    assert chamadas["n"] == 1
