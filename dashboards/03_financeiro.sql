-- ============================================================
-- DASHBOARD 3: FINANCEIRO
-- Fonte: fato_vendas (lucro, comissao, impostos, retorno)
-- ============================================================


-- CARD 1: Evolução mensal — faturamento, lucro, comissão, impostos (gráfico: Line / Combo)
SELECT
    d.ano_mes_desc                           AS mes,
    ROUND(SUM(fv.valor_venda)::numeric,   0)          AS faturamento,
    ROUND(SUM(fv.lucro)::numeric,         0)          AS lucro_liquido,
    ROUND(SUM(fv.comissao)::numeric,      0)          AS comissoes_pagas,
    ROUND(SUM(fv.impostos)::numeric,      0)          AS impostos,
    ROUND(SUM(fv.retorno)::numeric,       0)          AS retorno_bruto,
    ROUND(SUM(fv.lucro)::numeric / NULLIF(SUM(fv.valor_venda)::numeric, 0) * 100, 1) AS margem_liquida_pct
FROM gold.fato_vendas fv
JOIN gold.dim_data d ON fv.id_data = d.id_data
GROUP BY d.ano_mes_desc, d.ano_mes
ORDER BY d.ano_mes;


-- CARD 2: Totais do período — KPIs financeiros (gráfico: Scalar / Number)
SELECT
    ROUND(SUM(valor_venda)::numeric,  0)  AS faturamento_total,
    ROUND(SUM(lucro)::numeric,        0)  AS lucro_total,
    ROUND(SUM(comissao)::numeric,     0)  AS comissoes_total,
    ROUND(SUM(impostos)::numeric,     0)  AS impostos_total,
    ROUND(SUM(retorno)::numeric,      0)  AS retorno_total,
    ROUND(SUM(lucro)::numeric / NULLIF(SUM(valor_venda)::numeric, 0) * 100, 1) AS margem_liquida_pct
FROM gold.fato_vendas;


-- CARD 3: Lucro líquido e margem por vendedor (gráfico: Bar horizontal)
SELECT
    dv.nome                                                          AS vendedor,
    dl.loja,
    COUNT(fv.id_venda)                                              AS vendas,
    ROUND(SUM(fv.valor_venda)::numeric, 0)                                   AS faturamento,
    ROUND(SUM(fv.lucro)::numeric,       0)                                   AS lucro_liquido,
    ROUND(SUM(fv.comissao)::numeric,    0)                                   AS comissoes,
    ROUND(SUM(fv.lucro)::numeric / NULLIF(SUM(fv.valor_venda)::numeric, 0) * 100, 1) AS margem_pct
FROM gold.fato_vendas fv
JOIN gold.dim_vendedores dv ON fv.id_vendedor = dv.id_vendedor
JOIN gold.dim_lojas      dl ON fv.id_loja     = dl.id_loja
WHERE fv.id_vendedor <> -1
GROUP BY dv.nome, dl.loja
ORDER BY lucro_liquido DESC;


-- CARD 4: Lucro líquido e margem por loja (gráfico: Bar)
SELECT
    dl.loja,
    COUNT(fv.id_venda)                                              AS vendas,
    ROUND(SUM(fv.valor_venda)::numeric, 0)                                   AS faturamento,
    ROUND(SUM(fv.lucro)::numeric,       0)                                   AS lucro_liquido,
    ROUND(SUM(fv.comissao)::numeric,    0)                                   AS comissoes,
    ROUND(SUM(fv.impostos)::numeric,    0)                                   AS impostos,
    ROUND(SUM(fv.lucro)::numeric / NULLIF(SUM(fv.valor_venda)::numeric, 0) * 100, 1) AS margem_pct
FROM gold.fato_vendas fv
JOIN gold.dim_lojas dl ON fv.id_loja = dl.id_loja
WHERE fv.id_loja <> -1
GROUP BY dl.loja
ORDER BY lucro_liquido DESC;


-- CARD 5: Comissão paga por vendedor por mês (gráfico: Heatmap ou Table)
SELECT
    d.ano_mes_desc       AS mes,
    dv.nome              AS vendedor,
    ROUND(SUM(fv.comissao)::numeric, 0) AS comissao_total,
    COUNT(fv.id_venda)         AS vendas
FROM gold.fato_vendas fv
JOIN gold.dim_vendedores dv ON fv.id_vendedor = dv.id_vendedor
JOIN gold.dim_data        d ON fv.id_data     = d.id_data
WHERE fv.id_vendedor <> -1
GROUP BY d.ano_mes_desc, d.ano_mes, dv.nome
ORDER BY d.ano_mes, comissao_total DESC;


-- CARD 6: Trimestre — faturamento e lucro (gráfico: Bar agrupado)
SELECT
    d.ano                                    AS ano,
    d.trimestre,
    CONCAT(d.ano, ' Q', d.trimestre)         AS periodo,
    ROUND(SUM(fv.valor_venda)::numeric, 0)            AS faturamento,
    ROUND(SUM(fv.lucro)::numeric,       0)            AS lucro_liquido,
    ROUND(SUM(fv.lucro)::numeric / NULLIF(SUM(fv.valor_venda)::numeric, 0) * 100, 1) AS margem_pct
FROM gold.fato_vendas fv
JOIN gold.dim_data d ON fv.id_data = d.id_data
GROUP BY d.ano, d.trimestre
ORDER BY d.ano, d.trimestre;
