-- Prazo medio de pagamento (em dias) negociado por cliente.
SELECT
    c.nome AS cliente,
    COUNT(oc.id) AS total_ocs,
    ROUND(AVG(oc.condicao_pagamento_dias), 1) AS prazo_medio_dias,
    MIN(oc.condicao_pagamento_dias) AS prazo_minimo_dias,
    MAX(oc.condicao_pagamento_dias) AS prazo_maximo_dias
FROM ordens_compra oc
JOIN clientes c ON c.id = oc.cliente_id
WHERE oc.condicao_pagamento_dias IS NOT NULL
GROUP BY c.id
ORDER BY prazo_medio_dias DESC;
