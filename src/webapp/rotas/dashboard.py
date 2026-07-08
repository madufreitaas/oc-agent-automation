"""
Rotas de leitura do painel: GET / (Analytics), GET /detalhada (Ordens de
Compra), GET /alertas (Central de Alertas) e GET /auditoria (Auditoria e
Governanca) - essas 3 ultimas eram uma unica pagina ("Detalhada") ate serem
separadas para dar mais espaco/foco a cada uma na navegacao. Fase 3 da
migracao para backend real - ver o aviso de seguranca/RLS temporario no
docstring de webapp/main.py.

As conexoes vem do pool aberto uma vez na subida do FastAPI (ver webapp/pool.py
e o evento de lifespan em webapp/main.py) - evita o custo de abrir/fechar uma
conexao nova (handshake TCP+TLS+Postgres via connection pooler do Supabase)
a cada requisicao, que era o maior fator de lentidao percebida.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from formatacao_painel import (
    badge_tipo_alerta,
    barras_html,
    calcular_indicadores,
    fmt_data,
    fmt_moeda,
    link_documento,
    status_oc,
)
from webapp import pool
from webapp.contexto import templates
from webapp.dependencias import exige_login

router = APIRouter()

RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent.parent
QUERY_CENTRAL_ALERTAS = RAIZ_PROJETO / "sql" / "queries" / "central_alertas.sql"

# Mesmo limite usado em pipeline.py/report_generator.py para o banner de
# falhas recentes de extracao.
LIMITE_ALERTA_FALHAS_RECENTES = int(os.environ.get("LIMITE_ALERTA_FALHAS", "3"))


def _int_ou_none(valor: Optional[str], *, minimo: int, maximo: int) -> Optional[int]:
    """Converte um parametro de query de filtro (string, possivelmente vazia
    ou ausente) para int, ou None se estiver em branco/invalido/fora da
    faixa - trata o campo em branco do formulario (_filtros.html) como
    'sem filtro', em vez de 422."""

    if valor is None or valor.strip() == "":
        return None
    try:
        numero = int(valor)
    except ValueError:
        return None
    if not (minimo <= numero <= maximo):
        return None
    return numero


def _condicoes_filtro(
    status: str, ano: Optional[int], mes: Optional[int], dia: Optional[int], prefixo: str
) -> tuple[list[str], list[str]]:
    """Monta as condicoes SQL (parametrizadas com %s, nunca com o valor
    embutido na string) para os filtros da aba Detalhada: status de revisao
    (pendente/revisado/todos) e data de emissao da NF (ano/mes/dia, cada um
    opcional e combinavel independentemente - ex: so mes, sem ano, filtra
    esse mes em qualquer ano).

    data_emissao e uma coluna text no formato ISO 'AAAA-MM-DD' (gravada por
    oc.data_emissao.isoformat() em database.py), entao left()/substring()
    bastam - nao precisa de CAST para date.

    prefixo e o alias da tabela/subquery de onde vem revisado/data_emissao
    ("oc" na consulta de ordens_compra, "t" quando central_alertas.sql e
    envolvida numa subquery para poder ser filtrada aqui.
    """

    condicoes: list[str] = []
    parametros: list[str] = []

    if status == "pendente":
        condicoes.append(f"{prefixo}.revisado = false")
    elif status == "revisado":
        condicoes.append(f"{prefixo}.revisado = true")

    if ano:
        condicoes.append(f"left({prefixo}.data_emissao, 4) = %s")
        parametros.append(f"{ano:04d}")
    if mes:
        condicoes.append(f"substring({prefixo}.data_emissao from 6 for 2) = %s")
        parametros.append(f"{mes:02d}")
    if dia:
        condicoes.append(f"substring({prefixo}.data_emissao from 9 for 2) = %s")
        parametros.append(f"{dia:02d}")

    return condicoes, parametros


def _usuario_pode_revisar(conn, sessao) -> bool:
    """So decide se mostra o botao 'Marcar revisado' (Ordens de Compra e
    Central de Alertas usam as duas) - a trava de seguranca real e a policy
    de RLS 'revisor_ou_admin_pode_revisar', verificada de verdade em
    webapp/rotas/revisao.py via exige_papel (essa sim usa o client
    autenticado com o token do usuario, sujeito a RLS)."""

    linha_papel = conn.execute(
        "SELECT papel FROM perfis WHERE id = %s", (str(sessao.usuario.id),)
    ).fetchone()
    return (linha_papel["papel"] if linha_papel else "leitor") in ("admin", "revisor")


def _anos_disponiveis(conn) -> list[str]:
    return [
        row["ano"]
        for row in conn.execute(
            "SELECT DISTINCT left(data_emissao, 4) AS ano FROM ordens_compra "
            "WHERE data_emissao IS NOT NULL ORDER BY 1 DESC"
        ).fetchall()
    ]


def _banner_falhas(conn) -> str:
    falhas_recentes = conn.execute(
        "SELECT COUNT(*) AS n FROM log_extracao WHERE status LIKE %s AND timestamp >= now() - interval '1 day'",
        ("erro%",),
    ).fetchone()["n"]
    if falhas_recentes < LIMITE_ALERTA_FALHAS_RECENTES:
        return ""
    return (
        f"{falhas_recentes} falha(s) de extracao nas ultimas 24 horas "
        f"(limite de alerta: {LIMITE_ALERTA_FALHAS_RECENTES})."
    )


@router.get("/")
def analytics(request: Request, sessao=Depends(exige_login)):
    with pool.obter_conexao() as conn:
        indicadores = calcular_indicadores(conn)

        por_cliente = conn.execute(
            """
            SELECT c.nome AS cliente, SUM(oc.valor_total) AS total
            FROM ordens_compra oc JOIN clientes c ON c.id = oc.cliente_id
            GROUP BY c.id ORDER BY total DESC LIMIT 10
            """
        ).fetchall()

        itens_recorrentes = conn.execute(
            """
            SELECT descricao, SUM(quantidade) AS qtd
            FROM itens_oc GROUP BY descricao ORDER BY qtd DESC LIMIT 10
            """
        ).fetchall()

    classe_dot_alerta_kpi = "status-dot-ok" if indicadores["ocs_com_alerta"] == 0 else "status-dot-atencao"

    return templates.TemplateResponse(
        request,
        "analytics.html",
        {
            "usuario_email": sessao.usuario.email,
            "indicadores": indicadores,
            "classe_dot_alerta_kpi": classe_dot_alerta_kpi,
            "fmt_moeda": fmt_moeda,
            "barras_por_cliente": barras_html(
                [(r["cliente"], r["total"] or 0.0) for r in por_cliente], fmt_moeda
            ),
            "barras_itens": barras_html(
                [(r["descricao"], r["qtd"] or 0.0) for r in itens_recorrentes], lambda v: f"{v:g}"
            ),
        },
    )


# Optional[str] (nao int) de proposito nos 3 parametros de filtro abaixo: os
# <select>/<input> do formulario de filtro (_filtros.html) mandam "" (string
# vazia) quando o campo fica em branco - FastAPI rejeitaria isso com 422 se o
# tipo fosse Optional[int] direto, ja que "" nao e um inteiro valido.
# _int_ou_none trata "" como "sem filtro" (None), igual a nao mandar o parametro.


@router.get("/detalhada")
def ordens_compra(
    request: Request,
    sessao=Depends(exige_login),
    status: str = Query("todos", pattern="^(todos|pendente|revisado)$"),
    ano: Optional[str] = Query(None),
    mes: Optional[str] = Query(None),
    dia: Optional[str] = Query(None),
):
    ano_int = _int_ou_none(ano, minimo=1900, maximo=2999)
    mes_int = _int_ou_none(mes, minimo=1, maximo=12)
    dia_int = _int_ou_none(dia, minimo=1, maximo=31)
    ano, mes, dia = ano_int, mes_int, dia_int

    with pool.obter_conexao() as conn:
        pode_revisar = _usuario_pode_revisar(conn, sessao)
        anos_disponiveis = _anos_disponiveis(conn)
        banner_falhas = _banner_falhas(conn)

        condicoes_oc, params_oc = _condicoes_filtro(status, ano, mes, dia, "oc")
        where_oc = ("WHERE " + " AND ".join(condicoes_oc)) if condicoes_oc else ""
        ocs_recentes = conn.execute(
            f"""
            SELECT oc.id, oc.numero_oc, oc.data_emissao, c.nome AS cliente, oc.valor_total, oc.layout_origem,
                   oc.arquivo_origem, oc.revisado,
                   (oc.status_extracao = 'possivel_duplicata' OR oc.alerta_valor_divergente
                    OR oc.alerta_baixa_confianca OR oc.alerta_cnpj_invalido) AS tem_alerta
            FROM ordens_compra oc JOIN clientes c ON c.id = oc.cliente_id
            {where_oc}
            ORDER BY oc.data_extracao DESC LIMIT 15
            """,
            params_oc,
        ).fetchall()

    return templates.TemplateResponse(
        request,
        "ordens.html",
        {
            "usuario_email": sessao.usuario.email,
            "pode_revisar": pode_revisar,
            "ocs_recentes": ocs_recentes,
            "banner_falhas": banner_falhas,
            "fmt_moeda": fmt_moeda,
            "status_oc": status_oc,
            "link_documento": link_documento,
            "filtro_status": status,
            "filtro_ano": ano,
            "filtro_mes": mes,
            "filtro_dia": dia,
            "anos_disponiveis": anos_disponiveis,
        },
    )


@router.get("/alertas")
def central_alertas_view(
    request: Request,
    sessao=Depends(exige_login),
    status: str = Query("todos", pattern="^(todos|pendente|revisado)$"),
    ano: Optional[str] = Query(None),
    mes: Optional[str] = Query(None),
    dia: Optional[str] = Query(None),
):
    ano_int = _int_ou_none(ano, minimo=1900, maximo=2999)
    mes_int = _int_ou_none(mes, minimo=1, maximo=12)
    dia_int = _int_ou_none(dia, minimo=1, maximo=31)
    ano, mes, dia = ano_int, mes_int, dia_int

    with pool.obter_conexao() as conn:
        pode_revisar = _usuario_pode_revisar(conn, sessao)
        anos_disponiveis = _anos_disponiveis(conn)
        banner_falhas = _banner_falhas(conn)

        condicoes_alertas, params_alertas = _condicoes_filtro(status, ano, mes, dia, "t")
        where_alertas = ("WHERE " + " AND ".join(condicoes_alertas)) if condicoes_alertas else ""
        sql_central_alertas = QUERY_CENTRAL_ALERTAS.read_text(encoding="utf-8").rstrip().rstrip(";")
        central_alertas = conn.execute(
            f"SELECT * FROM ({sql_central_alertas}) t {where_alertas} ORDER BY t.data_extracao DESC",
            params_alertas,
        ).fetchall()

    return templates.TemplateResponse(
        request,
        "alertas.html",
        {
            "usuario_email": sessao.usuario.email,
            "pode_revisar": pode_revisar,
            "central_alertas": central_alertas,
            "banner_falhas": banner_falhas,
            "fmt_data": fmt_data,
            "badge_tipo_alerta": badge_tipo_alerta,
            "link_documento": link_documento,
            "filtro_status": status,
            "filtro_ano": ano,
            "filtro_mes": mes,
            "filtro_dia": dia,
            "anos_disponiveis": anos_disponiveis,
        },
    )


@router.get("/auditoria")
def auditoria(request: Request, sessao=Depends(exige_login)):
    with pool.obter_conexao() as conn:
        banner_falhas = _banner_falhas(conn)
        log_extracao = conn.execute(
            "SELECT arquivo, timestamp, status, confianca, erro FROM log_extracao ORDER BY timestamp DESC LIMIT 30"
        ).fetchall()

    return templates.TemplateResponse(
        request,
        "auditoria.html",
        {
            "usuario_email": sessao.usuario.email,
            "log_extracao": log_extracao,
            "banner_falhas": banner_falhas,
            "fmt_data": fmt_data,
            "link_documento": link_documento,
        },
    )
