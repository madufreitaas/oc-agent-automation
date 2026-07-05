-- Itens de cada Ordem de Compra, com numero da OC e cliente para contexto
-- (a tabela itens_oc sozinha so tem o id interno da OC, nao o numero nem o cliente).
SELECT
    oc.numero_oc,
    oc.data_emissao,
    c.nome AS cliente,
    i.codigo_produto,
    i.descricao,
    i.quantidade,
    i.unidade,
    i.valor_unitario,
    i.valor_total,
    i.lote,
    i.referencia
FROM itens_oc i
JOIN ordens_compra oc ON oc.id = i.ordem_compra_id
JOIN clientes c ON c.id = oc.cliente_id
ORDER BY oc.data_emissao DESC, oc.numero_oc, i.id;
