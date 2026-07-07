import logging
from pathlib import Path

import pytest

import database
import pipeline
from llm_extractor import ExtractionError

# Prefixo reservado para os nomes de arquivo usados por estes testes, para a
# fixture "dsn" conseguir limpar so o log_extracao criado por eles - o banco
# agora e o projeto Supabase demo compartilhado, nao mais um arquivo SQLite
# isolado por teste.
PREFIXO_TESTE = "teste_pipeline_"


class _TextoFalso:
    def __init__(self, texto: str):
        self.texto = texto


def _falha_sempre(texto, arquivo_origem):
    raise ExtractionError("falha simulada")


@pytest.fixture
def dsn():
    valor = database.dsn_demo()
    if not valor:
        pytest.skip("DATABASE_URL_DEMO nao configurada - ver docs/arquitetura_webapp.md")

    yield valor

    conexao = database.conectar(valor)
    conexao.execute("DELETE FROM log_extracao WHERE arquivo LIKE %s", (f"{PREFIXO_TESTE}%",))
    conexao.commit()
    conexao.close()


def test_executar_pipeline_move_para_quarentena_apos_falhas_repetidas(tmp_path: Path, monkeypatch, dsn):
    pasta_entrada = tmp_path / "entrada"
    pasta_entrada.mkdir()
    nome_arquivo = f"{PREFIXO_TESTE}problema.pdf"
    (pasta_entrada / nome_arquivo).write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(pipeline, "LIMITE_FALHAS_QUARENTENA", 2)
    monkeypatch.setattr(pipeline.pdf_reader, "extrair_texto", lambda caminho: _TextoFalso("texto"))
    monkeypatch.setattr(pipeline, "extrair_ordem_de_compra", _falha_sempre)

    pipeline.executar_pipeline(modo="producao", dsn=dsn, pasta_entrada=str(pasta_entrada))
    assert (pasta_entrada / nome_arquivo).exists()  # 1a falha: ainda nao atingiu o limite

    pipeline.executar_pipeline(modo="producao", dsn=dsn, pasta_entrada=str(pasta_entrada))
    assert not (pasta_entrada / nome_arquivo).exists()
    assert (pasta_entrada / "falhas" / nome_arquivo).exists()


def test_executar_pipeline_registra_alerta_com_muitas_falhas(tmp_path: Path, monkeypatch, caplog, dsn):
    pasta_entrada = tmp_path / "entrada"
    pasta_entrada.mkdir()
    for i in range(3):
        (pasta_entrada / f"{PREFIXO_TESTE}arquivo_{i}.pdf").write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(pipeline, "LIMITE_ALERTA_FALHAS", 3)
    monkeypatch.setattr(pipeline, "LIMITE_FALHAS_QUARENTENA", 999)  # nao mover para quarentena neste teste
    monkeypatch.setattr(pipeline.pdf_reader, "extrair_texto", lambda caminho: _TextoFalso("texto"))
    monkeypatch.setattr(pipeline, "extrair_ordem_de_compra", _falha_sempre)

    with caplog.at_level(logging.ERROR, logger="pipeline"):
        pipeline.executar_pipeline(modo="producao", dsn=dsn, pasta_entrada=str(pasta_entrada))

    assert any("ALERTA" in registro.message for registro in caplog.records)


def test_executar_pipeline_sem_muitas_falhas_nao_alerta(tmp_path: Path, monkeypatch, caplog, dsn):
    pasta_entrada = tmp_path / "entrada"
    pasta_entrada.mkdir()
    (pasta_entrada / f"{PREFIXO_TESTE}arquivo_0.pdf").write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(pipeline, "LIMITE_ALERTA_FALHAS", 3)
    monkeypatch.setattr(pipeline.pdf_reader, "extrair_texto", lambda caminho: _TextoFalso("texto"))
    monkeypatch.setattr(pipeline, "extrair_ordem_de_compra", _falha_sempre)

    with caplog.at_level(logging.ERROR, logger="pipeline"):
        pipeline.executar_pipeline(modo="producao", dsn=dsn, pasta_entrada=str(pasta_entrada))

    assert not any("ALERTA" in registro.message for registro in caplog.records)


def test_executar_pipeline_limita_arquivos_por_execucao(tmp_path: Path, monkeypatch, dsn):
    pasta_entrada = tmp_path / "entrada"
    pasta_entrada.mkdir()
    for i in range(5):
        (pasta_entrada / f"{PREFIXO_TESTE}arquivo_{i}.pdf").write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(pipeline, "LIMITE_ARQUIVOS_POR_EXECUCAO", 2)
    monkeypatch.setattr(pipeline.pdf_reader, "extrair_texto", lambda caminho: _TextoFalso("texto"))
    monkeypatch.setattr(pipeline, "extrair_ordem_de_compra", _falha_sempre)

    resumo = pipeline.executar_pipeline(modo="producao", dsn=dsn, pasta_entrada=str(pasta_entrada))

    assert resumo["total"] == 2  # so tentou 2 dos 5 pendentes nesta execucao
    assert len(list(pasta_entrada.glob("*.pdf"))) == 5  # nenhum arquivo falho e movido/apagado

    conn = database.conectar(dsn)
    tentativas = conn.execute(
        "SELECT COUNT(*) AS n FROM log_extracao WHERE arquivo LIKE %s", (f"{PREFIXO_TESTE}%",)
    ).fetchone()["n"]
    assert tentativas == 2  # so 2 arquivos chegaram a ser tentados de verdade
    conn.close()
