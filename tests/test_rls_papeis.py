"""
Testes de RLS por papel (Fase 5 da migracao para backend real - ver
sql/schema_postgres.sql). Confirmam que as policies do Postgres realmente
bloqueiam um usuario 'leitor' de marcar uma OC como revisada, e permitem
'admin'/'revisor' - a mesma operacao que webapp/rotas/revisao.py expoe.

Por que um teste separado, direto contra o Postgres (nao so um mock de rota
FastAPI): uma policy de RLS errada nao levanta excecao, so filtra a linha
silenciosamente (a UPDATE roda, mas afeta 0 linhas - PostgREST devolve 200
com data=[], nao um 403). Um teste que so mocka o supabase-py nunca pegaria
esse tipo de bug, porque o mock nunca chega a avaliar a policy de verdade.

Roda contra o projeto Supabase demo real - skip (nao fail) se as variaveis
de ambiente necessarias nao estiverem configuradas, mesmo padrao dos outros
testes que tocam o banco (ver tests/test_database.py).
"""

from __future__ import annotations

import os
import uuid

import pytest
from supabase import create_client

import database

PREFIXO_TESTE = "teste_rls_"


def _config_ou_skip() -> tuple[str, str, str, str]:
    url = os.environ.get("SUPABASE_URL", "")
    anon = os.environ.get("SUPABASE_ANON_KEY", "")
    service_role = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    dsn = database.dsn_demo()
    if not (url and anon and service_role and dsn):
        pytest.skip(
            "SUPABASE_URL/SUPABASE_ANON_KEY/SUPABASE_SERVICE_ROLE_KEY/DATABASE_URL_DEMO "
            "nao configuradas - ver docs/arquitetura_webapp.md."
        )
    return url, anon, service_role, dsn


@pytest.fixture
def oc_teste():
    """Cria cliente/fornecedor/OC de teste via conexao direta (bypassa RLS,
    mesma conexao que o pipeline usa) e limpa tudo ao final, independente do
    resultado dos testes."""

    _, _, _, dsn = _config_ou_skip()
    conn = database.conectar(dsn)

    cliente_id = conn.execute(
        "INSERT INTO clientes (nome, cnpj) VALUES (%s, %s) RETURNING id",
        (f"{PREFIXO_TESTE}cliente", None),
    ).fetchone()["id"]
    fornecedor_id = conn.execute(
        "INSERT INTO fornecedores (nome, cnpj) VALUES (%s, %s) RETURNING id",
        (f"{PREFIXO_TESTE}fornecedor", None),
    ).fetchone()["id"]
    ordem_compra_id = conn.execute(
        """
        INSERT INTO ordens_compra (numero_oc, cliente_id, fornecedor_id, arquivo_origem)
        VALUES (%s, %s, %s, %s) RETURNING id
        """,
        (f"{PREFIXO_TESTE}oc", cliente_id, fornecedor_id, f"{PREFIXO_TESTE}arquivo.pdf"),
    ).fetchone()["id"]
    conn.commit()

    yield ordem_compra_id

    conn.execute("DELETE FROM ordens_compra WHERE id = %s", (ordem_compra_id,))
    conn.execute("DELETE FROM fornecedores WHERE id = %s", (fornecedor_id,))
    conn.execute("DELETE FROM clientes WHERE id = %s", (cliente_id,))
    conn.commit()
    conn.close()


@pytest.fixture
def usuario_teste():
    """Fabrica de usuarios de teste: cria uma conta de e-mail/senha via
    Admin API (service_role - o unico jeito de criar um usuario sem passar
    pelo fluxo OAuth real da Microsoft, que nao da para automatizar aqui),
    promove ao papel pedido direto na tabela perfis, faz login por senha e
    devolve o access_token. Remove o(s) usuario(s) criado(s) ao final (a
    linha em perfis some junto, via ON DELETE CASCADE em auth.users)."""

    url, anon, service_role, dsn = _config_ou_skip()
    client_admin = create_client(url, service_role)
    criados: list[str] = []

    def _criar(papel: str) -> str:
        email = f"{PREFIXO_TESTE}{papel}_{uuid.uuid4().hex[:8]}@example.com"
        senha = f"Teste!{uuid.uuid4().hex}"
        resposta = client_admin.auth.admin.create_user(
            {"email": email, "password": senha, "email_confirm": True}
        )
        user_id = str(resposta.user.id)
        criados.append(user_id)

        conn = database.conectar(dsn)
        conn.execute("UPDATE perfis SET papel = %s WHERE id = %s", (papel, user_id))
        conn.commit()
        conn.close()

        client_usuario = create_client(url, anon)
        sessao = client_usuario.auth.sign_in_with_password({"email": email, "password": senha})
        return sessao.session.access_token

    yield _criar

    for user_id in criados:
        client_admin.auth.admin.delete_user(user_id)


def _tentar_marcar_revisado(url: str, anon: str, access_token: str, ordem_compra_id: int):
    client = create_client(url, anon)
    client.postgrest.auth(access_token)
    return client.table("ordens_compra").update({"revisado": True}).eq("id", ordem_compra_id).execute()


def test_leitor_nao_consegue_marcar_oc_como_revisada(oc_teste, usuario_teste):
    url, anon, _, _ = _config_ou_skip()
    access_token = usuario_teste("leitor")

    resultado = _tentar_marcar_revisado(url, anon, access_token, oc_teste)

    # RLS bloqueia sem levantar excecao - a policy so filtra a linha, entao
    # o retorno e uma lista vazia (0 linhas afetadas), nao um erro HTTP.
    assert resultado.data == []


def test_admin_consegue_marcar_oc_como_revisada(oc_teste, usuario_teste):
    url, anon, _, _ = _config_ou_skip()
    access_token = usuario_teste("admin")

    resultado = _tentar_marcar_revisado(url, anon, access_token, oc_teste)

    assert len(resultado.data) == 1
    assert resultado.data[0]["revisado"] is True


def test_revisor_consegue_marcar_oc_como_revisada(oc_teste, usuario_teste):
    url, anon, _, _ = _config_ou_skip()
    access_token = usuario_teste("revisor")

    resultado = _tentar_marcar_revisado(url, anon, access_token, oc_teste)

    assert len(resultado.data) == 1
    assert resultado.data[0]["revisado"] is True


def test_leitura_via_rls_bate_com_leitura_direta_do_pipeline(oc_teste, usuario_teste):
    """Verificacao cruzada da Fase 5 (ver docs/arquitetura_webapp.md): o
    pipeline grava via conexao direta (service role, contorna RLS) e o site
    le via PostgREST com o token do usuario (sujeito a RLS) - uma policy de
    SELECT com bug esconderia linhas sem erro nenhum. Confirma que a OC de
    teste, gravada pela fixture oc_teste (mesma conexao do pipeline), aparece
    tambem na leitura autenticada de um usuario 'leitor' comum."""

    url, anon, _, dsn = _config_ou_skip()
    access_token = usuario_teste("leitor")

    conn = database.conectar(dsn)
    numero_oc_direto = conn.execute(
        "SELECT numero_oc FROM ordens_compra WHERE id = %s", (oc_teste,)
    ).fetchone()["numero_oc"]
    conn.close()

    client = create_client(url, anon)
    client.postgrest.auth(access_token)
    resultado = client.table("ordens_compra").select("numero_oc").eq("id", oc_teste).execute()

    assert len(resultado.data) == 1
    assert resultado.data[0]["numero_oc"] == numero_oc_direto
