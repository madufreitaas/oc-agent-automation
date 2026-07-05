"""
Gera o painel HTML autocontido (sem dependencias externas/CDN) a partir do
banco SQLite, no estilo cards que a Madu ja usa em medidas HTML no Power BI.

Estrutura pensada para leitura executiva de cima para baixo: indicadores e
graficos de negocio primeiro, tabela operacional das OCs recentes em
seguida, uma central unica de alertas de qualidade de dado (nunca corrigidos
ou excluidos automaticamente - ver docs/boas_praticas_e_governanca.md), e
por fim uma secao de auditoria/log, visualmente discreta, para quem precisar
investigar o historico completo.

Nao inclui nenhum dado de dados_clinicos (tabela sensivel/LGPD) - o painel
e estritamente comercial/financeiro.
"""

from __future__ import annotations

import html
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import database
from export_csv import gerar_csv_string

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

# Tipos de alerta considerados criticos (erro deterministico, sem ambiguidade)
# vs os demais, que sao sinalizacoes de julgamento (precisam de revisao, mas
# podem ser legitimos). So muda a cor do badge, nunca o tratamento: nenhum
# alerta, de nenhum tipo, e corrigido ou excluido automaticamente.
TIPOS_ALERTA_CRITICOS = {"CNPJ invalido"}

# Paleta (ver skill de dataviz): superficie clara/escura, tinta, serie 1 = azul,
# cores de status fixas (nao tematicas) para os indicadores de severidade.
CSS = """
:root {
  --surface-1: #fcfcfb; --page: #f9f9f7; --text-primary: #0b0b0b;
  --text-secondary: #52514e; --muted: #898781; --grid: #e1e0d9;
  --baseline: #c3c2b7; --border: rgba(11,11,11,0.10); --series-1: #2a78d6;
  --status-good: #0ca30c; --status-warning: #fab219; --status-critical: #d03b3b;
}
@media (prefers-color-scheme: dark) {
  :root {
    --surface-1: #1a1a19; --page: #0d0d0d; --text-primary: #ffffff;
    --text-secondary: #c3c2b7; --muted: #898781; --grid: #2c2c2a;
    --baseline: #383835; --border: rgba(255,255,255,0.10); --series-1: #3987e5;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 32px; background: var(--page); color: var(--text-primary);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}
.cabecalho { margin-bottom: 24px; }
h1 { font-size: 24px; font-weight: 700; margin: 0 0 4px; letter-spacing: -0.01em; }
.subtitulo { color: var(--text-secondary); font-size: 13px; margin: 0; }
.eyebrow {
  font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--muted); margin: 0 0 6px;
}
.grid-cards {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px; margin-bottom: 28px;
}
.grid-2col {
  display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
}
@media (max-width: 860px) {
  .grid-2col { grid-template-columns: 1fr; }
}
.card {
  background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 12px; padding: 18px 20px;
}
.card .rotulo { font-size: 12px; color: var(--muted); margin-bottom: 8px; }
.card .valor {
  font-size: 27px; font-weight: 700; font-variant-numeric: proportional-nums;
  letter-spacing: -0.01em;
}
.secao {
  background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 12px; padding: 22px 24px; margin-bottom: 20px;
  overflow-x: auto;
}
.secao h2 { font-size: 15px; font-weight: 700; margin: 0 0 16px; color: var(--text-primary); }
.secao-auditoria {
  background: transparent; border: 1px dashed var(--border);
}
.secao-auditoria h2 { color: var(--muted); font-size: 13px; }
.barra-linha { display: flex; align-items: center; gap: 10px; margin-bottom: 11px; }
.barra-linha:last-child { margin-bottom: 0; }
.barra-rotulo {
  flex: 0 0 42%; font-size: 12px; color: var(--text-secondary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.barra-trilho { flex: 1; background: var(--grid); border-radius: 4px; height: 8px; }
.barra-preenchimento {
  background: var(--series-1); height: 8px; border-radius: 4px;
}
.barra-valor {
  flex: 0 0 auto; font-size: 12px; color: var(--text-primary); font-weight: 600;
  font-variant-numeric: tabular-nums; min-width: 84px; text-align: right;
}
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td {
  text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--grid);
  white-space: nowrap;
}
th {
  color: var(--muted); font-weight: 600; font-size: 11px; text-transform: uppercase;
  letter-spacing: 0.03em;
}
td.numero { text-align: right; font-variant-numeric: tabular-nums; }
footer { color: var(--muted); font-size: 12px; margin-top: 12px; }
.barra-acoes { display: flex; gap: 10px; margin-bottom: 24px; flex-wrap: wrap; }
.btn {
  background: var(--series-1); color: #ffffff; border: none; border-radius: 8px;
  padding: 9px 16px; font-size: 13px; font-weight: 600; cursor: pointer;
  font-family: inherit;
}
.btn:hover { opacity: 0.88; }
.btn-secundario {
  background: var(--surface-1); color: var(--text-primary); border: 1px solid var(--border);
}
.banner-alerta {
  display: flex; align-items: center; gap: 10px; font-size: 13px; font-weight: 500;
  background: var(--surface-1); border: 1px solid var(--border);
  border-left: 4px solid var(--status-critical); border-radius: 8px; padding: 12px 16px;
  margin-bottom: 20px; color: var(--text-primary);
}
.aviso-vazio { color: var(--muted); font-size: 13px; margin: 0; }
.status-dot {
  display: inline-block; width: 9px; height: 9px; border-radius: 50%;
  margin-right: 7px; vertical-align: middle; flex-shrink: 0;
}
.status-dot-ok { background: var(--status-good); }
.status-dot-atencao { background: var(--status-warning); }
.status-dot-critico { background: var(--status-critical); }
.badge {
  display: inline-flex; align-items: center; white-space: nowrap;
  padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 600;
  color: var(--text-primary); background: var(--page); border: 1px solid var(--border);
}
.governanca p { font-size: 13px; color: var(--text-secondary); line-height: 1.6; margin: 0 0 10px; }
.governanca p:last-child { margin-bottom: 0; }
"""


