"""
Aplicacao FastAPI do site de Ordens de Compra (backend real - ver
docs/arquitetura_webapp.md, a escrever na Fase 7). Substitui o relatorio
HTML estatico (report_generator.py, que continua existindo como snapshot
offline/fallback, ver README) por paginas server-side (Jinja2) servidas ao
vivo a partir do Postgres do Supabase.

Login (Fase 4): exigido em todas as rotas do dashboard via
Depends(exige_login) - Supabase Auth com provedor Azure (conta Microsoft),
com renovacao automatica de sessao (ver webapp/dependencias.py).

Leitura (dashboard.py): via pool de conexoes psycopg (webapp/pool.py),
aberto uma vez no startup (evento de lifespan abaixo) - a mesma conexao
"de confianca" que o pipeline usa (bypassa RLS, so para leitura). Escrita
de revisao (Fase 5, webapp/rotas/revisao.py): via client supabase-py
autenticado com o token do usuario logado, sujeito as policies de RLS de
verdade (sql/schema_postgres.sql) - a unica escrita que o site faz. Nenhuma
credencial (DATABASE_URL, chave anon ou service_role) e enviada ao
navegador em nenhum momento - todo acesso ao banco acontece neste processo
de servidor.

Rodar localmente (a partir da pasta src/, para os imports flat do resto do
projeto - ex: "import database" - continuarem funcionando):
    cd src
    python -m uvicorn webapp.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

# Mesmo motivo do load_dotenv() no topo de report_generator.py/pipeline.py:
# garante que o .env ja esteja carregado antes de qualquer os.environ.get()
# disparado por modulos importados abaixo (database.dsn_demo(), etc).
load_dotenv()

from webapp import pool  # noqa: E402 (depois do load_dotenv)
from webapp.dependencias import PrecisaLogin  # noqa: E402
from webapp.rotas import auth_rotas, dashboard, revisao  # noqa: E402


@asynccontextmanager
async def _ciclo_de_vida(app: FastAPI):
    pool.iniciar_pool()
    yield
    pool.encerrar_pool()


app = FastAPI(title="Painel de Ordens de Compra", lifespan=_ciclo_de_vida)

app.include_router(auth_rotas.router)
app.include_router(dashboard.router)
app.include_router(revisao.router)


@app.exception_handler(PrecisaLogin)
def _redirecionar_para_login(request: Request, exc: PrecisaLogin) -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=303)


@app.get("/healthz")
def healthz():
    """Endpoint sem autenticacao, so para o health check do host de deploy
    (Fase 6, Render) - as demais rotas exigem login e nao servem para isso
    (o health check nao teria como seguir um redirect para /login com
    Microsoft OAuth)."""

    return {"status": "ok"}
