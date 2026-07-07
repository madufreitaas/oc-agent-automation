"""
Pool de conexoes Postgres do site (nao do pipeline - pipeline.py roda uma
vez e encerra, database.conectar() avulso e adequado para ele; o site serve
requisicoes concorrentes ao longo do tempo, entao abrir e fechar uma conexao
nova a cada requisicao HTTP - handshake TCP+TLS+Postgres completo via
connection pooler do Supabase - e desperdicio de latencia). O pool e aberto
uma unica vez, na subida do FastAPI (ver main.py, evento de lifespan), e
reaproveitado entre requisicoes.

min_size/max_size conservadores de proposito: o connection pooler do
Supabase (camada gratuita) tem um limite total de conexoes compartilhado
entre o site e o pipeline local - nao faz sentido este pool sozinho reservar
muitas.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

import database

_pool: ConnectionPool | None = None


def _dsn_do_site() -> str:
    modo = os.environ.get("MODO_EXECUCAO", "demo")
    return database.dsn_producao() if modo == "producao" else database.dsn_demo()


def iniciar_pool() -> None:
    global _pool
    _pool = ConnectionPool(
        conninfo=_dsn_do_site(),
        min_size=1,
        max_size=4,
        kwargs={"row_factory": dict_row, "autocommit": False},
        open=True,
    )


def encerrar_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def obter_conexao():
    if _pool is None:
        raise RuntimeError("Pool de conexoes nao foi iniciado - iniciar_pool() deve rodar no startup do FastAPI.")
    with _pool.connection() as conn:
        yield conn
