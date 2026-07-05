-- Ordens de compra em que o proprio modelo relatou confianca baixa na
-- extracao (abaixo de LIMITE_CONFIANCA_BAIXA, padrao 0.7). Ver o criterio
-- explicito de calculo em src/llm_extractor.py (PROMPT_SISTEMA) e em
-- docs/data_model.md. Sinalizado para revisao, nunca corrigido automaticamente.
SELECT
    oc.numero_oc,
    c.nome AS cliente,
    oc.arquivo_origem,
    oc.confianca_extracao,
    oc.layout_origem,
    oc.data_extracao
FROM ordens_compra oc
JOIN clientes c ON c.id = oc.cliente_id
WHERE oc.alerta_baixa_confianca = 1
ORDER BY oc.confianca_extracao ASC;
