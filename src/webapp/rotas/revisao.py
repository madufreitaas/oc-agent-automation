"""
Rotas de revisao humana: POST /ocs/{id}/revisar e POST /ocs/{id}/desfazer-revisao.
So usuarios com papel 'admin' ou 'revisor' (ver Depends(exige_papel(...)) em
webapp/dependencias.py) conseguem marcar ou desmarcar uma OC como revisada -
a Central de alertas (aba Detalhada) nunca corrige ou exclui um alerta
sozinha, so sinaliza; marcar/desmarcar como revisada e a unica acao humana
que este backend permite sobre uma ordens_compra.

"Desfazer" existe para corrigir um clique errado (marcar a OC errada por
engano) sem precisar mexer no banco na mao - reaproveita a mesma policy de
RLS, so muda o valor gravado.

A escrita passa pelo client supabase-py/PostgREST autenticado com o
access_token do usuario logado (client.postgrest.auth(...)), nao pela
conexao de confianca que o pipeline/dashboard usam para leitura - assim a
policy "revisor_ou_admin_pode_revisar" (sql/schema_postgres.sql) e a
garantia real contra um papel 'leitor' revisando uma OC, nao so o gate de
aplicacao em exige_papel (defesa em profundidade: mesmo com um bug no gate
de app, o Postgres barra).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from supabase_client import cliente_auth
from webapp.dependencias import SessaoAtual, exige_papel

router = APIRouter()


def _atualizar_revisado(sessao: SessaoAtual, ordem_compra_id: int, revisado: bool) -> dict:
    client = cliente_auth()
    client.postgrest.auth(sessao.access_token)

    dados = (
        {
            "revisado": True,
            "revisado_em": datetime.now(timezone.utc).isoformat(),
            "revisado_por": str(sessao.usuario.id),
        }
        if revisado
        else {"revisado": False, "revisado_em": None, "revisado_por": None}
    )

    resultado = client.table("ordens_compra").update(dados).eq("id", ordem_compra_id).execute()

    # RLS filtra silenciosamente (nao levanta excecao) quando a policy nao
    # permite a linha - resultado.data vazio aqui significa "sem efeito",
    # seja porque o id nao existe, seja (nao deveria acontecer, ja que
    # exige_papel ja barrou antes) porque a policy negou mesmo assim.
    if not resultado.data:
        raise HTTPException(status_code=404, detail="Ordem de compra nao encontrada.")

    return {"ok": True, "id": ordem_compra_id, "revisado": revisado}


@router.post("/ocs/{ordem_compra_id}/revisar")
def revisar_oc(ordem_compra_id: int, sessao: SessaoAtual = Depends(exige_papel("admin", "revisor"))):
    return _atualizar_revisado(sessao, ordem_compra_id, revisado=True)


@router.post("/ocs/{ordem_compra_id}/desfazer-revisao")
def desfazer_revisao_oc(ordem_compra_id: int, sessao: SessaoAtual = Depends(exige_papel("admin", "revisor"))):
    return _atualizar_revisado(sessao, ordem_compra_id, revisado=False)
