-- Log de tentativas de extracao (sucesso e falha) por arquivo, para
-- auditoria e governanca (ex: comprovar para uma auditoria quais arquivos
-- foram processados, quando, com qual confianca e quais falharam).
SELECT
    arquivo,
    timestamp,
    status,
    confianca,
    erro
FROM log_extracao
ORDER BY timestamp DESC;
