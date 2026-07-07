"""
Gera o painel HTML autocontido (sem dependencias externas/CDN) a partir do
Postgres do Supabase, no estilo cards que a Madu ja usa em medidas HTML no
Power BI.

O CSS e os helpers de formatacao/HTML (fmt_moeda, barras_html,
badge_tipo_alerta, status_oc, link_documento, calcular_indicadores) ficam em
src/estilo_painel.py e src/formatacao_painel.py, compartilhados com as rotas
do site (src/webapp) - para nao duplicar a mesma logica em dois lugares.

O painel e organizado em abas (trocadas via JS, sem reload de pagina):
"Analytics" (indicadores e graficos de negocio, leitura executiva) e
"Detalhada" (exportacao CSV, tabela de OCs recentes, central unica de alertas
de qualidade de dado - nunca corrigidos ou excluidos automaticamente, ver
docs/boas_praticas_e_governanca.md - e a secao de auditoria/log).

Deliberadamente NAO existe uma aba mostrando o PDF/imagem do documento em si:
em producao, esses arquivos tem dado de saude do paciente (LGPD), entao nunca
devem ficar embutidos neste painel. Em vez disso, cada linha que referencia um
arquivo de origem vira um link clicavel (ver formatacao_painel.link_documento)
para onde o documento fica arquivado - em producao, isso aponta para a pasta
no OneDrive/SharePoint da empresa (URL_PASTA_ENTRADA_OC no .env), entao abrir
o link exige a autenticacao Microsoft de quem estiver acessando; o arquivo em
si nunca fica guardado ou exposto pelo painel.

Nao inclui nenhum dado de dados_clinicos (tabela sensivel/LGPD) - o painel
e estritamente comercial/financeiro.
"""

from __future__ import annotations

import html
import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

import database
from estilo_painel import CSS
from export_csv import gerar_csv_string
from formatacao_painel import (
    badge_tipo_alerta,
    barras_html,
    calcular_indicadores,
    fmt_data,
    fmt_moeda,
    link_documento,
    status_oc,
)

# Carregado aqui (topo do modulo, nao dentro de __main__) para garantir que o
# .env ja esteja lido antes de qualquer os.environ.get() neste arquivo -
# inclusive os que rodam no import (LIMITE_ALERTA_FALHAS_RECENTES abaixo).
# Chamar load_dotenv() de novo nao tem custo se outro script (ex:
# pipeline.py) ja tiver carregado o .env antes de importar este modulo.
load_dotenv()

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
SAIDA_PADRAO = RAIZ_PROJETO / "output" / "report" / "relatorio.html"
SAIDA_DEMO = RAIZ_PROJETO / "output" / "report" / "relatorio_demo.html"
QUERY_ORDENS_COMPRA = RAIZ_PROJETO / "sql" / "queries" / "exportar_csv_ordens_compra.sql"
QUERY_ITENS_POR_OC = RAIZ_PROJETO / "sql" / "queries" / "itens_por_oc.sql"
QUERY_CENTRAL_ALERTAS = RAIZ_PROJETO / "sql" / "queries" / "central_alertas.sql"
QUERY_LOG_EXTRACAO = RAIZ_PROJETO / "sql" / "queries" / "log_extracao.sql"

# Mesmo limite usado em pipeline.py (LIMITE_ALERTA_FALHAS) para decidir se o
# painel mostra um banner de alerta de falhas recentes (ultimas 24h).
LIMITE_ALERTA_FALHAS_RECENTES = int(os.environ.get("LIMITE_ALERTA_FALHAS", "3"))


def _js_string(texto: str) -> str:
    """Serializa uma string Python para uso seguro dentro de um <script>,
    evitando que a sequencia '</script' feche a tag por engano."""

    return json.dumps(texto).replace("</", "<\\/")


