-- Esquema do banco de Ordens de Compra (OC) extraidas de PDFs.
--
-- dados_clinicos fica em tabela separada, sinalizada como sensivel (LGPD):
-- nunca deve ser combinada com consultas de faturamento/comercial.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    cnpj TEXT,
    cidade TEXT,
    uf TEXT,
    UNIQUE (nome, cnpj)
);

CREATE TABLE IF NOT EXISTS fornecedores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    cnpj TEXT,
    UNIQUE (nome, cnpj)
);

CREATE TABLE IF NOT EXISTS ordens_compra (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_oc TEXT NOT NULL,
    data_emissao TEXT,
    cliente_id INTEGER NOT NULL REFERENCES clientes (id),
    fornecedor_id INTEGER NOT NULL REFERENCES fornecedores (id),
    condicao_pagamento_dias INTEGER,
    valor_frete REAL,
    valor_total REAL,
    tipo_faturamento TEXT,
    layout_origem TEXT,
    arquivo_origem TEXT,
    confianca_extracao REAL,
    data_extracao TEXT NOT NULL DEFAULT (datetime('now')),
    -- status_extracao: 'ok' (padrao) ou 'possivel_duplicata' (mesmo numero_oc
    -- + cliente salvo em arquivos diferentes - sinalizado, nunca excluido
    -- automaticamente; ver sql/queries/possiveis_duplicatas.sql)
    status_extracao TEXT NOT NULL DEFAULT 'ok',
    -- alerta_valor_divergente: 1 quando a soma dos itens (+ frete, se houver)
    -- nao bate com valor_total declarado no documento (dentro de uma
    -- tolerancia). Sinalizado para revisao, nunca corrigido automaticamente.
    alerta_valor_divergente INTEGER NOT NULL DEFAULT 0,
    -- alerta_baixa_confianca: 1 quando confianca_extracao (relatada pelo
    -- proprio modelo, ver criterio em llm_extractor.py) fica abaixo de
    -- LIMITE_CONFIANCA_BAIXA (padrao 0.7).
    alerta_baixa_confianca INTEGER NOT NULL DEFAULT 0,
    -- alerta_cnpj_invalido: 1 quando o CNPJ do cliente ou do fornecedor nao
    -- passa na validacao de digito verificador (validadores.cnpj_valido).
    alerta_cnpj_invalido INTEGER NOT NULL DEFAULT 0,
    UNIQUE (numero_oc, arquivo_origem)
);

CREATE TABLE IF NOT EXISTS itens_oc (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ordem_compra_id INTEGER NOT NULL REFERENCES ordens_compra (id) ON DELETE CASCADE,
    codigo_produto TEXT,
    descricao TEXT NOT NULL,
    quantidade REAL NOT NULL,
    unidade TEXT,
    valor_unitario REAL NOT NULL,
    valor_total REAL NOT NULL,
    lote TEXT,
    referencia TEXT
);

-- Tabela sensivel (LGPD): dados de saude do paciente. Manter isolada de
-- qualquer view/consulta comercial ou de exportacao agregada.
CREATE TABLE IF NOT EXISTS dados_clinicos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ordem_compra_id INTEGER NOT NULL UNIQUE REFERENCES ordens_compra (id) ON DELETE CASCADE,
    paciente TEXT,
    convenio TEXT,
    carteirinha TEXT,
    cirurgiao TEXT,
    data_realizacao TEXT,
    aviso_cirurgia TEXT,
    setor TEXT
);

CREATE TABLE IF NOT EXISTS log_extracao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arquivo TEXT NOT NULL,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL,
    confianca REAL,
    erro TEXT
);

CREATE INDEX IF NOT EXISTS idx_ordens_compra_cliente ON ordens_compra (cliente_id);
CREATE INDEX IF NOT EXISTS idx_ordens_compra_fornecedor ON ordens_compra (fornecedor_id);
CREATE INDEX IF NOT EXISTS idx_itens_oc_ordem ON itens_oc (ordem_compra_id);
