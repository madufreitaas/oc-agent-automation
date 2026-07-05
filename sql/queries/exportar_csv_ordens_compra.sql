-- Visao "achatada" de ordens de compra + cliente + fornecedor, pronta para
-- exportar em CSV (ver src/pipeline.py / uso de sqlite3 .mode csv .headers on).
-- Nao inclui dados_clinicos (tabela sensivel/LGPD, mantida fora de exports comerciais).
SELECT
    oc.numero_oc,
    oc.data_emissao,
    c.nome AS cliente,
    c.cnpj AS cliente_cnpj,
    c.cidade AS cliente_cidade,
    c.uf AS cliente_uf,
    f.nome AS fornecedor,
    f.cnpj AS fornecedor_cnpj,
    oc.condicao_pagamento_dias,
    oc.valor_frete,
    oc.valor_total,
    oc.tipo_faturamento,
    oc.layout_origem,
    oc.arquivo_origem,
    oc.confianca_extracao,
    oc.data_extracao
FROM ordens_compra oc
JOIN clientes c ON c.id = oc.cliente_id
JOIN fornecedores f ON f.id = oc.fornecedor_id
ORDER BY oc.data_emissao DESC;
