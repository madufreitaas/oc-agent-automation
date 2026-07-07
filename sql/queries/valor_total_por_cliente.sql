-- Valor total de Ordens de Compra por cliente (hospital), do maior para o menor.
SELECT
    c.nome AS cliente,
    c.cidade,
    c.uf,
    COUNT(oc.id) AS total_ocs,
    SUM(oc.valor_total) AS valor_total_acumulado,
    ROUND(AVG(oc.valor_total)::numeric, 2) AS valor_medio_por_oc
FROM ordens_compra oc
JOIN clientes c ON c.id = oc.cliente_id
GROUP BY c.id
ORDER BY valor_total_acumulado DESC;
