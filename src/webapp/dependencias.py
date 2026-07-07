"""
Dependencia de autenticacao (FastAPI Depends), usada nas rotas do dashboard.

exige_login(): confirma que a requisicao tem uma sessao Supabase valida,
lendo os cookies httponly sb_access_token/sb_refresh_token setados em
POST /auth/sessao (ver rotas/auth_rotas.py). Faz a validacao chamando o
Supabase Auth (client.auth.get_user), que confere o token no servidor - nao
so decodifica o JWT localmente.

Renovacao automatica (access_token expira em ~1h por padrao, ver
docs/arquitetura_webapp.md): se get_user() rejeitar o access_token mas o
refresh_token do cookie ainda for valido, chama client.auth.refresh_session()
e reemite os dois cookies com os tokens novos - a usuaria nunca ve um logout
por expiracao de token sozinha, so quando o refresh_token tambem expirar ou
for revogado.

FastAPI injeta o mesmo objeto Response que sera devolvido na dependencia
quando ela declara um parametro Response - os cookies setados aqui dentro
sao mesclados na resposta final da rota, mesmo a dependencia nao sendo ela
mesma o "endpoint". E o jeito recomendado pelo FastAPI de setar cookies a
partir de uma dependencia (nao um hack).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, Response
from supabase_auth.errors import AuthApiError
from supabase_auth.types import User

from supabase_client import cliente_auth

COOKIE_ACCESS = "sb_access_token"
COOKIE_REFRESH = "sb_refresh_token"

# Cookies "secure" (so enviados por HTTPS) em producao; em desenvolvimento
# local (http://127.0.0.1) o navegador descartaria um cookie secure, entao
# fica desligado a menos que AMBIENTE=producao esteja configurado (ver
# .env.example e o deploy da Fase 6, que roda atras de HTTPS).
_PRODUCAO = os.environ.get("AMBIENTE", "local") == "producao"


class PrecisaLogin(Exception):
    """Levantada quando a requisicao nao tem uma sessao Supabase valida.
    main.py registra um exception handler que converte isso num redirect
    para /login, em vez de expor um 401/500 cru para quem esta so navegando
    pelo site sem estar logado."""


@dataclass
class SessaoAtual:
    """access_token incluido (nao so o User) porque a Fase 5 precisa dele
    para autenticar chamadas supabase-py/PostgREST em nome do usuario logado
    (client.postgrest.auth(access_token)) - assim as policies de RLS
    (sql/schema_postgres.sql) sao avaliadas de verdade, com auth.uid() igual
    ao id de quem esta logado. Se exige_login renovou a sessao nesta mesma
    requisicao, access_token ja e o token novo (nunca o cookie antigo/expirado)."""

    usuario: User
    access_token: str


def definir_cookies_sessao(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        COOKIE_ACCESS, access_token, httponly=True, secure=_PRODUCAO, samesite="lax", path="/",
    )
    # refresh_token dura bem mais que o access_token (dias/semanas, conforme
    # configurado no projeto Supabase) - max_age generoso, mas o Supabase
    # quem decide de fato quando o refresh_token deixa de ser valido.
    response.set_cookie(
        COOKIE_REFRESH, refresh_token, httponly=True, secure=_PRODUCAO, samesite="lax", path="/",
        max_age=60 * 60 * 24 * 30,
    )


def limpar_cookies_sessao(response: Response) -> None:
    response.delete_cookie(COOKIE_ACCESS, path="/")
    response.delete_cookie(COOKIE_REFRESH, path="/")


def exige_login(request: Request, response: Response) -> SessaoAtual:
    access_token = request.cookies.get(COOKIE_ACCESS)
    refresh_token = request.cookies.get(COOKIE_REFRESH)
    if not access_token:
        raise PrecisaLogin()

    client = cliente_auth()

    try:
        resultado = client.auth.get_user(access_token)
        if resultado is not None:
            return SessaoAtual(usuario=resultado.user, access_token=access_token)
    except AuthApiError:
        pass  # access_token expirado/invalido - tenta renovar via refresh_token abaixo

    if not refresh_token:
        raise PrecisaLogin()

    try:
        nova_sessao = client.auth.refresh_session(refresh_token)
    except AuthApiError:
        raise PrecisaLogin()

    if nova_sessao.session is None:
        raise PrecisaLogin()

    definir_cookies_sessao(response, nova_sessao.session.access_token, nova_sessao.session.refresh_token)
    return SessaoAtual(usuario=nova_sessao.user, access_token=nova_sessao.session.access_token)


def papel_atual(sessao: SessaoAtual) -> str:
    """Le o papel do usuario logado direto da tabela perfis, via PostgREST
    autenticado com o access_token dele - respeitando a policy
    'usuario_ve_o_proprio_perfil' (id = auth.uid()), nao uma conexao de
    confianca que ignora RLS. Fallback para 'leitor' (o papel mais restrito)
    se a linha nao aparecer por algum motivo - nunca assume um papel mais
    permissivo por omissao."""

    client = cliente_auth()
    client.postgrest.auth(sessao.access_token)
    resultado = client.table("perfis").select("papel").eq("id", str(sessao.usuario.id)).execute()
    if not resultado.data:
        return "leitor"
    return resultado.data[0]["papel"]


def exige_papel(*papeis_permitidos: str):
    """Fabrica de dependencia: Depends(exige_papel("admin", "revisor")).

    Gate de autorizacao no nivel da aplicacao, para dar um erro 403 claro
    cedo - mas nao e a unica defesa: a escrita de verdade (ver
    webapp/rotas/revisao.py) tambem passa pelo PostgREST autenticado com o
    token do usuario, entao a policy 'revisor_ou_admin_pode_revisar' do
    Postgres e a garantia final, mesmo se este gate tivesse um bug."""

    def dependencia(sessao: SessaoAtual = Depends(exige_login)) -> SessaoAtual:
        if papel_atual(sessao) not in papeis_permitidos:
            raise HTTPException(status_code=403, detail="Seu papel nao permite esta acao.")
        return sessao

    return dependencia
