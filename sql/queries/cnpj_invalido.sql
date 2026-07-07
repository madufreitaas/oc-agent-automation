-- Ordens de compra em que o CNPJ do cliente ou do fornecedor nao passa na
-- validacao de digito verificador (validadores.cnpj_valido - verificacao
-- deterministica, independente do LLM). Sinalizado para revisao, nunca
-- corrigido automaticamente.
SELECT
    oc.numero_oc,
    c.nome AS cliente,
    c.cnpj AS cliente_cnpj,
    f.nome AS fornecedor,
    f.cnpj AS fornecedor_cnpj,
    oc.arquivo_origem,
    oc.data_extracao
FROM ordens_compra oc
JOIN clientes c ON c.id = oc.cliente_id
JOIN fornecedores f ON f.id = oc.fornecedor_id
WHERE oc.alerta_cnpj_invalido
ORDER BY oc.data_extracao DESC;
