-- Central unificada de alertas: uma linha por (OC, tipo de alerta), juntando
-- as quatro sinalizacoes do projeto (duplicidade, valor divergente, baixa
-- confianca, CNPJ invalido). Todas seguem a mesma regra de governanca:
-- sinalizadas para revisao humana, nunca corrigidas ou excluidas
-- automaticamente pelo pipeline. Ver docs/boas_praticas_e_governanca.md.
--
-- As consultas individuais (possiveis_duplicatas.sql, alertas_valor.sql,
-- baixa_confianca.sql, cnpj_invalido.sql) continuam disponiveis para
-- analise pontual de cada tipo separadamente.

SELECT
    'Duplicidade' AS tipo,
    oc.numero_oc,
    c.nome AS cliente,
    oc.arquivo_origem,
    'OC com mesmo numero e cliente salva em outro arquivo' AS detalhe,
    oc.data_extracao
FROM ordens_compra oc
JOIN clientes c ON c.id = oc.cliente_id
WHERE oc.status_extracao = 'possivel_duplicata'

UNION ALL

SELECT
    'Valor divergente',
    oc.numero_oc,
    c.nome,
    oc.arquivo_origem,
    'Soma dos itens nao bate com o valor total declarado',
    oc.data_extracao
FROM ordens_compra oc
JOIN clientes c ON c.id = oc.cliente_id
WHERE oc.alerta_valor_divergente = 1

UNION ALL

SELECT
    'Baixa confianca',
    oc.numero_oc,
    c.nome,
    oc.arquivo_origem,
    'Confianca relatada pelo modelo: ' || ROUND(oc.confianca_extracao, 2),
    oc.data_extracao
FROM ordens_compra oc
JOIN clientes c ON c.id = oc.cliente_id
WHERE oc.alerta_baixa_confianca = 1

UNION ALL

SELECT
    'CNPJ invalido',
    oc.numero_oc,
    c.nome,
    oc.arquivo_origem,
    'Cliente: ' || COALESCE(c.cnpj, '-') || '  /  Fornecedor: ' || COALESCE(f.cnpj, '-'),
    oc.data_extracao
FROM ordens_compra oc
JOIN clientes c ON c.id = oc.cliente_id
JOIN fornecedores f ON f.id = oc.fornecedor_id
WHERE oc.alerta_cnpj_invalido = 1

ORDER BY data_extracao DESC;
