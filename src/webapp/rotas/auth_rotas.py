"""
Rotas de autenticacao: GET /login (pagina com o botao "Entrar com Microsoft"),
POST /auth/sessao (recebe os tokens depois do redirect OAuth e seta os
cookies httponly) e GET /logout.

Fluxo completo (detalhado em docs/arquitetura_webapp.md, escrito na Fase 7):
1. login.html carrega supabase-js (via CDN) e, ao clicar no botao, chama
   supabase.auth.signInWithOAuth({ provider: 'azure' }). O Supabase cuida do
   redirect para a Microsoft e da troca do codigo OAuth por um token - tudo
   isso acontece no navegador, este backend nao participa dessa etapa.
2. Depois do redirect de volta para o site, o script em login.html le a
   sessao (supabase.auth.getSession()) e faz um POST explicito do
   access_token + refresh_token para /auth/sessao (rota abaixo) - nao existe
   transferencia automatica do JWT do navegador para o FastAPI, precisa
   deste passo manual.
3. /auth/sessao valida o access_token contra o Supabase Auth (auth.get_user,
   que confere no servidor, nao so decodifica o JWT) e so entao seta os
   cookies httponly - a partir daqui, exige_login (webapp/dependencias.py)
   cuida da sessao (incluindo renovacao automatica) nas demais rotas.
"""

from __future__ import annotations

import json
import os

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from supabase_auth.errors import AuthApiError

from supabase_client import cliente_auth
from webapp.contexto import templates
from webapp.dependencias import definir_cookies_sessao, limpar_cookies_sessao

router = APIRouter()


@router.get("/login")
def login(request: Request):
    # Serializados aqui (nao com um filtro Jinja "tojson", que so existe no
    # ambiente Flask) para embutir com seguranca dentro do <script> do
    # template - json.dumps escapa aspas/barras corretamente para JS.
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "supabase_url_json": json.dumps(os.environ.get("SUPABASE_URL", "")),
            "supabase_anon_key_json": json.dumps(os.environ.get("SUPABASE_ANON_KEY", "")),
        },
    )


class TokensSessao(BaseModel):
    access_token: str
    refresh_token: str


@router.post("/auth/sessao")
def criar_sessao(dados: TokensSessao, response: Response):
    client = cliente_auth()
    try:
        resultado = client.auth.get_user(dados.access_token)
    except AuthApiError:
        resultado = None

    if resultado is None:
        return Response(status_code=401, content="Token invalido ou expirado.")

    definir_cookies_sessao(response, dados.access_token, dados.refresh_token)
    return {"ok": True, "email": resultado.user.email}


@router.get("/logout")
def logout():
    resposta = RedirectResponse(url="/login", status_code=303)
    limpar_cookies_sessao(resposta)
    return resposta
