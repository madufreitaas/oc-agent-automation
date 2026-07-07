"""
CSS compartilhado do painel de Ordens de Compra - usado tanto pelo gerador de
HTML estatico (report_generator.py) quanto pelas paginas do site (src/webapp),
para nao duplicar a mesma folha de estilo em dois lugares.

Paleta e especificacoes de marca seguem a skill de dataviz do projeto:
superficie clara/escura definida via custom properties, cores de status fixas
(nao tematicas) reservadas para os indicadores de severidade, barras com ponta
arredondada so no lado do dado (reta na base).
"""

CSS = """
:root {
  --surface-1: #fcfcfb; --page: #f9f9f7; --text-primary: #0b0b0b;
  --text-secondary: #52514e; --muted: #898781; --grid: #e1e0d9;
  --baseline: #c3c2b7; --border: rgba(11,11,11,0.10); --series-1: #2a78d6;
  --status-good: #0ca30c; --status-warning: #fab219; --status-critical: #d03b3b;
  --shadow: 0 1px 2px rgba(11,11,11,0.04), 0 1px 8px rgba(11,11,11,0.04);
}
@media (prefers-color-scheme: dark) {
  :root {
    --surface-1: #1a1a19; --page: #0d0d0d; --text-primary: #ffffff;
    --text-secondary: #c3c2b7; --muted: #898781; --grid: #2c2c2a;
    --baseline: #383835; --border: rgba(255,255,255,0.10); --series-1: #3987e5;
    --shadow: 0 1px 2px rgba(0,0,0,0.20), 0 1px 8px rgba(0,0,0,0.24);
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
body {
  margin: 0; background: var(--page); color: var(--text-primary);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  -webkit-font-smoothing: antialiased;
}
.container {
  max-width: 1240px; margin: 0 auto; padding: 32px;
}
@media (max-width: 720px) {
  .container { padding: 18px 14px; }
}
.cabecalho { margin-bottom: 24px; }
h1 { font-size: 24px; font-weight: 700; margin: 0 0 4px; letter-spacing: -0.01em; }
@media (max-width: 480px) {
  h1 { font-size: 20px; }
}
.subtitulo { color: var(--text-secondary); font-size: 13px; margin: 0; }
.eyebrow {
  font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--muted); margin: 0 0 6px;
}
.grid-cards {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 16px; margin-bottom: 28px;
}
.grid-2col {
  display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
}
@media (max-width: 860px) {
  .grid-2col { grid-template-columns: 1fr; }
}
.card {
  background: var(--surface-1); border: 1px solid var(--border); box-shadow: var(--shadow);
  border-radius: 12px; padding: 18px 20px;
}
.card .rotulo { font-size: 12px; color: var(--muted); margin-bottom: 8px; }
.card .valor {
  font-size: 27px; font-weight: 700; font-variant-numeric: proportional-nums;
  letter-spacing: -0.01em; word-break: break-word;
}
@media (max-width: 480px) {
  .card .valor { font-size: 22px; }
}
.secao {
  background: var(--surface-1); border: 1px solid var(--border); box-shadow: var(--shadow);
  border-radius: 12px; padding: 22px 24px; margin-bottom: 20px;
}
@media (max-width: 720px) {
  .secao { padding: 16px 16px; border-radius: 10px; }
}
.secao h2 { font-size: 15px; font-weight: 700; margin: 0 0 16px; color: var(--text-primary); }
.secao-auditoria {
  background: transparent; border: 1px dashed var(--border); box-shadow: none;
}
.secao-auditoria h2 { color: var(--muted); font-size: 13px; }
.barra-linha { display: flex; align-items: center; gap: 10px; margin-bottom: 11px; }
.barra-linha:last-child { margin-bottom: 0; }
.barra-rotulo {
  flex: 0 0 38%; font-size: 12px; color: var(--text-secondary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
@media (max-width: 480px) {
  .barra-rotulo { flex-basis: 30%; }
}
.barra-trilho { flex: 1; background: var(--grid); border-radius: 4px; height: 8px; min-width: 40px; }
.barra-preenchimento {
  background: var(--series-1); height: 8px; border-radius: 0 4px 4px 0; min-width: 2px;
}
.barra-valor {
  flex: 0 0 auto; font-size: 12px; color: var(--text-primary); font-weight: 600;
  font-variant-numeric: tabular-nums; min-width: 72px; text-align: right;
}
.tabela-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td {
  text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--grid);
  white-space: nowrap;
}
th {
  color: var(--muted); font-weight: 600; font-size: 11px; text-transform: uppercase;
  letter-spacing: 0.03em;
}
tbody tr:hover td { background: var(--page); }
td.numero { text-align: right; font-variant-numeric: tabular-nums; }
.col-opcional { }
@media (max-width: 640px) {
  .col-opcional { display: none; }
}
footer { color: var(--muted); font-size: 12px; margin-top: 12px; }
.barra-acoes { display: flex; gap: 10px; margin-bottom: 24px; flex-wrap: wrap; }
.btn {
  background: var(--series-1); color: #ffffff; border: none; border-radius: 8px;
  padding: 10px 16px; font-size: 13px; font-weight: 600; cursor: pointer;
  font-family: inherit; min-height: 38px;
}
.btn:hover { opacity: 0.88; }
.btn:active { opacity: 0.78; }
.btn-secundario {
  background: var(--surface-1); color: var(--text-primary); border: 1px solid var(--border);
}
@media (max-width: 480px) {
  .barra-acoes { flex-direction: column; }
  .btn { width: 100%; }
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
.menu-abas {
  display: flex; gap: 4px; margin-bottom: 24px; border-bottom: 1px solid var(--border);
  overflow-x: auto;
}
.menu-item {
  background: none; border: none; font: inherit; font-family: inherit;
  font-weight: 600; font-size: 13px; color: var(--muted); white-space: nowrap;
  padding: 10px 4px; margin-right: 22px; cursor: pointer;
  border-bottom: 2px solid transparent; margin-bottom: -1px;
}
.menu-item:hover { color: var(--text-primary); }
.menu-item-ativo { color: var(--text-primary); border-bottom-color: var(--series-1); }
.aba { display: none; }
.aba-ativa { display: block; }
@media print {
  .barra-acoes { display: none; }
  .menu-abas { display: none; }
  .aba { display: block; }
  .card, .secao { box-shadow: none; }
  body { background: #ffffff; }
}
"""
