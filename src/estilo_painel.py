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
  --surface-1: #fcfcfb; --surface-2: #f3f2ee; --page: #f9f9f7; --text-primary: #0b0b0b;
  --text-secondary: #52514e; --muted: #898781; --grid: #e1e0d9;
  --baseline: #c3c2b7; --border: rgba(11,11,11,0.10); --series-1: #2a78d6;
  --status-good: #0ca30c; --status-warning: #fab219; --status-critical: #d03b3b;
  --shadow: 0 1px 2px rgba(11,11,11,0.04), 0 1px 8px rgba(11,11,11,0.04);
  --shadow-lift: 0 4px 10px rgba(11,11,11,0.06), 0 1px 3px rgba(11,11,11,0.06);
  /* --brand e a cor de identidade visual (sidebar, botoes, links ativos) - por
     pedido de marca, usa o mesmo azul dos graficos (--series-1) em vez de uma
     cor separada, entao os dois tokens ficam iguais de proposito aqui. */
  --brand: var(--series-1); --brand-hover: color-mix(in srgb, var(--series-1) 78%, black);
  --brand-soft: color-mix(in srgb, var(--series-1) 12%, transparent);
  --brand-contrast: #ffffff;
}
@media (prefers-color-scheme: dark) {
  :root {
    --surface-1: #1a1a19; --surface-2: #141413; --page: #0d0d0d; --text-primary: #ffffff;
    --text-secondary: #c3c2b7; --muted: #898781; --grid: #2c2c2a;
    --baseline: #383835; --border: rgba(255,255,255,0.10); --series-1: #3987e5;
    --shadow: 0 1px 2px rgba(0,0,0,0.20), 0 1px 8px rgba(0,0,0,0.24);
    --shadow-lift: 0 6px 16px rgba(0,0,0,0.32), 0 1px 3px rgba(0,0,0,0.28);
    --brand: var(--series-1); --brand-hover: color-mix(in srgb, var(--series-1) 80%, white);
    --brand-soft: color-mix(in srgb, var(--series-1) 16%, transparent);
    --brand-contrast: #ffffff;
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
  background: var(--brand); color: var(--brand-contrast); border: none; border-radius: 8px;
  padding: 10px 16px; font-size: 13px; font-weight: 600; cursor: pointer;
  font-family: inherit; min-height: 38px;
}
.btn:hover { background: var(--brand-hover); }
.btn:active { opacity: 0.85; }
.btn:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
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

/* --- App shell (webapp/templates/base.html) -------------------------------
   Layout de sidebar exclusivo do site (FastAPI + Jinja). O relatorio estatico
   gerado por report_generator.py monta seu proprio HTML e continua usando
   .container/.cabecalho/.menu-abas acima - nenhuma classe deste bloco existe
   la, entao as duas telas evoluem sem se afetar. */
.app-shell { display: flex; min-height: 100vh; }
.sidebar {
  flex: 0 0 232px; background: var(--surface-2); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; padding: 22px 16px;
  position: sticky; top: 0; height: 100vh;
}
.sidebar-brand { display: flex; align-items: center; gap: 10px; padding: 0 8px 22px; }
.sidebar-brand .marca-icone {
  width: 30px; height: 30px; border-radius: 8px; flex-shrink: 0;
  background: linear-gradient(135deg, var(--brand), color-mix(in srgb, var(--brand) 55%, black));
}
.sidebar-brand .marca-texto { min-width: 0; }
.sidebar-brand .eyebrow { margin: 0 0 2px; }
.sidebar-brand h1 { font-size: 15px; margin: 0; line-height: 1.2; }
.sidebar-nav { display: flex; flex-direction: column; gap: 2px; flex: 1; }
.nav-item {
  display: flex; align-items: center; gap: 10px; padding: 9px 10px; border-radius: 8px;
  font-size: 13px; font-weight: 600; color: var(--text-secondary); text-decoration: none;
}
.nav-item svg { flex-shrink: 0; opacity: 0.75; }
.nav-item:hover { background: var(--border); color: var(--text-primary); }
.nav-item-ativo, .nav-item-ativo:hover {
  background: var(--brand-soft); color: var(--brand);
}
.nav-item-ativo svg { opacity: 1; }
.sidebar-user {
  border-top: 1px solid var(--border); padding-top: 14px; font-size: 12px; color: var(--muted);
}
.sidebar-user a { color: var(--muted); }
.sidebar-user a:hover { color: var(--text-primary); }
.main-area { flex: 1; min-width: 0; }
.topbar {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 18px 32px; border-bottom: 1px solid var(--border);
  position: sticky; top: 0; background: color-mix(in srgb, var(--page) 88%, transparent);
  backdrop-filter: blur(6px); z-index: 5;
}
.topbar h1 { font-size: 19px; margin: 0; }
.topbar .subtitulo { margin: 2px 0 0; }
.conteudo-pagina { padding: 28px 32px; }
.sidebar-toggle {
  display: inline-flex; background: none; border: 1px solid var(--border); border-radius: 7px;
  width: 34px; height: 34px; align-items: center; justify-content: center; cursor: pointer;
  color: var(--text-primary); flex-shrink: 0;
}
.sidebar-toggle:hover { background: var(--border); }
/* Acima de 860px o botao recolhe a sidebar no lugar (largura->0), preservando
   o layout de duas colunas; abaixo disso ela vira um overlay que desliza por
   cima do conteudo - os dois modos usam o mesmo botao, decidido em JS. */
.sidebar {
  transition: width 0.18s ease, min-width 0.18s ease, padding 0.18s ease;
}
.app-shell.sidebar-fechada .sidebar {
  width: 0; min-width: 0; flex-basis: 0; padding-left: 0; padding-right: 0;
  border-right: none; overflow: hidden;
}
@media (max-width: 860px) {
  .sidebar {
    position: fixed; left: 0; top: 0; z-index: 20; width: 232px; flex-basis: 232px;
    transform: translateX(-100%); transition: transform 0.18s ease; box-shadow: var(--shadow-lift);
  }
  .sidebar.sidebar-aberta { transform: translateX(0); }
  .app-shell.sidebar-fechada .sidebar { width: 232px; flex-basis: 232px; padding: 22px 16px; border-right: 1px solid var(--border); }
  .topbar { padding: 14px 16px; }
  .conteudo-pagina { padding: 18px 14px; }
}

/* Cartao de KPI com lasca de cor no topo (identifica cada indicador sem
   depender so do numero) - usa as cores categoricas ja validadas da skill de
   dataviz, na mesma ordem fixa (nunca ciclada aleatoriamente). */
.card-kpi { position: relative; overflow: hidden; }
.card-kpi::before {
  content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: var(--kpi-accent, var(--brand));
}
.card-kpi .rotulo { display: flex; align-items: center; justify-content: space-between; gap: 8px; }

@media print {
  .barra-acoes { display: none; }
  .menu-abas { display: none; }
  .aba { display: block; }
  .card, .secao { box-shadow: none; }
  body { background: #ffffff; }
  .sidebar, .topbar, .sidebar-toggle { display: none; }
  .app-shell { display: block; }
}

/* --- Login (webapp/templates/login.html) ---------------------------------
   Tela isolada (fora do app-shell) - cartao central sobre um fundo com
   gradiente sutil nas duas cores de marca/dado, so para dar personalidade
   sem competir com o conteudo do formulario. */
.tela-login {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  padding: 24px;
  background:
    radial-gradient(700px circle at 12% -10%, color-mix(in srgb, var(--brand) 16%, transparent), transparent 60%),
    radial-gradient(600px circle at 100% 110%, color-mix(in srgb, var(--series-1) 14%, transparent), transparent 60%),
    var(--page);
}
.cartao-login {
  width: 100%; max-width: 380px; background: var(--surface-1); border: 1px solid var(--border);
  box-shadow: var(--shadow-lift); border-radius: 16px; padding: 32px 28px;
}
.cartao-login .marca-icone {
  width: 40px; height: 40px; border-radius: 10px; margin: 0 auto 16px;
  background: linear-gradient(135deg, var(--brand), color-mix(in srgb, var(--brand) 55%, black));
}
.cartao-login .cabecalho-login { text-align: center; margin-bottom: 22px; }
.cartao-login h1 { font-size: 18px; }
.btn-microsoft {
  width: 100%; display: inline-flex; align-items: center; justify-content: center; gap: 10px;
  background: var(--surface-1); color: var(--text-primary); border: 1px solid var(--border);
  border-radius: 8px; padding: 11px 16px; font-size: 13px; font-weight: 600; cursor: pointer;
  font-family: inherit; min-height: 42px;
}
.btn-microsoft:hover { background: var(--page); }
.btn-microsoft:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
"""
