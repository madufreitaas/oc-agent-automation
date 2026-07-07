"""
Cliente supabase-py compartilhado pelas rotas de autenticacao do site
(src/webapp/rotas/auth_rotas.py) e pela dependencia de sessao
(src/webapp/dependencias.py).

Usa sempre a chave anon/publishable (SUPABASE_ANON_KEY) - a mesma que o
supabase-js usa no navegador para iniciar o login. Isso e suficiente para
validar o access_token de um usuario (auth.get_user(jwt)) e renovar a sessao
(auth.refresh_session()): essas duas operacoes sao por design da API do
Supabase Auth, nao exigem a service_role key. A service_role key (que
ignora RLS) nunca e usada neste modulo nem em nenhum lugar do site - so o
pipeline local (database.py, via psycopg direto) tem esse nivel de acesso.
"""

from __future__ import annotations

import os

from supabase import Client, create_client


def cliente_auth() -> Client:
    """Cria um client supabase-py novo, autenticado so com a chave anon.

    Criado por chamada (nao um singleton de modulo) de proposito: o client
    supabase-py guarda estado de sessao internamente, e cada requisicao HTTP
    do site pode estar validando/renovando o token de um usuario diferente -
    reaproveitar uma instancia entre requisicoes misturaria sessoes.
    """

    url = os.environ.get("SUPABASE_URL", "")
    chave_anon = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not chave_anon:
        raise RuntimeError(
            "SUPABASE_URL/SUPABASE_ANON_KEY nao configuradas no .env - "
            "ver docs/arquitetura_webapp.md."
        )
    return create_client(url, chave_anon)
