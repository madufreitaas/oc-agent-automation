# Arquitetura do site (backend real: Supabase + FastAPI)

Este documento descreve a arquitetura do site que substituiu o relatorio HTML estatico (`report_generator.py`, que continua existindo como snapshot offline/fallback): passo a passo de configuracao no Azure e no Supabase, o modelo de autenticacao e permissoes, o fluxo de sessao, as variaveis de ambiente, e o deploy. Para as regras de governanca (o que o sistema faz e nunca faz), ver `docs/boas_praticas_e_governanca.md`, secoes 23-25.

## Por que este site existe

O relatorio HTML estatico nao tinha como marcar uma OC sinalizada (Central de alertas) como "ja revisada" - era so leitura, sem banco vivo por tras. O site resolve isso com um backend real: Postgres gerenciado, autenticacao Microsoft, e um controle de acesso por papel (RBAC) para quem pode revisar. O proposito hoje e portfolio (demo), preparado para virar a ferramenta interna da MDR/Mederi depois, quando a TI aprovar a infraestrutura oficial.

## Stack

- Banco + Auth + RLS: Supabase (Postgres gerenciado, camada gratuita).
- Site: FastAPI + Jinja2 (server-side rendering). O unico ponto com JavaScript de verdade e a pagina de login, que usa `supabase-js` (via CDN, sem etapa de build) para iniciar o OAuth com a Microsoft.
- Pipeline de extracao (`pdf_reader.py`, `llm_extractor.py`, `database.py`, `pipeline.py`): continua Python puro, rodando local. Grava no Postgres do Supabase via `psycopg`, com uma conexao "de confianca" (contorna RLS, ver secao sobre RLS abaixo) - correto para um processo automatizado que so roda localmente, nunca exposto.
- Deploy: Render (plano gratuito), ver secao de deploy.

## Dois projetos Supabase, nunca um so

Demo e producao sao projetos Supabase separados, decisao definitiva (nao "decidir depois"): um projeto so misturaria `auth.users` e RLS de dado sintetico com dado real, alem de complicar as policies. Mesma filosofia dos bancos SQLite demo/producao separados que o projeto ja usava antes desta migracao.

## Configuracao no Azure (App Registration)

Passo a passo para o modo pessoal (usado hoje, ate a TI aprovar o modo empresa):

1. Portal Azure (portal.azure.com) - Microsoft Entra ID - App registrations - New registration.
2. Nome: qualquer um identificavel (ex: `oc-agent-automation-demo`).
3. Tipos de conta suportados: "Contas em qualquer diretorio organizacional e contas pessoais Microsoft" - permite login com qualquer conta Microsoft, nao so a da empresa.
4. Redirect URI (tipo Web): `https://<seu-projeto>.supabase.co/auth/v1/callback` (o dominio do proprio projeto Supabase, nao do site). Esse valor nao muda ao trocar de modo pessoal para empresa.
5. Registrar. Na tela de visao geral do app (nao do tenant inteiro), copiar o "Application (client) ID".
6. "Certificates & secrets" - "New client secret" - escolher uma descricao e o prazo de expiracao mais longo disponivel (o secret expira, padrao 6-24 meses - anote a data de expiracao em algum lugar, porque quando vencer o login para de funcionar sem aviso nenhum). Copiar o "Value" (nao o "Secret ID") assim que aparecer - so e mostrado uma vez.

## Configuracao no Supabase (provedor Azure)

1. Painel do projeto Supabase - Authentication - Providers (ou "Sign In / Providers") - Azure - habilitar.
2. Colar o Application (client) ID em "Application (client) ID".
3. Colar o Value do secret em "Secret Value".
4. "Azure Tenant URL": deixar em branco no modo pessoal (qualquer conta Microsoft pode logar). So preencher no modo empresa (ver abaixo).
5. "Allow users without an email": manter desligado - o projeto depende do e-mail do usuario (promocao manual a admin, log de acesso), e o login ja pede o escopo `email` explicitamente.
6. Authentication - URL Configuration - Redirect URLs: adicionar a URL do site publicado seguida de `/login` (ex: `https://oc-agent-automation.onrender.com/login`). Sem isso, o `signInWithOAuth` do `login.html` nao consegue voltar para a pagina certa depois do login na Microsoft.

## Modo pessoal vs modo empresa (troca de configuracao, nao de codigo)

- Pessoal (hoje): App Registration com qualquer conta Microsoft, Tenant URL em branco no Supabase.
- Empresa (futuro, quando a TI aprovar): um App Registration novo, restrito ao tenant da MDR/Mederi, mais o Tenant ID preenchido no provedor Azure do Supabase. Nenhum codigo muda.

Ressalva importante: ao trocar do App Registration pessoal para o da empresa, a conta Microsoft "nova" (corporativa) gera um `id` novo em `auth.users` - e uma identidade OAuth diferente da conta pessoal, nao a mesma pessoa "migrada" automaticamente. Isso quebra o vinculo em `ordens_compra.revisado_por`, que aponta para o `uuid` antigo (da conta pessoal): o historico de "quem revisou o que" precisa ser remapeado manualmente nessa troca (um `UPDATE ordens_compra SET revisado_por = '<uuid-novo>' WHERE revisado_por = '<uuid-antigo>'`, rodado uma vez, direto no banco). Nao e automatico, e nao ha como evitar - documentado aqui para nao ser surpresa.

## RBAC via RLS (papeis e permissoes)

Tres papeis, na tabela `public.perfis` (uma linha por usuario, criada automaticamente no primeiro login via trigger): `leitor` (so visualiza, padrao de todo usuario novo), `revisor` e `admin` (podem marcar/desmarcar uma OC como revisada). Promover alguem a `admin`/`revisor` e manual, direto no banco:

```sql
update public.perfis set papel = 'admin' where email = 'pessoa@exemplo.com';
```

A garantia real de que um `leitor` nao consegue revisar uma OC e a policy de RLS `revisor_ou_admin_pode_revisar` em `sql/schema_postgres.sql`, avaliada pelo proprio Postgres a cada `UPDATE` em `ordens_compra` - nao um `if` no codigo do FastAPI. Ver `docs/boas_praticas_e_governanca.md`, secao 24, e o teste automatizado `tests/test_rls_papeis.py` (roda contra o Supabase real, confirma que o `leitor` e bloqueado e o `admin`/`revisor` conseguem).

`dados_clinicos` (tabela sensivel, LGPD) nao tem nenhuma policy de leitura para usuarios autenticados do site - so a service role (pipeline local) enxerga, por desenho.

## Fluxo de login (client -> servidor)

Nao existe transferencia automatica do JWT do `supabase-js` para o FastAPI - o fluxo e explicito:

1. `login.html` chama `supabase.auth.signInWithOAuth({ provider: 'azure', options: { scopes: 'email offline_access' } })`. O Supabase cuida do redirect para a Microsoft e da troca do codigo OAuth por um token.
2. Depois do redirect de volta, o `onAuthStateChange` do `supabase-js` dispara com a sessao pronta (`access_token` + `refresh_token`).
3. O client faz um POST explicito desses dois tokens para `POST /auth/sessao` (`webapp/rotas/auth_rotas.py`), que valida o `access_token` chamando `client.auth.get_user(token)` (confere no servidor do Supabase, nao so decodifica o JWT) e so entao seta os dois como cookies httponly.

## Renovacao automatica de sessao

O `access_token` expira em cerca de 1h por padrao. `webapp/dependencias.exige_login` verifica a validade a cada requisicao; se expirado mas o `refresh_token` do cookie ainda for valido, chama `client.auth.refresh_session()` server-side, reemite os dois cookies com os tokens novos, e segue a requisicao normalmente - sem exigir novo login. A usuaria so e deslogada de fato quando o `refresh_token` tambem expira ou e revogado (logout explicito).

## Variaveis de ambiente

Ver `.env.example` para a lista completa comentada. Resumo do que cada uma faz:

| Variavel | Uso |
|---|---|
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Publicas por design do Supabase (aparecem no HTML de `login.html`), protegidas por RLS. |
| `SUPABASE_SERVICE_ROLE_KEY` | Ignora RLS - so o pipeline local usa (nunca configurada no host de deploy). |
| `DATABASE_URL_DEMO`, `DATABASE_URL_PRODUCAO` | String de conexao Postgres (Session Pooler, nao a conexao direta - exige IPv6 e costuma falhar em redes comuns) usada pelo pipeline e pelas leituras do site. |
| `MODO_AUTH` | So um lembrete de qual modo (pessoal/empresa) esta ativo hoje - a troca de verdade acontece no painel do Supabase, nao aqui. |
| `AMBIENTE` | `local` (cookies sem a flag secure) ou `producao` (cookies exigem HTTPS) - configurar `producao` no host de deploy. |
| `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID` | So para referencia de qual App Registration esta em uso - o codigo Python nunca le essas variaveis, elas vao direto para o painel do Supabase. |

## Deploy (Render)

O `render.yaml` na raiz do repositorio e um Blueprint: no painel do Render, "New +" - "Blueprint" - selecionar o repositorio - o Render le o arquivo e propoe o servico ja configurado (build/start command, regiao Oregon, plano free). As variaveis marcadas com `sync: false` no blueprint sao pedidas na hora de criar o servico (copiar do `.env` local): `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `DATABASE_URL_DEMO`, `DATABASE_URL_PRODUCAO` (pode ficar em branco). `SUPABASE_SERVICE_ROLE_KEY` deliberadamente nao aparece no blueprint - o site nunca precisa dela.

O comando de start (`cd src && python -m uvicorn webapp.main:app --host 0.0.0.0 --port $PORT`) precisa do `cd src` e do `python -m` (nao o binario `uvicorn` direto) para os imports "flat" do resto do projeto (`import database`, etc) continuarem funcionando, do mesmo jeito que rodam localmente.

Depois do primeiro deploy, atualizar em Supabase - Authentication - URL Configuration - Redirect URLs com a URL publica do Render seguida de `/login` (ver secao de configuracao acima) - sem isso, o login quebra em producao mesmo funcionando local.

O plano gratuito do Render "dorme" depois de ~15 minutos sem trafego (o primeiro acesso depois disso demora uns 30-50s para acordar) - aceitavel para portfolio, nao e tratado como bug.

## Keep-alive do Supabase

O Supabase pausa projetos do free tier inativos por muito tempo (a reativacao nao e instantanea) - relevante justamente por ser portfolio, com acessos esporadicos. `.github/workflows/keep-alive.yml` chama o endpoint de saude do Supabase Auth uma vez por semana (`workflow_dispatch` tambem permite rodar manualmente, em Actions - Run workflow), so para contar como atividade. Nao tenta manter o Render sempre acordado - ver secao anterior.

## Rodando localmente

```
cd src
python -m uvicorn webapp.main:app --reload
```

Acessar `http://127.0.0.1:8000/login`. Requer `SUPABASE_URL`, `SUPABASE_ANON_KEY` e `DATABASE_URL_DEMO` configurados no `.env` (ver `.env.example`), alem do provedor Azure ja habilitado no Supabase (secao acima) - sem isso, o login carrega mas o botao "Entrar com Microsoft" nao tem para onde redirecionar de verdade.