def gerar_relatorio(
    dsn: str,
    saida: str | Path = SAIDA_PADRAO,
) -> Path:
    conn = database.conectar(dsn)

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

    ocs_recentes = conn.execute(
        """
        SELECT oc.numero_oc, oc.data_emissao, c.nome AS cliente, oc.valor_total, oc.layout_origem,
               oc.arquivo_origem,
               (oc.status_extracao = 'possivel_duplicata' OR oc.alerta_valor_divergente
                OR oc.alerta_baixa_confianca OR oc.alerta_cnpj_invalido) AS tem_alerta
        FROM ordens_compra oc JOIN clientes c ON c.id = oc.cliente_id
        ORDER BY oc.data_extracao DESC LIMIT 15
        """
    ).fetchall()

    central_alertas = conn.execute(Path(QUERY_CENTRAL_ALERTAS).read_text(encoding="utf-8")).fetchall()
    log_extracao = conn.execute(
        "SELECT arquivo, timestamp, status, confianca, erro FROM log_extracao ORDER BY timestamp DESC LIMIT 30"
    ).fetchall()
    falhas_recentes = conn.execute(
        "SELECT COUNT(*) AS n FROM log_extracao WHERE status LIKE %s AND timestamp >= now() - interval '1 day'",
        ("erro%",),
    ).fetchone()["n"]

    csv_ordens_compra = gerar_csv_string(QUERY_ORDENS_COMPRA, dsn)
    csv_itens_por_oc = gerar_csv_string(QUERY_ITENS_POR_OC, dsn)
    csv_central_alertas = gerar_csv_string(QUERY_CENTRAL_ALERTAS, dsn)
    csv_log_extracao = gerar_csv_string(QUERY_LOG_EXTRACAO, dsn)

    conn.close()

    gerado_em = datetime.now().strftime("%Y-%m-%d %H:%M")

    linhas_tabela = "\n".join(
        f"""<tr>
              <td>{html.escape(row['numero_oc'])}</td>
              <td class="col-opcional">{html.escape(row['data_emissao'] or '-')}</td>
              <td>{html.escape(row['cliente'])}</td>
              <td class="numero">{fmt_moeda(row['valor_total'])}</td>
              <td class="col-opcional">{html.escape(row['layout_origem'] or '-')}</td>
              <td>{status_oc(bool(row['tem_alerta']))}</td>
              <td>{link_documento(row['arquivo_origem'])}</td>
            </tr>"""
        for row in ocs_recentes
    )

    linhas_alertas = "\n".join(
        f"""<tr>
              <td>{badge_tipo_alerta(row['tipo'])}</td>
              <td>{html.escape(row['numero_oc'])}</td>
              <td>{html.escape(row['cliente'])}</td>
              <td>{html.escape(row['detalhe'])}</td>
              <td class="col-opcional">{link_documento(row['arquivo_origem'])}</td>
              <td class="col-opcional">{html.escape(fmt_data(row['data_extracao']))}</td>
            </tr>"""
        for row in central_alertas
    )

    linhas_log = "\n".join(
        f"""<tr>
              <td>{link_documento(row['arquivo'])}</td>
              <td>{html.escape(fmt_data(row['timestamp']))}</td>
              <td>{html.escape(row['status'])}</td>
              <td class="numero">{f"{row['confianca']:.2f}" if row['confianca'] is not None else '-'}</td>
              <td>{html.escape(row['erro'] or '-')}</td>
            </tr>"""
        for row in log_extracao
    )

    banner_falhas = (
        f'<div class="banner-alerta">&#9888; {falhas_recentes} falha(s) de extracao nas ultimas 24 horas '
        f'(limite de alerta: {LIMITE_ALERTA_FALHAS_RECENTES}). Veja a secao de auditoria no final da pagina.</div>'
        if falhas_recentes >= LIMITE_ALERTA_FALHAS_RECENTES
        else ""
    )

    classe_dot_alerta_kpi = "status-dot-ok" if indicadores["ocs_com_alerta"] == 0 else "status-dot-atencao"

    corpo = f"""
<div class="container">
<div class="cabecalho">
  <p class="eyebrow">MDR / Mederi &middot; extraido automaticamente via oc-agent-automation</p>
  <h1>Painel de Ordens de Compra</h1>
  <p class="subtitulo">Atualizado em {gerado_em}</p>
</div>

{banner_falhas}

<div class="menu-abas">
  <button class="menu-item menu-item-ativo" id="menu-analytics" onclick="mostrarAba('analytics')">Analytics</button>
  <button class="menu-item" id="menu-detalhada" onclick="mostrarAba('detalhada')">Detalhada</button>
</div>

<div class="aba aba-ativa" id="aba-analytics">
  <div class="grid-cards">
    <div class="card"><div class="rotulo">Total de OCs processadas</div><div class="valor">{indicadores["total_ocs"]}</div></div>
    <div class="card"><div class="rotulo">Valor total acumulado</div><div class="valor">{fmt_moeda(indicadores["valor_total"])}</div></div>
    <div class="card"><div class="rotulo">Ticket medio por OC</div><div class="valor">{fmt_moeda(indicadores["ticket_medio"])}</div></div>
    <div class="card"><div class="rotulo">Clientes distintos</div><div class="valor">{indicadores["clientes_distintos"]}</div></div>
    <div class="card"><div class="rotulo">OCs com alerta</div><div class="valor"><span class="status-dot {classe_dot_alerta_kpi}"></span>{indicadores["ocs_com_alerta"]}</div></div>
  </div>

  <div class="grid-2col">
    <div class="secao">
      <h2>Valor total por cliente</h2>
      {barras_html([(r['cliente'], r['total'] or 0.0) for r in por_cliente], fmt_moeda)}
    </div>

    <div class="secao">
      <h2>Itens mais recorrentes (quantidade total)</h2>
      {barras_html([(r['descricao'], r['qtd'] or 0.0) for r in itens_recorrentes], lambda v: f"{v:g}")}
    </div>
  </div>
</div>

<div class="aba" id="aba-detalhada">
  <div class="barra-acoes">
    <button class="btn" onclick="baixarCSV('ordens_compra.csv', CSV_ORDENS_COMPRA)">Baixar OCs (CSV)</button>
    <button class="btn btn-secundario" onclick="baixarCSV('itens_por_oc.csv', CSV_ITENS_POR_OC)">Baixar itens por OC (CSV)</button>
    <button class="btn btn-secundario" onclick="baixarCSV('alertas.csv', CSV_CENTRAL_ALERTAS)">Baixar alertas (CSV)</button>
    <button class="btn btn-secundario" onclick="baixarCSV('log_extracao.csv', CSV_LOG_EXTRACAO)">Baixar log de extracao (CSV)</button>
  </div>

  <div class="secao">
    <h2>Ordens de compra recentes</h2>
    <div class="tabela-scroll">
    <table>
      <thead><tr><th>Numero OC</th><th class="col-opcional">Emissao</th><th>Cliente</th><th>Valor total</th><th class="col-opcional">Layout</th><th>Status</th><th>Documento</th></tr></thead>
      <tbody>{linhas_tabela}</tbody>
    </table>
    </div>
    <footer>Dados clinicos (paciente, convenio, cirurgiao) nao sao exibidos neste painel por serem informacao sensivel (LGPD).</footer>
  </div>

  <div class="secao">
    <h2>Central de alertas</h2>
    {(
      "<p class='aviso-vazio'>Nenhum alerta ativo. Todos os dados estao prontos para uso.</p>"
      if not central_alertas else
      f'''<div class="banner-alerta" style="border-left-color: var(--status-warning);">&#9888; {len(central_alertas)} item(ns) sinalizado(s) para revisao (duplicidade, valor divergente, baixa confianca ou CNPJ invalido). Nada foi corrigido ou excluido automaticamente.</div>
      <div class="tabela-scroll">
      <table>
        <thead><tr><th>Tipo</th><th>Numero OC</th><th>Cliente</th><th>Detalhe</th><th class="col-opcional">Arquivo</th><th class="col-opcional">Extraido em</th></tr></thead>
        <tbody>{linhas_alertas}</tbody>
      </table>
      </div>'''
    )}
  </div>

  <div class="secao secao-auditoria">
    <h2>Auditoria e governanca</h2>
    <div class="governanca">
      <p>Este painel e gerado automaticamente a partir de PDFs de Ordens de Compra, extraidos por um modelo de linguagem (LLM) via OpenRouter (o modelo especifico e configuravel, ver OPENROUTER_MODEL no .env). Cada extracao e validada contra um schema fixo antes de entrar no banco, com retry automatico em caso de falha transitoria de rede.</p>
      <p>Dados de saude do paciente (quando presentes na observacao da OC) ficam isolados na tabela dados_clinicos, separada das tabelas comerciais, e nao aparecem em nenhuma consulta, exportacao ou secao deste painel.</p>
      <p>Um arquivo que falha repetidamente e movido para uma pasta de quarentena em vez de ser tentado para sempre. O log abaixo mostra as ultimas tentativas de extracao (sucesso e falha), com o arquivo, data/hora, status, confianca do modelo e o erro registrado quando houve falha.</p>
    </div>
    <div class="tabela-scroll">
    <table>
      <thead><tr><th>Arquivo</th><th>Data/hora</th><th>Status</th><th>Confianca</th><th>Erro</th></tr></thead>
      <tbody>{linhas_log}</tbody>
    </table>
    </div>
  </div>
</div>
</div>

<script>
const CSV_ORDENS_COMPRA = {_js_string(csv_ordens_compra)};
const CSV_ITENS_POR_OC = {_js_string(csv_itens_por_oc)};
const CSV_CENTRAL_ALERTAS = {_js_string(csv_central_alertas)};
const CSV_LOG_EXTRACAO = {_js_string(csv_log_extracao)};

function baixarCSV(nomeArquivo, conteudo) {{
  const bom = '\\ufeff'; // BOM UTF-8, para o Excel abrir acentos corretamente
  const blob = new Blob([bom + conteudo], {{ type: 'text/csv;charset=utf-8;' }});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = nomeArquivo;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}}

function mostrarAba(nome) {{
  document.querySelectorAll('.aba').forEach(function(el) {{ el.classList.remove('aba-ativa'); }});
  document.querySelectorAll('.menu-item').forEach(function(el) {{ el.classList.remove('menu-item-ativo'); }});
  document.getElementById('aba-' + nome).classList.add('aba-ativa');
  document.getElementById('menu-' + nome).classList.add('menu-item-ativo');
}}
</script>
"""

    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(
        f"<!doctype html><html lang='pt-br'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<meta name='color-scheme' content='light dark'>"
        f"<title>Painel de Ordens de Compra</title><style>{CSS}</style></head>"
        f"<body>{corpo}</body></html>",
        encoding="utf-8",
    )
    return saida


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gera o painel HTML de Ordens de Compra")
    parser.add_argument(
        "--modo",
        choices=["demo", "producao"],
        default="demo",
        help=(
            "demo (padrao): le o banco de demonstracao e gera relatorio_demo.html. "
            "producao: le o banco real e gera relatorio.html."
        ),
    )
    parser.add_argument("--dsn", default=None, help="Sobrepoe a string de conexao Postgres.")
    parser.add_argument("--saida", default=None, help="Sobrepoe o caminho do HTML gerado.")
    args = parser.parse_args()

    dsn_padrao = database.dsn_demo() if args.modo == "demo" else database.dsn_producao()
    saida_padrao = SAIDA_DEMO if args.modo == "demo" else SAIDA_PADRAO

    caminho = gerar_relatorio(dsn=args.dsn or dsn_padrao, saida=args.saida or saida_padrao)
    print(f"Relatorio gerado em {caminho}")
