"""
Helpers de formatacao/HTML e calculo de indicadores do painel de Ordens de
Compra - compartilhados entre o gerador de HTML estatico (report_generator.py)
e as rotas do site (src/webapp), para nao duplicar a mesma logica de exibicao
e consulta em dois lugares.

calcular_indicadores() recebe uma conexao ja aberta (psycopg.Connection, com
row_factory=dict_row - ver database.conectar()), entao o acesso a cada linha
por row["coluna"] funciona igual tanto aqui quanto nas rotas do site.
"""

from __future__ import annotations

import html
import os
from urllib.parse import quote

# Tipos de alerta considerados criticos (erro deterministico, sem ambiguidade)
# vs os demais, que sao sinalizacoes de julgamento (precisam de revisao, mas
# podem ser legitimos). So muda a cor do badge, nunca o tratamento: nenhum
# alerta, de nenhum tipo, e corrigido ou excluido automaticamente.
TIPOS_ALERTA_CRITICOS = {"CNPJ invalido"}


def fmt_moeda(valor: float | None) -> str:
    if valor is None:
        return "-"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_data(valor) -> str:
    """Formata uma data/timestamp para exibicao no texto do painel. Colunas
    timestamptz do Postgres voltam do psycopg como objetos datetime (nao
    string, diferente do SQLite antigo) - por isso este helper aceita tanto
    datetime (colunas timestamptz, ex: data_extracao/timestamp) quanto string
    (colunas text, ex: data_emissao) sem quebrar em nenhum dos dois casos."""

    if valor is None:
        return "-"
    if hasattr(valor, "strftime"):
        return valor.strftime("%Y-%m-%d %H:%M")
    return str(valor)


def barras_html(linhas: list[tuple[str, float]], fmt_valor) -> str:
    if not linhas:
        return "<p class='aviso-vazio'>Sem dados.</p>"
    maximo = max(valor for _, valor in linhas) or 1
    partes = []
    for rotulo, valor in linhas:
        largura_pct = round((valor / maximo) * 100, 1)
        partes.append(
            f"""<div class="barra-linha">
              <div class="barra-rotulo" title="{html.escape(rotulo)}">{html.escape(rotulo)}</div>
              <div class="barra-trilho"><div class="barra-preenchimento" style="width:{largura_pct}%"></div></div>
              <div class="barra-valor">{fmt_valor(valor)}</div>
            </div>"""
        )
    return "\n".join(partes)


def badge_tipo_alerta(tipo: str) -> str:
    classe_dot = "status-dot-critico" if tipo in TIPOS_ALERTA_CRITICOS else "status-dot-atencao"
    return f'<span class="badge"><span class="status-dot {classe_dot}"></span>{html.escape(tipo)}</span>'


def status_oc(tem_alerta: bool) -> str:
    if tem_alerta:
        return '<span class="status-dot status-dot-atencao"></span>Revisar'
    return '<span class="status-dot status-dot-ok"></span>OK'


def badge_tipo_faturamento(tipo: str | None) -> str:
    """Mostra a instrucao comercial extraida da observacao da OC (ver
    OrdemDeCompra.tipo_faturamento em schema.py) - nao e um alerta, so
    informacao logistica, por isso sem status-dot."""

    if not tipo:
        return '<span style="color: var(--muted); font-size: 12px;">-</span>'
    return f'<span class="badge">{html.escape(tipo.title())}</span>'


def link_documento(nome_arquivo: str | None) -> str:
    """Renderiza o nome do arquivo de origem como link clicavel para onde o
    PDF processado fica arquivado, se URL_PASTA_ENTRADA_OC estiver configurada
    no .env. Em producao, essa variavel aponta para a mesma pasta de
    PASTA_ENTRADA_OC, so que pelo link web (OneDrive/SharePoint) em vez do
    caminho local - abrir o link exige a autenticacao Microsoft de quem
    estiver acessando, que e o comportamento esperado (o documento fica
    protegido pelo controle de acesso do OneDrive/SharePoint da empresa; o
    painel HTML em si nunca guarda ou expõe o arquivo). Sem a variavel
    configurada (por exemplo, no modo demo), mostra so o nome do arquivo,
    sem link."""

    if not nome_arquivo:
        return "-"
    texto = html.escape(nome_arquivo)
    base = os.environ.get("URL_PASTA_ENTRADA_OC", "").strip().rstrip("/")
    if not base:
        return texto
    href = f"{base}/{quote(nome_arquivo)}"
    return f'<a href="{html.escape(href)}" target="_blank" rel="noopener">{texto}</a>'


def calcular_indicadores(conn) -> dict:
    """Calcula os indicadores executivos (aba Analytics): total de OCs, valor
    total acumulado, clientes distintos, ticket medio e quantas OCs tem algum
    alerta ativo. Funcao pura de leitura, sem efeito colateral - reaproveitada
    tanto pelo relatorio HTML estatico quanto pelas rotas do site."""

    total_ocs = conn.execute("SELECT COUNT(*) AS n FROM ordens_compra").fetchone()["n"]
    valor_total = conn.execute("SELECT SUM(valor_total) AS s FROM ordens_compra").fetchone()["s"] or 0.0
    clientes_distintos = conn.execute(
        "SELECT COUNT(DISTINCT cliente_id) AS n FROM ordens_compra"
    ).fetchone()["n"]
    ticket_medio = (valor_total / total_ocs) if total_ocs else 0.0
    ocs_com_alerta = conn.execute(
        """
        SELECT COUNT(*) AS n FROM ordens_compra
        WHERE status_extracao = 'possivel_duplicata'
           OR alerta_valor_divergente
           OR alerta_baixa_confianca
           OR alerta_cnpj_invalido
        """
    ).fetchone()["n"]

    return {
        "total_ocs": total_ocs,
        "valor_total": valor_total,
        "clientes_distintos": clientes_distintos,
        "ticket_medio": ticket_medio,
        "ocs_com_alerta": ocs_com_alerta,
    }
