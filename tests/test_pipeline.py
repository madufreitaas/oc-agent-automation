import logging
from pathlib import Path

import database
import pipeline
from llm_extractor import ExtractionError


class _TextoFalso:
    def __init__(self, texto: str):
        self.texto = texto


def _falha_sempre(texto, arquivo_origem):
    raise ExtractionError("falha simulada")


def test_executar_pipeline_move_para_quarentena_apos_falhas_repetidas(tmp_path: Path, monkeypatch):
    pasta_entrada = tmp_path / "entrada"
    pasta_entrada.mkdir()
    (pasta_entrada / "problema.pdf").write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(pipeline, "LIMITE_FALHAS_QUARENTENA", 2)
    monkeypatch.setattr(pipeline.pdf_reader, "extrair_texto", lambda caminho: _TextoFalso("texto"))
    monkeypatch.setattr(pipeline, "extrair_ordem_de_compra", _falha_sempre)

    db_path = tmp_path / "teste.db"

    pipeline.executar_pipeline(modo="producao", db_path=db_path, pasta_entrada=str(pasta_entrada))
    assert (pasta_entrada / "problema.pdf").exists()  # 1a falha: ainda nao atingiu o limite

    pipeline.executar_pipeline(modo="producao", db_path=db_path, pasta_entrada=str(pasta_entrada))
    assert not (pasta_entrada / "problema.pdf").exists()
    assert (pasta_entrada / "falhas" / "problema.pdf").exists()


def test_executar_pipeline_registra_alerta_com_muitas_falhas(tmp_path: Path, monkeypatch, caplog):
    pasta_entrada = tmp_path / "entrada"
    pasta_entrada.mkdir()
    for i in range(3):
        (pasta_entrada / f"arquivo_{i}.pdf").write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(pipeline, "LIMITE_ALERTA_FALHAS", 3)
    monkeypatch.setattr(pipeline, "LIMITE_FALHAS_QUARENTENA", 999)  # nao mover para quarentena neste teste
    monkeypatch.setattr(pipeline.pdf_reader, "extrair_texto", lambda caminho: _TextoFalso("texto"))
    monkeypatch.setattr(pipeline, "extrair_ordem_de_compra", _falha_sempre)

    with caplog.at_level(logging.ERROR, logger="pipeline"):
        pipeline.executar_pipeline(
            modo="producao", db_path=tmp_path / "teste.db", pasta_entrada=str(pasta_entrada)
        )

    assert any("ALERTA" in registro.message for registro in caplog.records)


def test_executar_pipeline_sem_muitas_falhas_nao_alerta(tmp_path: Path, monkeypatch, caplog):
    pasta_entrada = tmp_path / "entrada"
    pasta_entrada.mkdir()
    (pasta_entrada / "arquivo_0.pdf").write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(pipeline, "LIMITE_ALERTA_FALHAS", 3)
    monkeypatch.setattr(pipeline.pdf_reader, "extrair_texto", lambda caminho: _TextoFalso("texto"))
    monkeypatch.setattr(pipeline, "extrair_ordem_de_compra", _falha_sempre)

    with caplog.at_level(logging.ERROR, logger="pipeline"):
        pipeline.executar_pipeline(
            modo="producao", db_path=tmp_path / "teste.db", pasta_entrada=str(pasta_entrada)
        )

    assert not any("ALERTA" in registro.message for registro in caplog.records)


def test_executar_pipeline_limita_arquivos_por_execucao(tmp_path: Path, monkeypatch):
    pasta_entrada = tmp_path / "entrada"
    pasta_entrada.mkdir()
    for i in range(5):
        (pasta_entrada / f"arquivo_{i}.pdf").write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(pipeline, "LIMITE_ARQUIVOS_POR_EXECUCAO", 2)
    monkeypatch.setattr(pipeline.pdf_reader, "extrair_texto", lambda caminho: _TextoFalso("texto"))
    monkeypatch.setattr(pipeline, "extrair_ordem_de_compra", _falha_sempre)

    db_path = tmp_path / "teste.db"
    resumo = pipeline.executar_pipeline(modo="producao", db_path=db_path, pasta_entrada=str(pasta_entrada))

    assert resumo["total"] == 2  # so tentou 2 dos 5 pendentes nesta execucao
    assert len(list(pasta_entrada.glob("*.pdf"))) == 5  # nenhum arquivo falho e movido/apagado

    conn = database.conectar(db_path)
    tentativas = conn.execute("SELECT COUNT(*) AS n FROM log_extracao").fetchone()["n"]
    assert tentativas == 2  # so 2 arquivos chegaram a ser tentados de verdade
    conn.close()


def test_executar_pipeline_faz_backup_do_banco_existente(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "teste.db"

    monkeypatch.setattr(pipeline, "_coletar_pdfs_demo", lambda: [])

    pipeline.executar_pipeline(modo="demo", db_path=db_path)  # cria o banco, sem nada para backup ainda
    assert not (tmp_path / "backups").exists()

    pipeline.executar_pipeline(modo="demo", db_path=db_path)  # agora o banco ja existia antes desta execucao
    backups = list((tmp_path / "backups").glob("teste_*.db"))
    assert len(backups) == 1
