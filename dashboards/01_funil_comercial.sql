-- ============================================================
-- DASHBOARD 1: FUNIL COMERCIAL
-- Cada bloco separado por "-- CARD" é uma questão no Metabase.
-- Tipo de gráfico sugerido indicado em cada card.
-- ============================================================


-- CARD 1: Funil de etapas (gráfico: Funnel ou Bar horizontal)
-- Mostra o volume em cada etapa do funil.
SELECT etapa, ordem, total
FROM (
    SELECT 'Leads Recebidos'  AS etapa, 1 AS ordem, COUNT(*)           AS total FROM gold.fato_leads
    UNION ALL
    SELECT 'Agendamentos',             2,            COUNT(DISTINCT id) AS total FROM gold.fato_agendamentos WHERE flag_agendamento = 1
    UNION ALL
    SELECT 'Visitas',                  3,            COUNT(DISTINCT id) AS total FROM gold.fato_agendamentos WHERE flag_visita = 1
    UNION ALL
    SELECT 'Vendas',                   4,            COUNT(*)           AS total FROM gold.fato_vendas
) t
ORDER BY ordem;


-- CARD 2: Taxas de conversão entre etapas (gráfico: Scalar / KPI row)
WITH etapas AS (
    SELECT
        (SELECT COUNT(*) FROM gold.fato_leads)                                                      AS leads,
        (SELECT COUNT(DISTINCT id) FROM gold.fato_agendamentos WHERE flag_agendamento = 1)          AS agendamentos,
        (SELECT COUNT(DISTINCT id) FROM gold.fato_agendamentos WHERE flag_visita      = 1)          AS visitas,
        (SELECT COUNT(*)           FROM gold.fato_vendas)                                           AS vendas
)
SELECT
    leads,
    agendamentos,
    visitas,
    vendas,
    ROUND(agendamentos::numeric / NULLIF(leads, 0)        * 100, 1) AS pct_lead_agendamento,
    ROUND(visitas::numeric      / NULLIF(agendamentos, 0) * 100, 1) AS pct_agendamento_visita,
    ROUND(vendas::numeric       / NULLIF(visitas, 0)      * 100, 1) AS pct_visita_venda,
    ROUND(vendas::numeric       / NULLIF(leads, 0)        * 100, 1) AS pct_conversao_total
FROM etapas;


-- CARD 3: Leads e conversão por mês (gráfico: Line / Combo)
-- Filtro de período: adicionar filtro em id_data via Metabase UI
SELECT
    d.ano_mes_desc                                                              AS mes,
    COUNT(*)                                                                    AS leads,
    SUM(fl.convertido_flag)::numeric                                                     AS convertidos,
    ROUND(SUM(fl.convertido_flag)::numeric / NULLIF(COUNT(*), 0) * 100, 1)    AS taxa_conversao_pct
FROM gold.fato_leads fl
JOIN gold.dim_data d ON fl.id_data = d.id_data
GROUP BY d.ano_mes_desc, d.ano_mes
ORDER BY d.ano_mes;


-- CARD 4: Top motivos de perda (gráfico: Bar horizontal)
SELECT
    COALESCE(NULLIF(TRIM(motivo), ''), '(sem motivo)')           AS motivo,
    COUNT(*)                                                     AS total,
    ROUND(COUNT(*)::numeric / (SUM(COUNT(*)) OVER ()) * 100, 1)   AS pct_do_total
FROM gold.fato_leads
WHERE perdido_flag = 1
GROUP BY motivo
ORDER BY total DESC
LIMIT 15;


-- CARD 5: Funil por canal (gráfico: Bar agrupado)
SELECT
    COALESCE(dc.canal, 'sem canal')                                             AS canal,
    COUNT(DISTINCT fl.id)                                                       AS leads,
    COUNT(DISTINCT fa.id) FILTER (WHERE fa.flag_agendamento = 1)               AS agendamentos,
    COUNT(DISTINCT fa.id) FILTER (WHERE fa.flag_visita      = 1)               AS visitas,
    ROUND(
        COUNT(DISTINCT fa.id) FILTER (WHERE fa.flag_agendamento = 1)::numeric
        / NULLIF(COUNT(DISTINCT fl.id), 0) * 100, 1
    )                                                                           AS pct_agendado
FROM gold.fato_leads fl
LEFT JOIN gold.dim_canal       dc ON fl.id_canal = dc.id_canal
LEFT JOIN gold.fato_agendamentos fa ON fl.id     = fa.id
GROUP BY dc.canal
ORDER BY leads DESC;


-- CARD 6: Leads por estágio atual (gráfico: Pie ou Bar)
SELECT
    COALESCE(de.estagio, 'sem estágio')  AS estagio,
    COUNT(*)                             AS total
FROM gold.fato_leads fl
LEFT JOIN gold.dim_estagio de ON fl.id_estagio = de.id_estagio
GROUP BY de.estagio
ORDER BY total DESC;
