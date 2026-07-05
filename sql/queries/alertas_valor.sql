-- Ordens de compra em que a soma dos itens (com ou sem frete) nao bate com
-- o valor_total declarado no documento, dentro de uma tolerancia de
-- R$ 0,02. Sinalizadas automaticamente em database.py, nunca corrigidas
-- pelo pipeline - a decisao (corrigir a extracao, revisar o PDF original,
-- ou aceitar a diferenca) fica sempre com um humano.
SELECT
    oc.numero_oc,
    c.nome AS cliente,
    oc.arquivo_origem,
    oc.valor_total AS valor_total_declarado,
    (SELECT SUM(i.valor_total) FROM itens_oc i WHERE i.ordem_compra_id = oc.id) AS soma_itens,
    oc.valor_frete,
    oc.data_extracao
FROM ordens_compra oc
JOIN clientes c ON c.id = oc.cliente_id
WHERE oc.alerta_valor_divergente = 1
ORDER BY oc.data_extracao DESC;