def _js_string(texto: str) -> str:
    """Serializa uma string Python para uso seguro dentro de um <script>,
    evitando que a sequencia '</script' feche a tag por engano."""

    return json.dumps(texto).replace("</", "<\\/")


def _fmt_moeda(valor: float | None) -> str:
    if valor is None:
        return "-"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _barras_html(linhas: list[tuple[str, float]], fmt_valor) -> str:
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


def _badge_tipo_alerta(tipo: str) -> str:
    classe_dot = "status-dot-critico" if tipo in TIPOS_ALERTA_CRITICOS else "status-dot-atencao"
    return f'<span class="badge"><span class="status-dot {classe_dot}"></span>{html.escape(tipo)}</span>'


def _status_oc(tem_alerta: bool) -> str:
    if tem_alerta:
        return '<span class="status-dot status-dot-atencao"></span>Revisar'
    return '<span class="status-dot status-dot-ok"></span>OK'


def gerar_relatorio(db_path: str | Path = database.DB_PADRAO_PATH, saida: str | Path = SAIDA_PADRAO) -> Path:
    conn = database.conectar(db_path)
    conn.row_factory = sqlite3.Row

    total_ocs = conn.execute("SELECT COUNT(*) AS n FROM ordens_compra").fetchone()["n"]
    valor_total = conn.execute("SELECT SUM(valor_total) AS s FROM ordens_compra").fetchone()["s"] or 0.0
    clientes_distintos = conn.execute("SELECT COUNT(DISTINCT cliente_id) AS n FROM ordens_compra").fetchone()["n"]
    ticket_medio = (valor_total / total_ocs) if total_ocs else 0.0
    ocs_com_alerta = conn.execute(
        """
        SELECT COUNT(*) AS n FROM ordens_compra
        WHERE status_extracao = 'possivel_duplicata'
           OR alerta_valor_divergente = 1
           OR alerta_baixa_confianca = 1
           OR alerta_cnpj_invalido = 1
        """
    ).fetchone()["n"]

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
               (oc.status_extracao = 'possivel_duplicata' OR oc.alerta_valor_divergente = 1
                OR oc.alerta_baixa_confianca = 1 OR oc.alerta_cnpj_invalido = 1) AS tem_alerta
        FROM ordens_compra oc JOIN clientes c ON c.id = oc.cliente_id
        ORDER BY oc.data_extracao DESC LIMIT 15
        """
    ).fetchall()

    central_alertas = conn.execute(Path(QUERY_CENTRAL_ALERTAS).read_text(encoding="utf-8")).fetchall()
    log_extracao = conn.execute(
        "SELECT arquivo, timestamp, status, confianca, erro FROM log_extracao ORDER BY timestamp DESC LIMIT 30"
    ).fetchall()
    falhas_recentes = conn.execute(
        "SELECT COUNT(*) AS n FROM log_extracao WHERE status LIKE 'erro%' AND timestamp >= datetime('now', '-1 day')"
    ).fetchone()["n"]

    csv_ordens_compra = gerar_csv_string(QUERY_ORDENS_COMPRA, db_path)
    csv_itens_por_oc = gerar_csv_string(QUERY_ITENS_POR_OC, db_path)
    csv_central_alertas = gerar_csv_string(QUERY_CENTRAL_ALERTAS, db_path)
    csv_log_extracao = gerar_csv_string(QUERY_LOG_EXTRACAO, db_path)

    conn.close()

    gerado_em = datetime.now().strftime("%Y-%m-%d %H:%M")

    linhas_tabela = "\n".join(
        f"""<tr>
              <td>{html.escape(row['numero_oc'])}</td>
              <td>{html.escape(row['data_emissao'] or '-')}</td>
              <td>{html.escape(row['cliente'])}</td>
              <td class="numero">{_fmt_moeda(row['valor_total'])}</td>
              <td>{html.escape(row['layout_origem'] or '-')}</td>
              <td>{_status_oc(bool(row['tem_alerta']))}</td>
            </tr>"""
        for row in ocs_recentes
    )

    linhas_alertas = "\n".join(
        f"""<tr>
              <td>{_badge_tipo_alerta(row['tipo'])}</td>
              <td>{html.escape(row['numero_oc'])}</td>
              <td>{html.escape(row['cliente'])}</td>
              <td>{html.escape(row['detalhe'])}</td>
              <td>{html.escape(row['arquivo_origem'] or '-')}</td>
              <td>{html.escape(row['data_extracao'] or '-')}</td>
            </tr>"""
        for row in central_alertas
    )

    linhas_log = "\n".join(
        f"""<tr>
              <td>{html.escape(row['arquivo'])}</td>
              <td>{html.escape(row['timestamp'] or '-')}</td>
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

    classe_dot_alerta_kpi = "status-dot-ok" if ocs_com_alerta == 0 else "status-dot-atencao"

    corpo = f"""
<div class="cabecalho">
  <p class="eyebrow">MDR / Mederi &middot; extraido automaticamente via oc-agent-automation</p>
  <h1>Painel de Ordens de Compra</h1>
  <p class="subtitulo">Atualizado em {gerado_em}</p>
</div>

{banner_falhas}

<div class="barra-acoes">
  <button class="btn" onclick="baixarCSV('ordens_compra.csv', CSV_ORDENS_COMPRA)">Baixar OCs (CSV)</button>
  <button class="btn btn-secundario" onclick="baixarCSV('itens_por_oc.csv', CSV_ITENS_POR_OC)">Baixar itens por OC (CSV)</button>
  <button class="btn btn-secundario" onclick="baixarCSV('alertas.csv', CSV_CENTRAL_ALERTAS)">Baixar alertas (CSV)</button>
  <button class="btn btn-secundario" onclick="baixarCSV('log_extracao.csv', CSV_LOG_EXTRACAO)">Baixar log de extracao (CSV)</button>
</div>

<div class="grid-cards">
  <div class="card"><div class="rotulo">Total de OCs processadas</div><div class="valor">{total_ocs}</div></div>
  <div class="card"><div class="rotulo">Valor total acumulado</div><div class="valor">{_fmt_moeda(valor_total)}</div></div>
  <div class="card"><div class="rotulo">Ticket medio por OC</div><div class="valor">{_fmt_moeda(ticket_medio)}</div></div>
  <div class="card"><div class="rotulo">Clientes distintos</div><div class="valor">{clientes_distintos}</div></div>
  <div class="card"><div class="rotulo">OCs com alerta</div><div class="valor"><span class="status-dot {classe_dot_alerta_kpi}"></span>{ocs_com_alerta}</div></div>
</div>

<div class="grid-2col">
  <div class="secao">
    <h2>Valor total por cliente</h2>
    {_barras_html([(r['cliente'], r['total'] or 0.0) for r in por_cliente], _fmt_moeda)}
  </div>

  <div class="secao">
    <h2>Itens mais recorrentes (quantidade total)</h2>
    {_barras_html([(r['descricao'], r['qtd'] or 0.0) for r in itens_recorrentes], lambda v: f"{v:g}")}
  </div>
</div>

<div class="secao">
  <h2>Ordens de compra recentes</h2>
  <table>
    <thead><tr><th>Numero OC</th><th>Emissao</th><th>Cliente</th><th>Valor total</th><th>Layout</th><th>Status</th></tr></thead>
    <tbody>{linhas_tabela}</tbody>
  </table>
  <footer>Dados clinicos (paciente, convenio, cirurgiao) nao sao exibidos neste painel por serem informacao sensivel (LGPD).</footer>
</div>

<div class="secao">
  <h2>Central de alertas</h2>
  {(
    "<p class='aviso-vazio'>Nenhum alerta ativo. Todos os dados estao prontos para uso.</p>"
    if not central_alertas else
    f'''<div class="banner-alerta" style="border-left-color: var(--status-warning);">&#9888; {len(central_alertas)} item(ns) sinalizado(s) para revisao (duplicidade, valor divergente, baixa confianca ou CNPJ invalido). Nada foi corrigido ou excluido automaticamente.</div>
    <table>
      <thead><tr><th>Tipo</th><th>Numero OC</th><th>Cliente</th><th>Detalhe</th><th>Arquivo</th><th>Extraido em</th></tr></thead>
      <tbody>{linhas_alertas}</tbody>
    </table>'''
  )}
</div>

<div class="secao secao-auditoria">
  <h2>Auditoria e governanca</h2>
  <div class="governanca">
    <p>Este painel e gerado automaticamente a partir de PDFs de Ordens de Compra, extraidos por um modelo de linguagem (LLM) via OpenRouter (o modelo especifico e configuravel, ver OPENROUTER_MODEL no .env). Cada extracao e validada contra um schema fixo antes de entrar no banco, com retry automatico em caso de falha transitoria de rede.</p>
    <p>Dados de saude do paciente (quando presentes na observacao da OC) ficam isolados na tabela dados_clinicos, separada das tabelas comerciais, e nao aparecem em nenhuma consulta, exportacao ou secao deste painel.</p>
    <p>Um arquivo que falha repetidamente e movido para uma pasta de quarentena em vez de ser tentado para sempre. O log abaixo mostra as ultimas tentativas de extracao (sucesso e falha), com o arquivo, data/hora, status, confianca do modelo e o erro registrado quando houve falha.</p>
  </div>
  <table>
    <thead><tr><th>Arquivo</th><th>Data/hora</th><th>Status</th><th>Confianca</th><th>Erro</th></tr></thead>
    <tbody>{linhas_log}</tbody>
  </table>
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
</script>
"""

    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(
        f"<!doctype html><html lang='pt-br'><head><meta charset='utf-8'>"
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
    parser.add_argument("--db", default=None, help="Sobrepoe o caminho do banco SQLite.")
    parser.add_argument("--saida", default=None, help="Sobrepoe o caminho do HTML gerado.")
    args = parser.parse_args()

    db_padrao = database.DB_DEMO_PATH if args.modo == "demo" else database.DB_PADRAO_PATH
    saida_padrao = SAIDA_DEMO if args.modo == "demo" else SAIDA_PADRAO

    caminho = gerar_relatorio(db_path=args.db or db_padrao, saida=args.saida or saida_padrao)
    print(f"Relatorio gerado em {caminho}")
