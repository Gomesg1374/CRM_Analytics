-- ============================================================
-- DASHBOARD 4: CANAIS E LEADS
-- ============================================================


-- CARD 1: Volume de leads por canal — total do período (gráfico: Bar horizontal)
SELECT
    COALESCE(dc.canal, 'sem canal')                                              AS canal,
    COUNT(*)                                                                     AS leads,
    SUM(fl.convertido_flag)::numeric                                                      AS convertidos,
    SUM(fl.perdido_flag)::numeric                                                         AS perdidos,
    ROUND(SUM(fl.convertido_flag)::numeric / NULLIF(COUNT(*), 0) * 100, 1)      AS taxa_conversao_pct
FROM gold.fato_leads fl
LEFT JOIN gold.dim_canal dc ON fl.id_canal = dc.id_canal
GROUP BY dc.canal
ORDER BY leads DESC;


-- CARD 2: Tendência de leads por canal ao longo do tempo (gráfico: Line — série por canal)
SELECT
    d.ano_mes_desc                           AS mes,
    COALESCE(dc.canal, 'sem canal')          AS canal,
    COUNT(*)                                 AS leads
FROM gold.fato_leads fl
JOIN  gold.dim_data  d  ON fl.id_data  = d.id_data
LEFT JOIN gold.dim_canal dc ON fl.id_canal = dc.id_canal
GROUP BY d.ano_mes_desc, d.ano_mes, dc.canal
ORDER BY d.ano_mes, leads DESC;


-- CARD 3: Taxa de conversão por canal (gráfico: Bar horizontal)
-- Inclui leads, convertidos e taxa; ordena pelos canais com mais conversões.
SELECT
    COALESCE(dc.canal, 'sem canal')                                              AS canal,
    COUNT(*)                                                                     AS leads,
    SUM(fl.convertido_flag)::numeric                                                      AS convertidos,
    ROUND(SUM(fl.convertido_flag)::numeric / NULLIF(COUNT(*), 0) * 100, 1)      AS taxa_conversao_pct,
    COUNT(DISTINCT fa.id) FILTER (WHERE fa.flag_agendamento = 1)                AS agendamentos,
    COUNT(DISTINCT fa.id) FILTER (WHERE fa.flag_visita      = 1)                AS visitas
FROM gold.fato_leads fl
LEFT JOIN gold.dim_canal          dc ON fl.id_canal = dc.id_canal
LEFT JOIN gold.fato_agendamentos  fa ON fl.id       = fa.id
GROUP BY dc.canal
ORDER BY taxa_conversao_pct DESC;


-- CARD 4: Leads por canal e mês — stacked (gráfico: Bar empilhado)
SELECT
    d.ano_mes_desc                   AS mes,
    COALESCE(dc.canal, 'sem canal')  AS canal,
    COUNT(*)                         AS leads
FROM gold.fato_leads fl
JOIN  gold.dim_data  d  ON fl.id_data  = d.id_data
LEFT JOIN gold.dim_canal dc ON fl.id_canal = dc.id_canal
GROUP BY d.ano_mes_desc, d.ano_mes, dc.canal
ORDER BY d.ano_mes;


-- CARD 5: Canal de origem das vendas realizadas (gráfico: Pie / Bar)
SELECT
    COALESCE(dc.canal, 'sem canal')                                  AS canal,
    COUNT(fv.id_venda)                                               AS vendas,
    ROUND(SUM(fv.valor_venda)::numeric, 0)                                    AS faturamento,
    ROUND(COUNT(fv.id_venda)::numeric / (SUM(COUNT(fv.id_venda)) OVER ()) * 100, 1) AS pct_vendas
FROM gold.fato_vendas fv
LEFT JOIN gold.dim_canal dc ON fv.id_canal = dc.id_canal
GROUP BY dc.canal
ORDER BY vendas DESC;
