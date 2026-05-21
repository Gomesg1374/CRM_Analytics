-- ============================================================
-- DASHBOARD 5: ESTOQUE E MARCA
-- ============================================================


-- CARD 1: Vendas por marca — total do período (gráfico: Bar horizontal)
SELECT
    dv.marca,
    COUNT(fv.id_venda)                                                            AS vendas,
    ROUND(COUNT(fv.id_venda)::numeric / (SUM(COUNT(fv.id_venda)) OVER ()) * 100, 1) AS market_share_pct,
    ROUND(SUM(fv.valor_venda)::numeric,   0)                                               AS faturamento,
    ROUND(AVG(fv.valor_venda)::numeric,   0)                                               AS ticket_medio,
    ROUND(SUM(fv.lucro)::numeric,         0)                                               AS lucro_total
FROM gold.fato_vendas fv
JOIN gold.dim_veiculos dv ON fv.id_veiculo = dv.id_veiculo
WHERE dv.marca <> 'desconhecida'
GROUP BY dv.marca
ORDER BY vendas DESC;


-- CARD 2: Participação de mercado por marca e mês (gráfico: Line — série por marca)
SELECT
    d.ano_mes_desc  AS mes,
    dv.marca,
    COUNT(fv.id_venda)                                                              AS vendas,
    ROUND(COUNT(fv.id_venda)::numeric / (SUM(COUNT(fv.id_venda)) OVER (PARTITION BY d.ano_mes)) * 100, 1) AS market_share_pct
FROM gold.fato_vendas fv
JOIN gold.dim_veiculos dv ON fv.id_veiculo = dv.id_veiculo
JOIN gold.dim_data      d ON fv.id_data    = d.id_data
WHERE dv.marca <> 'desconhecida'
GROUP BY d.ano_mes_desc, d.ano_mes, dv.marca
ORDER BY d.ano_mes, vendas DESC;


-- CARD 3: Top 15 modelos mais vendidos (gráfico: Bar horizontal)
SELECT
    dv.marca,
    dv.modelo,
    COUNT(fv.id_venda)                                              AS vendas,
    ROUND(AVG(fv.valor_venda)::numeric, 0)                                   AS ticket_medio,
    ROUND(AVG(fv.valor_venda - fv.valor_compra - COALESCE(fv.custos, 0))::numeric, 0) AS margem_media
FROM gold.fato_vendas fv
JOIN gold.dim_veiculos dv ON fv.id_veiculo = dv.id_veiculo
WHERE dv.marca <> 'desconhecida'
GROUP BY dv.marca, dv.modelo
ORDER BY vendas DESC
LIMIT 15;


-- CARD 4: Ticket médio e margem por marca (gráfico: Scatter ou Bar agrupado)
SELECT
    dv.marca,
    COUNT(fv.id_venda)                                                            AS vendas,
    ROUND(AVG(fv.valor_venda)::numeric,   0)                                               AS ticket_medio,
    ROUND(AVG(fv.valor_compra)::numeric,  0)                                               AS custo_medio,
    ROUND(AVG(fv.valor_venda - fv.valor_compra - COALESCE(fv.custos, 0))::numeric, 0)     AS margem_bruta_media,
    ROUND(AVG(fv.lucro)::numeric,         0)                                               AS lucro_medio,
    ROUND(AVG(fv.lucro)::numeric / NULLIF(AVG(fv.valor_venda)::numeric, 0) * 100, 1)              AS margem_pct
FROM gold.fato_vendas fv
JOIN gold.dim_veiculos dv ON fv.id_veiculo = dv.id_veiculo
WHERE dv.marca <> 'desconhecida'
GROUP BY dv.marca
ORDER BY vendas DESC;


-- CARD 5: Tipo de veículo mais vendido por marca (gráfico: Table / Heatmap)
SELECT
    dv.marca,
    dv.tipo,
    COUNT(fv.id_venda) AS vendas
FROM gold.fato_vendas fv
JOIN gold.dim_veiculos dv ON fv.id_veiculo = dv.id_veiculo
WHERE dv.marca <> 'desconhecida'
  AND dv.tipo  IS NOT NULL
GROUP BY dv.marca, dv.tipo
ORDER BY dv.marca, vendas DESC;


-- CARD 6: Estoque atual por marca e situação (gráfico: Bar empilhado)
-- Usa dim_veiculos diretamente (não fato_vendas) para mostrar o estoque vivo.
SELECT
    marca,
    situacao,
    COUNT(*) AS veiculos
FROM gold.dim_veiculos
WHERE marca <> 'desconhecida'
GROUP BY marca, situacao
ORDER BY marca, veiculos DESC;
