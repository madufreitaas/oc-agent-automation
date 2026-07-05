from pathlib import Path

import pytest

from folder_watcher import FolderWatcherError, coletar_pdfs, marcar_como_processado, mover_para_falhas


def test_coletar_pdfs_lista_apenas_pdfs_pendentes(tmp_path: Path):
    (tmp_path / "oc_1.pdf").write_bytes(b"%PDF-1.4 fake")
    (tmp_path / "oc_2.pdf").write_bytes(b"%PDF-1.4 fake")
    (tmp_path / "nao_e_pdf.txt").write_text("ignorar")

    pasta_processados = tmp_path / "processados"
    pasta_processados.mkdir()
    (pasta_processados / "oc_antigo.pdf").write_bytes(b"%PDF-1.4 fake")

    pasta_falhas = tmp_path / "falhas"
    pasta_falhas.mkdir()
    (pasta_falhas / "oc_quarentena.pdf").write_bytes(b"%PDF-1.4 fake")

    pendentes = coletar_pdfs(tmp_path)

    nomes = {p.name for p in pendentes}
    assert nomes == {"oc_1.pdf", "oc_2.pdf"}


def test_coletar_pdfs_pasta_inexistente_levanta_erro(tmp_path: Path):
    with pytest.raises(FolderWatcherError):
        coletar_pdfs(tmp_path / "nao_existe")


def test_coletar_pdfs_caminho_nao_e_pasta_levanta_erro(tmp_path: Path):
    arquivo = tmp_path / "arquivo.pdf"
    arquivo.write_bytes(b"%PDF-1.4 fake")
    with pytest.raises(FolderWatcherError):
        coletar_pdfs(arquivo)


def test_marcar_como_processado_move_para_subpasta(tmp_path: Path):
    caminho_pdf = tmp_path / "oc_1.pdf"
    caminho_pdf.write_bytes(b"%PDF-1.4 fake")

    destino = marcar_como_processado(caminho_pdf)

    assert destino.parent.name == "processados"
    assert destino.exists()
    assert not caminho_pdf.exists()


def test_marcar_como_processado_nao_sobrescreve_arquivo_existente(tmp_path: Path):
    caminho_pdf = tmp_path / "oc_1.pdf"
    caminho_pdf.write_bytes(b"conteudo novo")

    pasta_processados = tmp_path / "processados"
    pasta_processados.mkdir()
    (pasta_processados / "oc_1.pdf").write_bytes(b"conteudo antigo")

    destino = marcar_como_processado(caminho_pdf)

    assert destino.name != "oc_1.pdf"
    assert destino.read_bytes() == b"conteudo novo"
    assert (pasta_processados / "oc_1.pdf").read_bytes() == b"conteudo antigo"


def test_mover_para_falhas_move_para_subpasta(tmp_path: Path):
    caminho_pdf = tmp_path / "oc_problematico.pdf"
    caminho_pdf.write_bytes(b"%PDF-1.4 fake")

    destino = mover_para_falhas(caminho_pdf)

    assert destino.parent.name == "falhas"
    assert destino.exists()
    assert not caminho_pdf.exists()
