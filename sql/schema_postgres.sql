-- Esquema Postgres do banco de Ordens de Compra (OC), para rodar no SQL
-- Editor de um projeto Supabase (demo ou producao - projetos SEPARADOS, ver
-- docs/arquitetura_webapp.md, nunca o mesmo projeto para os dois).
--
-- Portado de sql/schema.sql (SQLite). Diferencas de dialeto: GENERATED ALWAYS
-- AS IDENTITY no lugar de AUTOINCREMENT, TIMESTAMPTZ DEFAULT now() no lugar
-- de TEXT DEFAULT (datetime('now')). sql/schema.sql (SQLite) continua sendo
-- o schema usado pelo pipeline local antes desta migracao - nao apagar.
--
-- dados_clinicos fica em tabela separada, sinalizada como sensivel (LGPD):
-- nunca deve ser combinada com consultas de faturamento/comercial, e (ver
-- secao de RLS no final) nao tem nenhuma politica de leitura para usuarios
-- autenticados do site - so a service role (usada pelo pipeline local) enxerga.

create table if not exists public.clientes (
    id bigint generated always as identity primary key,
    nome text not null,
    cnpj text,
    cidade text,
    uf text,
    unique (nome, cnpj)
);

create table if not exists public.fornecedores (
    id bigint generated always as identity primary key,
    nome text not null,
    cnpj text,
    unique (nome, cnpj)
);

create table if not exists public.ordens_compra (
    id bigint generated always as identity primary key,
    numero_oc text not null,
    data_emissao text,
    cliente_id bigint not null references public.clientes (id),
    fornecedor_id bigint not null references public.fornecedores (id),
    condicao_pagamento_dias integer,
    valor_frete double precision,
    valor_total double precision,
    tipo_faturamento text,
    layout_origem text,
    arquivo_origem text,
    confianca_extracao double precision,
    data_extracao timestamptz not null default now(),
    -- status_extracao: 'ok' (padrao) ou 'possivel_duplicata' (mesmo numero_oc
    -- + cliente salvo em arquivos diferentes - sinalizado, nunca excluido
    -- automaticamente; ver sql/queries/possiveis_duplicatas.sql)
    status_extracao text not null default 'ok',
    -- alerta_valor_divergente: true quando a soma dos itens (+ frete, se
    -- houver) nao bate com valor_total declarado no documento (dentro de uma
    -- tolerancia). Sinalizado para revisao, nunca corrigido automaticamente.
    alerta_valor_divergente boolean not null default false,
    -- alerta_baixa_confianca: true quando confianca_extracao (relatada pelo
    -- proprio modelo, ver criterio em llm_extractor.py) fica abaixo de
    -- LIMITE_CONFIANCA_BAIXA (padrao 0.7).
    alerta_baixa_confianca boolean not null default false,
    -- alerta_cnpj_invalido: true quando o CNPJ do cliente ou do fornecedor
    -- nao passa na validacao de digito verificador (validadores.cnpj_valido).
    alerta_cnpj_invalido boolean not null default false,
    -- Fluxo de revisao humana (so viavel agora que existe um backend real -
    -- ver docs/arquitetura_webapp.md). revisado_por referencia o usuario
    -- Microsoft que revisou, via auth.users do Supabase. ATENCAO: ao trocar
    -- do App Registration pessoal para o da empresa (modo "empresa"), o id
    -- do usuario muda (e uma identidade OAuth nova) - o historico de
    -- revisado_por precisa ser remapeado manualmente nessa troca, nao e
    -- automatico.
    revisado boolean not null default false,
    revisado_em timestamptz,
    revisado_por uuid references auth.users (id),
    unique (numero_oc, arquivo_origem)
);

create table if not exists public.itens_oc (
    id bigint generated always as identity primary key,
    ordem_compra_id bigint not null references public.ordens_compra (id) on delete cascade,
    codigo_produto text,
    descricao text not null,
    quantidade double precision not null,
    unidade text,
    valor_unitario double precision not null,
    valor_total double precision not null,
    lote text,
    referencia text
);

