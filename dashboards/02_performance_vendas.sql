-- ============================================================
-- DASHBOARD 2: PERFORMANCE DE VENDAS
-- ============================================================


-- CARD 1: Vendas vs Meta por vendedor e mês (gráfico: Table ou Bar agrupado)
-- Linha = mês × vendedor; inclui % de atingimento de meta.
SELECT
    d.ano_mes_desc                                                                 AS mes,
    dv.nome                                                                        AS vendedor,
    dl.loja,
    COUNT(fv.id_venda)                                                             AS vendas,
    MAX(fm.meta_qtd)::numeric                                                               AS meta,
    ROUND(COUNT(fv.id_venda)::numeric / NULLIF(MAX(fm.meta_qtd)::numeric, 0) * 100, 1)    AS pct_meta
FROM gold.fato_vendas fv
JOIN  gold.dim_vendedores    dv ON fv.id_vendedor = dv.id_vendedor
JOIN  gold.dim_lojas         dl ON fv.id_loja     = dl.id_loja
JOIN  gold.dim_data           d ON fv.id_data     = d.id_data
LEFT JOIN gold.fato_meta_vendedor fm
    ON fv.id_vendedor = fm.id_vendedor AND fv.ano_mes = fm.ano_mes
WHERE fv.id_vendedor <> -1
GROUP BY d.ano_mes_desc, d.ano_mes, dv.nome, dl.loja, fm.meta_qtd
ORDER BY d.ano_mes DESC, vendas DESC;


-- CARD 2: Ranking geral de vendedores — total do período (gráfico: Bar horizontal)
SELECT
    dv.nome                                                          AS vendedor,
    dl.loja,
    COUNT(fv.id_venda)                                              AS total_vendas,
    ROUND(AVG(fv.valor_venda)::numeric, 0)                                   AS ticket_medio,
    ROUND(AVG(fv.desconto)::numeric, 0)                                      AS desconto_medio,
    ROUND(SUM(fv.valor_venda - fv.valor_compra - COALESCE(fv.custos, 0))::numeric, 0) AS margem_bruta
FROM gold.fato_vendas fv
JOIN gold.dim_vendedores dv ON fv.id_vendedor = dv.id_vendedor
JOIN gold.dim_lojas      dl ON fv.id_loja     = dl.id_loja
WHERE fv.id_vendedor <> -1
GROUP BY dv.nome, dl.loja
ORDER BY total_vendas DESC;


-- CARD 3: Vendas vs Meta por loja e mês (gráfico: Bar agrupado ou Line)
SELECT
    d.ano_mes_desc                                                                AS mes,
    dl.loja,
    COUNT(fv.id_venda)                                                            AS vendas,
    MAX(fm.meta_qtd)::numeric                                                              AS meta,
    ROUND(COUNT(fv.id_venda)::numeric / NULLIF(MAX(fm.meta_qtd)::numeric, 0) * 100, 1)   AS pct_meta
FROM gold.fato_vendas fv
JOIN  gold.dim_lojas   dl ON fv.id_loja = dl.id_loja
JOIN  gold.dim_data     d ON fv.id_data = d.id_data
LEFT JOIN gold.fato_meta_loja fm
    ON fv.id_loja = fm.id_loja AND fv.ano_mes = fm.ano_mes
WHERE fv.id_loja <> -1
GROUP BY d.ano_mes_desc, d.ano_mes, dl.loja, fm.meta_qtd
ORDER BY d.ano_mes, dl.loja;


-- CARD 4: Ticket médio e desconto médio por mês (gráfico: Line / Combo)
SELECT
    d.ano_mes_desc                         AS mes,
    ROUND(AVG(fv.valor_venda)::numeric,  0)         AS ticket_medio,
    ROUND(AVG(fv.valor_compra)::numeric, 0)         AS custo_medio,
    ROUND(AVG(fv.desconto)::numeric,     0)         AS desconto_medio,
    ROUND(AVG(fv.valor_venda - fv.valor_compra - COALESCE(fv.custos, 0))::numeric, 0) AS margem_bruta_media
FROM gold.fato_vendas fv
JOIN gold.dim_data d ON fv.id_data = d.id_data
GROUP BY d.ano_mes_desc, d.ano_mes
ORDER BY d.ano_mes;


-- CARD 5: Margem bruta por loja (gráfico: Bar)
SELECT
    dl.loja,
    COUNT(fv.id_venda)                                                            AS vendas,
    ROUND(SUM(fv.valor_venda)::numeric, 0)                                                 AS faturamento,
    ROUND(SUM(fv.valor_venda - fv.valor_compra - COALESCE(fv.custos, 0))::numeric, 0)     AS margem_bruta,
    ROUND(
        SUM(fv.valor_venda - fv.valor_compra - COALESCE(fv.custos, 0))::numeric
        / NULLIF(SUM(fv.valor_venda)::numeric, 0) * 100, 1
    )                                                                             AS pct_margem
FROM gold.fato_vendas fv
JOIN gold.dim_lojas dl ON fv.id_loja = dl.id_loja
WHERE fv.id_loja <> -1
GROUP BY dl.loja
ORDER BY margem_bruta DESC;
