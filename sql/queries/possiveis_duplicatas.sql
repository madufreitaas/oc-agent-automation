-- Ordens de compra com o mesmo numero de OC e cliente, salvas em arquivos
-- diferentes (possivel duplicidade, ex: o mesmo PDF salvo duas vezes pela
-- automacao com nomes de arquivo diferentes). Sinalizadas automaticamente
-- em database.py, nunca excluidas pelo pipeline - a decisao de excluir ou
-- nao cada grupo fica sempre com um humano, apos revisar aqui.
SELECT
    oc.numero_oc,
    c.nome AS cliente,
    oc.id AS ordem_compra_id,
    oc.arquivo_origem,
    oc.valor_total,
    oc.data_extracao
FROM ordens_compra oc
JOIN clientes c ON c.id = oc.cliente_id
WHERE oc.status_extracao = 'possivel_duplicata'
ORDER BY oc.numero_oc, oc.data_extracao;