-- Tabela sensivel (LGPD): dados de saude do paciente. Mantida isolada de
-- qualquer view/consulta comercial ou de exportacao agregada. RLS ativado
-- sem NENHUMA politica de select para usuarios autenticados do site (ver
-- secao de RLS no final) - so a service role (pipeline local) enxerga.
create table if not exists public.dados_clinicos (
    id bigint generated always as identity primary key,
    ordem_compra_id bigint not null unique references public.ordens_compra (id) on delete cascade,
    paciente text,
    convenio text,
    carteirinha text,
    cirurgiao text,
    data_realizacao text,
    aviso_cirurgia text,
    setor text
);

create table if not exists public.log_extracao (
    id bigint generated always as identity primary key,
    arquivo text not null,
    timestamp timestamptz not null default now(),
    status text not null,
    confianca double precision,
    erro text
);

create index if not exists idx_ordens_compra_cliente on public.ordens_compra (cliente_id);
create index if not exists idx_ordens_compra_fornecedor on public.ordens_compra (fornecedor_id);
create index if not exists idx_itens_oc_ordem on public.itens_oc (ordem_compra_id);


-- ============================================================
-- Usuarios e RBAC (Role-Based Access Control)
-- ============================================================
-- Nao criamos uma tabela "usuarios" do zero - o Supabase Auth ja gerencia
-- auth.users internamente ao ativar o login. public.perfis e o padrao
-- idiomatico do Supabase: uma linha por usuario autenticado, ligada por id,
-- com o papel (RBAC) que controla o que cada um pode ver/fazer.
--
-- papel: 'admin' (acesso total, inclusive marcar revisao), 'revisor' (pode
-- marcar OCs como revisadas), 'leitor' (so visualiza). Hoje so existe um
-- usuario real (a Madu, papel 'admin', promovido manualmente apos o primeiro
-- login - ver docs/arquitetura_webapp.md), mas a tabela ja fica pronta para
-- multiplos usuarios quando a ferramenta virar uso real da empresa.
create table if not exists public.perfis (
    id uuid references auth.users (id) on delete cascade primary key,
    email text,
    papel text not null default 'leitor'
        check (papel in ('admin', 'revisor', 'leitor')),  -- evita erro de digitacao silencioso
    criado_em timestamptz not null default now()
);

-- Cria a linha em perfis automaticamente a cada novo login/cadastro.
create or replace function public.criar_perfil_novo_usuario()
returns trigger as $$
begin
    insert into public.perfis (id, email) values (new.id, new.email);
    return new;
end;
$$ language plpgsql security definer set search_path = public;

drop trigger if exists ao_criar_usuario on auth.users;
create trigger ao_criar_usuario
    after insert on auth.users
    for each row execute procedure public.criar_perfil_novo_usuario();

-- Log de acesso ao site (login/logout), no mesmo espirito de auditoria do
-- log_extracao ja existente - nunca apagado automaticamente.
create table if not exists public.log_acesso (
    id bigint generated always as identity primary key,
    usuario_email text not null,
    timestamp timestamptz not null default now(),
    evento text not null,   -- 'login' ou 'logout'
    ip text
);


-- ============================================================
-- RLS (Row Level Security)
-- ============================================================
-- Function security definer para checar o papel do usuario logado, evitando
-- que a politica de ordens_compra referencie perfis diretamente (perfis
-- tambem tem RLS ativado - uma subquery direta causaria recursao/negacao
-- silenciosa, um dos gotchas mais comuns do Supabase).
create or replace function public.papel_do_usuario_atual()
returns text as $$
    select papel from public.perfis where id = auth.uid();
$$ language sql security definer stable set search_path = public;

alter table public.perfis enable row level security;
create policy "usuario_ve_o_proprio_perfil" on public.perfis
    for select using (id = auth.uid());

alter table public.clientes enable row level security;
create policy "autenticado_pode_ler_clientes" on public.clientes
    for select using (auth.role() = 'authenticated');

alter table public.fornecedores enable row level security;
create policy "autenticado_pode_ler_fornecedores" on public.fornecedores
    for select using (auth.role() = 'authenticated');

alter table public.itens_oc enable row level security;
create policy "autenticado_pode_ler_itens" on public.itens_oc
    for select using (auth.role() = 'authenticated');

alter table public.log_extracao enable row level security;
create policy "autenticado_pode_ler_log_extracao" on public.log_extracao
    for select using (auth.role() = 'authenticated');

alter table public.ordens_compra enable row level security;

create policy "autenticado_pode_ler_ordens_compra" on public.ordens_compra
    for select using (auth.role() = 'authenticated');

