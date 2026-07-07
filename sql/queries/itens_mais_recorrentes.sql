-- Produtos mais recorrentes entre todas as Ordens de Compra, por quantidade total pedida.
SELECT
    i.codigo_produto,
    i.descricao,
    COUNT(DISTINCT i.ordem_compra_id) AS numero_ocs,
    SUM(i.quantidade) AS quantidade_total,
    ROUND(AVG(i.valor_unitario)::numeric, 2) AS valor_unitario_medio,
    SUM(i.valor_total) AS valor_total_acumulado
FROM itens_oc i
GROUP BY i.codigo_produto, i.descricao
ORDER BY quantidade_total DESC
LIMIT 20;