-- So admin/revisor podem atualizar (usado exclusivamente para marcar
-- revisado/revisado_em/revisado_por - nenhuma outra rota do site atualiza
-- ordens_compra; a extracao em si so grava via service role, que ignora RLS).
create policy "revisor_ou_admin_pode_revisar" on public.ordens_compra
    for update using (public.papel_do_usuario_atual() in ('admin', 'revisor'));

-- dados_clinicos: RLS ativado, DE PROPOSITO sem nenhuma politica de select -
-- nenhum usuario autenticado do site consegue ler essa tabela via
-- PostgREST/supabase-py, so a service role (pipeline local, que ignora RLS).
-- Reforca no banco a regra ja estabelecida em
-- docs/boas_praticas_e_governanca.md de nunca misturar dado clinico em
-- relatorio comercial.
--
-- REVOKE explicito abaixo: o proprio Supabase concede TRUNCATE/REFERENCES/
-- TRIGGER para anon/authenticated em toda tabela nova do schema public, por
-- padrao da plataforma (independente do toggle "Automatically expose new
-- tables" - esse toggle so afeta SELECT/INSERT/UPDATE/DELETE). Nao da para
-- ler dado por esses privilegios via API normal, mas TRUNCATE permitiria
-- apagar a tabela inteira - revogado por precaucao (defesa em profundidade),
-- ainda que hoje ja fosse bloqueado por nao ter SELECT/DELETE.
alter table public.dados_clinicos enable row level security;
revoke all on public.dados_clinicos from anon, authenticated;

alter table public.log_acesso enable row level security;
create policy "usuario_ve_o_proprio_log_acesso" on public.log_acesso
    for select using (usuario_email = (select email from public.perfis where id = auth.uid()));


-- ============================================================
-- Grants explicitos (necessarios porque "Automatically expose new tables"
-- foi desmarcado na criacao do projeto - recomendado, e o padrao seguro por
-- omissao do proprio Supabase). RLS sozinho nao basta: sem GRANT, a role nem
-- chega a avaliar a politica - isso vale ATE PARA service_role. RLS
-- (row level security, controla LINHAS) e GRANT (controla TABELAS) sao dois
-- mecanismos separados do Postgres:
--   - service_role tem o atributo BYPASSRLS, entao ignora as POLITICAS de
--     RLS - mas ainda precisa de GRANT de tabela como qualquer outra role.
--   - anon/authenticated nao tem BYPASSRLS, entao para elas GRANT e RLS
--     precisam das duas coisas.
-- Repetir este bloco nao tem efeito colateral se os grants ja existirem
-- (idempotente).
--
-- dados_clinicos: service_role recebe grant completo (o pipeline precisa
-- gravar dado clinico durante a extracao). anon/authenticated NAO recebem
-- nenhum grant nessa tabela de proposito - RLS tambem ficaria ligado sem
-- politica (ver acima), entao fica bloqueada em duas camadas.
--
-- IMPORTANTE (achado ao revisar o projeto ja em uso): o proprio Supabase
-- concede TRUNCATE/REFERENCES/TRIGGER para anon/authenticated em toda tabela
-- nova do schema public, por padrao da plataforma - independente de
-- "Automatically expose new tables" (esse toggle so afeta
-- SELECT/INSERT/UPDATE/DELETE). Ninguem consegue LER dado por esses
-- privilegios via API normal (PostgREST nao expoe um verbo TRUNCATE), mas
-- TRUNCATE permitiria apagar uma tabela inteira - revogado abaixo por
-- precaucao (defesa em profundidade), ja que "nunca excluir sem revisao
-- humana" e uma regra central deste projeto (ver
-- docs/boas_praticas_e_governanca.md).
-- ============================================================
grant usage on schema public to anon, authenticated, service_role;

revoke truncate, references, trigger on all tables in schema public from anon, authenticated;

grant select on public.clientes to authenticated;
grant select on public.fornecedores to authenticated;
grant select, update on public.ordens_compra to authenticated;
grant select on public.itens_oc to authenticated;
grant select on public.log_extracao to authenticated;
grant select on public.perfis to authenticated;
grant select on public.log_acesso to authenticated;

-- service_role: acesso completo a tudo (bypassa RLS, mas precisa do GRANT).
-- E o papel usado exclusivamente pelo pipeline local (nunca pelo site/JS).
grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;
