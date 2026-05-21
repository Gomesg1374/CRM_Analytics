"""
Cria os 5 dashboards prioritários no Metabase via API.
Uso:  python scripts/create_metabase_dashboards.py
"""
import requests, uuid

BASE  = "http://localhost:3000"
DB_ID = 2   # "CRM Analytics" (PostgreSQL)

# IDs fixos para os parâmetros de data (iguais em todos os dashboards)
P_INICIO_ID = "p-data-inicio"
P_FIM_ID    = "p-data-fim"

DATE_PARAMS = [
    {"id": P_INICIO_ID, "type": "date/single", "name": "Data Início", "slug": "data_inicio"},
    {"id": P_FIM_ID,    "type": "date/single", "name": "Data Fim",    "slug": "data_fim"},
]

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def login(email, password):
    r = requests.post(f"{BASE}/api/session",
                      json={"username": email, "password": password})
    r.raise_for_status()
    return r.json()["id"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def date_tags():
    """Template-tags de data_inicio / data_fim para cards SQL."""
    return {
        "data_inicio": {
            "id": str(uuid.uuid4()), "name": "data_inicio",
            "display-name": "Data Início", "type": "date", "required": False,
        },
        "data_fim": {
            "id": str(uuid.uuid4()), "name": "data_fim",
            "display-name": "Data Fim", "type": "date", "required": False,
        },
    }

def date_mappings(card_id):
    """Parameter mappings para o dashcard conectar ao filtro de data."""
    return [
        {"parameter_id": P_INICIO_ID, "card_id": card_id,
         "target": ["variable", ["template-tag", "data_inicio"]]},
        {"parameter_id": P_FIM_ID,    "card_id": card_id,
         "target": ["variable", ["template-tag", "data_fim"]]},
    ]

def create_card(session, name, sql, display="table", viz=None, dated=False):
    tags = date_tags() if dated else {}
    payload = {
        "name": name,
        "display": display,
        "dataset_query": {
            "type": "native",
            "native": {"query": sql, "template-tags": tags},
            "database": DB_ID,
        },
        "visualization_settings": viz or {},
    }
    r = requests.post(f"{BASE}/api/card", json=payload,
                      headers={"X-Metabase-Session": session})
    r.raise_for_status()
    return r.json()["id"]

def create_dashboard(session, name, description=""):
    r = requests.post(f"{BASE}/api/dashboard",
                      json={"name": name, "description": description},
                      headers={"X-Metabase-Session": session})
    r.raise_for_status()
    return r.json()["id"]

def configure_dashboard(session, dash_id, layout, dated_card_ids=None):
    """
    layout          : list of (card_id, row, col, size_x, size_y)
    dated_card_ids  : set of card_ids that have date template tags
    """
    dated = set(dated_card_ids or [])
    dashcards = []
    for i, (cid, row, col, sx, sy) in enumerate(layout):
        mappings = date_mappings(cid) if cid in dated else []
        dashcards.append({
            "id": -(i + 1), "card_id": cid, "row": row, "col": col,
            "size_x": sx, "size_y": sy,
            "series": [], "parameter_mappings": mappings,
            "visualization_settings": {},
        })
    body = {"dashcards": dashcards, "tabs": [], "parameters": DATE_PARAMS}
    r = requests.put(f"{BASE}/api/dashboard/{dash_id}", json=body,
                     headers={"X-Metabase-Session": session})
    if not r.ok:
        print(f"  ERRO {r.status_code}: {r.text[:400]}")
    r.raise_for_status()

# ---------------------------------------------------------------------------
# SQL definitions
# (cards com filtro de data usam [[AND d.data >= {{data_inicio}}::date]] etc.)
# ---------------------------------------------------------------------------

SQLS = {
    # ── FUNIL COMERCIAL ─────────────────────────────────────────────────────
    "funil_por_mes": """
SELECT d.ano_mes_desc AS "Mês",
       COUNT(DISTINCT fl.id) AS "Leads",
       COUNT(DISTINCT fa.id) FILTER (WHERE fa.flag_agendamento = 1) AS "Agendamentos",
       COUNT(DISTINCT fa.id) FILTER (WHERE fa.flag_visita = 1)      AS "Visitas",
       COUNT(DISTINCT fv.id_venda)                                  AS "Vendas"
FROM gold.dim_data d
LEFT JOIN gold.fato_leads fl        ON fl.id_data = d.id_data
LEFT JOIN gold.fato_agendamentos fa ON fa.id_data_agendamento = d.id_data
LEFT JOIN gold.fato_vendas fv       ON fv.id_data = d.id_data
WHERE d.ano BETWEEN 2022 AND 2026
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY d.ano_mes_desc, d.ano_mes
HAVING COUNT(DISTINCT fl.id) > 0
    OR COUNT(DISTINCT fa.id) > 0
    OR COUNT(DISTINCT fv.id_venda) > 0
ORDER BY d.ano_mes
""",
    "funil_por_estagio": """
SELECT e.estagio AS "Etapa", COUNT(*) AS "Leads"
FROM gold.fato_leads fl
JOIN gold.dim_estagio e ON fl.id_estagio = e.id_estagio
JOIN gold.dim_data d    ON fl.id_data = d.id_data
WHERE 1=1
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY e.estagio, e.id_estagio
ORDER BY e.id_estagio
""",
    "motivos_perda": """
SELECT motivo AS "Motivo", COUNT(*) AS "Qtd"
FROM gold.fato_leads fl
JOIN gold.dim_data d ON fl.id_data = d.id_data
WHERE fl.perdido_flag = 1
  AND fl.motivo IS NOT NULL AND fl.motivo <> ''
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY motivo
ORDER BY "Qtd" DESC
LIMIT 15
""",
    "leads_por_canal": """
SELECT c.canal AS "Canal", COUNT(*) AS "Leads"
FROM gold.fato_leads fl
JOIN gold.dim_canal c ON fl.id_canal = c.id_canal
JOIN gold.dim_data d  ON fl.id_data = d.id_data
WHERE 1=1
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY c.canal
ORDER BY "Leads" DESC
""",
    "taxa_conversao_canal": """
SELECT c.canal AS "Canal",
       COUNT(fl.id) AS "Leads",
       COUNT(fl.id) FILTER (WHERE fl.convertido_flag = 1) AS "Convertidos",
       ROUND((100.0 * COUNT(fl.id) FILTER (WHERE fl.convertido_flag = 1)
             / NULLIF(COUNT(fl.id), 0))::numeric, 1) AS "% Conversão"
FROM gold.fato_leads fl
JOIN gold.dim_canal c ON fl.id_canal = c.id_canal
JOIN gold.dim_data d  ON fl.id_data = d.id_data
WHERE 1=1
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY c.canal
ORDER BY "% Conversão" DESC NULLS LAST
""",
    "kpi_funil": """
SELECT
  (SELECT COUNT(*) FROM gold.fato_leads)                                    AS "Total Leads",
  (SELECT COUNT(*) FROM gold.fato_agendamentos WHERE flag_agendamento = 1)  AS "Agendamentos",
  (SELECT COUNT(*) FROM gold.fato_agendamentos WHERE flag_visita = 1)       AS "Visitas",
  (SELECT COUNT(*) FROM gold.fato_vendas)                                   AS "Vendas",
  ROUND((100.0 *
    (SELECT COUNT(*) FROM gold.fato_vendas) /
    NULLIF((SELECT COUNT(*) FROM gold.fato_leads), 0))::numeric, 1)         AS "Conv. Lead→Venda (%)"
""",

    # ── PERFORMANCE DE VENDAS ────────────────────────────────────────────────
    "vendas_vs_meta_vendedor": """
SELECT v.nome AS "Vendedor",
       l.loja AS "Loja",
       COUNT(fv.id_venda)           AS "Vendas Realizadas",
       COALESCE(SUM(mv.meta_qtd), 0) AS "Meta",
       ROUND((100.0 * COUNT(fv.id_venda) /
             NULLIF(SUM(mv.meta_qtd), 0))::numeric, 1) AS "% Atingimento"
FROM gold.dim_vendedores v
LEFT JOIN gold.fato_vendas fv        ON fv.id_vendedor = v.id_vendedor
LEFT JOIN gold.dim_lojas l           ON fv.id_loja = l.id_loja
LEFT JOIN gold.dim_data d            ON fv.id_data = d.id_data
LEFT JOIN gold.fato_meta_vendedor mv ON mv.id_vendedor = v.id_vendedor
WHERE v.status = 'ativo'
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY v.nome, l.loja
ORDER BY "Vendas Realizadas" DESC
""",
    "vendas_vs_meta_loja": """
SELECT l.loja AS "Loja",
       COUNT(fv.id_venda)            AS "Vendas Realizadas",
       COALESCE(SUM(ml.meta_qtd), 0) AS "Meta",
       ROUND((100.0 * COUNT(fv.id_venda) /
             NULLIF(SUM(ml.meta_qtd), 0))::numeric, 1) AS "% Atingimento"
FROM gold.dim_lojas l
LEFT JOIN gold.fato_vendas fv     ON fv.id_loja = l.id_loja
LEFT JOIN gold.dim_data d         ON fv.id_data = d.id_data
LEFT JOIN gold.fato_meta_loja ml  ON ml.id_loja = l.id_loja
WHERE 1=1
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY l.loja
ORDER BY l.loja
""",
    "ticket_medio_mes": """
SELECT d.ano_mes_desc AS "Mês",
       ROUND(AVG(fv.valor_venda)::numeric, 0) AS "Ticket Médio (R$)",
       ROUND(AVG(fv.desconto)::numeric, 0)    AS "Desconto Médio (R$)"
FROM gold.fato_vendas fv
JOIN gold.dim_data d ON fv.id_data = d.id_data
WHERE 1=1
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY d.ano_mes_desc, d.ano_mes
ORDER BY d.ano_mes
""",
    "ranking_vendedores": """
SELECT v.nome AS "Vendedor",
       l.loja AS "Loja",
       COUNT(fv.id_venda)                    AS "Vendas",
       ROUND(SUM(fv.valor_venda)::numeric, 0) AS "Receita (R$)",
       ROUND(AVG(fv.valor_venda)::numeric, 0) AS "Ticket Médio (R$)",
       ROUND(SUM(fv.comissao)::numeric, 0)    AS "Comissão (R$)",
       ROUND((100.0 * AVG(fv.desconto /
             NULLIF(fv.valor_venda, 0)))::numeric, 1) AS "Desc. Médio (%)"
FROM gold.fato_vendas fv
JOIN gold.dim_vendedores v ON fv.id_vendedor = v.id_vendedor
JOIN gold.dim_lojas l      ON fv.id_loja = l.id_loja
JOIN gold.dim_data d       ON fv.id_data = d.id_data
WHERE 1=1
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY v.nome, l.loja
ORDER BY "Vendas" DESC
""",
    "vendas_por_mes_loja": """
SELECT d.ano_mes_desc AS "Mês", l.loja AS "Loja",
       COUNT(fv.id_venda)                     AS "Vendas",
       ROUND(SUM(fv.valor_venda)::numeric, 0)  AS "Receita (R$)"
FROM gold.fato_vendas fv
JOIN gold.dim_data d  ON fv.id_data = d.id_data
JOIN gold.dim_lojas l ON fv.id_loja = l.id_loja
WHERE 1=1
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY d.ano_mes_desc, d.ano_mes, l.loja
ORDER BY d.ano_mes
""",

    # ── FINANCEIRO ───────────────────────────────────────────────────────────
    "lucro_por_mes": """
SELECT d.ano_mes_desc AS "Mês",
       ROUND(SUM(fv.valor_venda)::numeric, 0)  AS "Receita (R$)",
       ROUND(SUM(fv.valor_compra)::numeric, 0) AS "Custo Compra (R$)",
       ROUND(SUM(fv.custos)::numeric, 0)       AS "Outros Custos (R$)",
       ROUND(SUM(fv.lucro)::numeric, 0)        AS "Lucro (R$)",
       ROUND(SUM(fv.impostos)::numeric, 0)     AS "Impostos (R$)",
       ROUND(SUM(fv.comissao)::numeric, 0)     AS "Comissões (R$)"
FROM gold.fato_vendas fv
JOIN gold.dim_data d ON fv.id_data = d.id_data
WHERE 1=1
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY d.ano_mes_desc, d.ano_mes
ORDER BY d.ano_mes
""",
    "margem_por_loja": """
SELECT l.loja AS "Loja",
       COUNT(fv.id_venda)                    AS "Vendas",
       ROUND(SUM(fv.valor_venda)::numeric, 0) AS "Receita (R$)",
       ROUND(SUM(fv.lucro)::numeric, 0)       AS "Lucro (R$)",
       ROUND((100.0 * SUM(fv.lucro) /
             NULLIF(SUM(fv.valor_venda), 0))::numeric, 1) AS "Margem (%)",
       ROUND(SUM(fv.comissao)::numeric, 0)    AS "Comissões (R$)",
       ROUND(SUM(fv.impostos)::numeric, 0)    AS "Impostos (R$)"
FROM gold.fato_vendas fv
JOIN gold.dim_lojas l ON fv.id_loja = l.id_loja
JOIN gold.dim_data d  ON fv.id_data = d.id_data
WHERE 1=1
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY l.loja
ORDER BY "Lucro (R$)" DESC
""",
    "kpi_financeiro": """
SELECT
  ROUND(SUM(valor_venda)::numeric, 0)  AS "Receita Total (R$)",
  ROUND(SUM(lucro)::numeric, 0)        AS "Lucro Total (R$)",
  ROUND(SUM(comissao)::numeric, 0)     AS "Comissões Pagas (R$)",
  ROUND(SUM(impostos)::numeric, 0)     AS "Impostos (R$)",
  ROUND((100.0 * SUM(lucro) /
        NULLIF(SUM(valor_venda), 0))::numeric, 1) AS "Margem Líquida (%)"
FROM gold.fato_vendas
""",
    "retorno_por_mes": """
SELECT d.ano_mes_desc AS "Mês",
       COUNT(fv.id_venda) FILTER (WHERE fv.situacao = 'Devolvido')  AS "Devoluções",
       COUNT(fv.id_venda) FILTER (WHERE fv.situacao <> 'Devolvido') AS "Vendas Efetivas",
       ROUND((100.0 *
         COUNT(fv.id_venda) FILTER (WHERE fv.situacao = 'Devolvido') /
         NULLIF(COUNT(fv.id_venda), 0))::numeric, 1) AS "% Devoluções"
FROM gold.fato_vendas fv
JOIN gold.dim_data d ON fv.id_data = d.id_data
WHERE 1=1
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY d.ano_mes_desc, d.ano_mes
ORDER BY d.ano_mes
""",

    # ── CANAIS E LEADS ───────────────────────────────────────────────────────
    "leads_canal_mes": """
SELECT d.ano_mes_desc AS "Mês", c.canal AS "Canal",
       COUNT(*) AS "Leads"
FROM gold.fato_leads fl
JOIN gold.dim_data d  ON fl.id_data = d.id_data
JOIN gold.dim_canal c ON fl.id_canal = c.id_canal
WHERE 1=1
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY d.ano_mes_desc, d.ano_mes, c.canal
ORDER BY d.ano_mes
""",
    "conversao_canal_detalhe": """
SELECT c.canal AS "Canal",
       COUNT(fl.id)                                               AS "Leads Recebidos",
       COUNT(fl.id) FILTER (WHERE fl.convertido_flag = 1)        AS "Convertidos",
       COUNT(fl.id) FILTER (WHERE fl.perdido_flag = 1)           AS "Perdidos",
       ROUND((100.0 * COUNT(fl.id) FILTER (WHERE fl.convertido_flag = 1)
             / NULLIF(COUNT(fl.id), 0))::numeric, 1)              AS "Taxa Conversão (%)"
FROM gold.fato_leads fl
JOIN gold.dim_canal c ON fl.id_canal = c.id_canal
JOIN gold.dim_data d  ON fl.id_data = d.id_data
WHERE 1=1
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY c.canal
ORDER BY "Leads Recebidos" DESC
""",
    "agendamentos_por_canal": """
SELECT c.canal AS "Canal",
       COUNT(*) FILTER (WHERE fa.flag_agendamento = 1) AS "Agendamentos",
       COUNT(*) FILTER (WHERE fa.flag_visita = 1)      AS "Visitas",
       ROUND((100.0 * COUNT(*) FILTER (WHERE fa.flag_visita = 1) /
             NULLIF(COUNT(*) FILTER (WHERE fa.flag_agendamento = 1), 0))::numeric, 1) AS "% Visita/Agend."
FROM gold.fato_agendamentos fa
JOIN gold.dim_canal c ON fa.id_canal = c.id_canal
JOIN gold.dim_data d  ON fa.id_data_agendamento = d.id_data
WHERE 1=1
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY c.canal
ORDER BY "Agendamentos" DESC
""",
    "leads_vs_vendas_canal": """
SELECT c.canal AS "Canal",
       COUNT(DISTINCT fl.id)       AS "Leads",
       COUNT(DISTINCT fv.id_venda) AS "Vendas",
       ROUND((100.0 * COUNT(DISTINCT fv.id_venda) /
             NULLIF(COUNT(DISTINCT fl.id), 0))::numeric, 1) AS "Conversão (%)"
FROM gold.dim_canal c
LEFT JOIN gold.fato_leads fl  ON fl.id_canal = c.id_canal
LEFT JOIN gold.fato_vendas fv ON fv.id_canal = c.id_canal
GROUP BY c.canal
ORDER BY "Leads" DESC
""",

    # ── ESTOQUE E MARCA ──────────────────────────────────────────────────────
    "vendas_por_marca": """
SELECT v.marca AS "Marca",
       COUNT(fv.id_venda)                    AS "Unidades Vendidas",
       ROUND(SUM(fv.valor_venda)::numeric, 0) AS "Receita (R$)",
       ROUND(SUM(fv.lucro)::numeric, 0)       AS "Lucro (R$)",
       ROUND((100.0 * COUNT(fv.id_venda) /
             NULLIF(SUM(COUNT(fv.id_venda)) OVER (), 0))::numeric, 1) AS "Market Share (%)"
FROM gold.fato_vendas fv
JOIN gold.dim_veiculos v ON fv.id_veiculo = v.id_veiculo
JOIN gold.dim_data d     ON fv.id_data = d.id_data
WHERE v.marca IS NOT NULL AND v.marca <> 'desconhecida'
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY v.marca
ORDER BY "Unidades Vendidas" DESC
""",
    "top_modelos": """
SELECT v.modelo AS "Modelo", v.marca AS "Marca",
       COUNT(fv.id_venda)                    AS "Unidades",
       ROUND(SUM(fv.valor_venda)::numeric, 0) AS "Receita (R$)",
       ROUND(AVG(fv.valor_venda)::numeric, 0) AS "Ticket Médio (R$)"
FROM gold.fato_vendas fv
JOIN gold.dim_veiculos v ON fv.id_veiculo = v.id_veiculo
JOIN gold.dim_data d     ON fv.id_data = d.id_data
WHERE v.modelo IS NOT NULL
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY v.modelo, v.marca
ORDER BY "Unidades" DESC
LIMIT 20
""",
    "marca_por_mes": """
SELECT d.ano_mes_desc AS "Mês", v.marca AS "Marca",
       COUNT(fv.id_venda) AS "Vendas"
FROM gold.fato_vendas fv
JOIN gold.dim_data d     ON fv.id_data = d.id_data
JOIN gold.dim_veiculos v ON fv.id_veiculo = v.id_veiculo
WHERE v.marca IS NOT NULL AND v.marca <> 'desconhecida'
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY d.ano_mes_desc, d.ano_mes, v.marca
ORDER BY d.ano_mes
""",
    "perfil_veiculo_vendido": """
SELECT v.tipo AS "Tipo", v.cor AS "Cor",
       COUNT(fv.id_venda)                    AS "Vendas",
       ROUND(AVG(fv.valor_venda)::numeric, 0) AS "Ticket Médio (R$)"
FROM gold.fato_vendas fv
JOIN gold.dim_veiculos v ON fv.id_veiculo = v.id_veiculo
JOIN gold.dim_data d     ON fv.id_data = d.id_data
WHERE v.tipo IS NOT NULL
  [[AND d.data >= {{data_inicio}}::date]]
  [[AND d.data <= {{data_fim}}::date]]
GROUP BY v.tipo, v.cor
ORDER BY "Vendas" DESC
LIMIT 20
""",
}

# ---------------------------------------------------------------------------
# Build dashboards
# ---------------------------------------------------------------------------
def build_all(session):
    print("Criando cards e dashboards...")

    # ── 1. Funil Comercial ──────────────────────────────────────────────────
    c_funil_mes   = create_card(session, "Funil por Mês",           SQLS["funil_por_mes"],       "bar",   dated=True)
    c_estagio     = create_card(session, "Leads por Etapa",          SQLS["funil_por_estagio"],   "bar",   dated=True)
    c_motivos     = create_card(session, "Top Motivos de Perda",     SQLS["motivos_perda"],       "row",   dated=True)
    c_leads_canal = create_card(session, "Leads por Canal",          SQLS["leads_por_canal"],     "pie",   dated=True)
    c_conv_canal  = create_card(session, "Conversão por Canal",      SQLS["taxa_conversao_canal"],"table", dated=True)
    c_kpi_funil   = create_card(session, "KPIs — Funil Geral",       SQLS["kpi_funil"],           "table")

    d1 = create_dashboard(session, "Funil Comercial",
                          "Leads → Agendamentos → Visitas → Vendas")
    configure_dashboard(session, d1, [
        (c_kpi_funil,    0,  0, 24, 4),
        (c_funil_mes,    4,  0, 24, 10),
        (c_estagio,     14,  0, 12, 10),
        (c_leads_canal, 14, 12, 12, 10),
        (c_conv_canal,  24,  0, 12, 8),
        (c_motivos,     24, 12, 12, 8),
    ], dated_card_ids={c_funil_mes, c_estagio, c_motivos, c_leads_canal, c_conv_canal})
    print(f"  ✅ Dashboard 1 (id={d1}): Funil Comercial")

    # ── 2. Performance de Vendas ────────────────────────────────────────────
    c_vs_vendedor     = create_card(session, "Vendas vs Meta por Vendedor", SQLS["vendas_vs_meta_vendedor"], "bar",   dated=True)
    c_vs_loja         = create_card(session, "Vendas vs Meta por Loja",     SQLS["vendas_vs_meta_loja"],     "bar",   dated=True)
    c_ticket_mes      = create_card(session, "Ticket Médio por Mês",        SQLS["ticket_medio_mes"],        "line",  dated=True)
    c_ranking         = create_card(session, "Ranking de Vendedores",       SQLS["ranking_vendedores"],      "table", dated=True)
    c_vendas_loja_mes = create_card(session, "Vendas por Mês e Loja",       SQLS["vendas_por_mes_loja"],     "line",  dated=True)

    d2 = create_dashboard(session, "Performance de Vendas",
                          "Vendas realizadas vs metas, ticket médio e ranking de vendedores")
    configure_dashboard(session, d2, [
        (c_vs_loja,          0,  0, 12, 9),
        (c_vs_vendedor,      0, 12, 12, 9),
        (c_ticket_mes,       9,  0, 12, 9),
        (c_vendas_loja_mes,  9, 12, 12, 9),
        (c_ranking,         18,  0, 24, 10),
    ], dated_card_ids={c_vs_vendedor, c_vs_loja, c_ticket_mes, c_ranking, c_vendas_loja_mes})
    print(f"  ✅ Dashboard 2 (id={d2}): Performance de Vendas")

    # ── 3. Financeiro ───────────────────────────────────────────────────────
    c_kpi_fin     = create_card(session, "KPIs — Financeiro",           SQLS["kpi_financeiro"],  "table")
    c_lucro_mes   = create_card(session, "Receita, Custo e Lucro/Mês",  SQLS["lucro_por_mes"],   "line",  dated=True)
    c_margem_loja = create_card(session, "Margem por Loja",             SQLS["margem_por_loja"], "bar",   dated=True)
    c_retorno     = create_card(session, "Devoluções por Mês",          SQLS["retorno_por_mes"], "bar",   dated=True)

    d3 = create_dashboard(session, "Financeiro",
                          "Lucro, comissões, impostos e margem por loja")
    configure_dashboard(session, d3, [
        (c_kpi_fin,      0,  0, 24, 4),
        (c_lucro_mes,    4,  0, 24, 10),
        (c_margem_loja, 14,  0, 12, 9),
        (c_retorno,     14, 12, 12, 9),
    ], dated_card_ids={c_lucro_mes, c_margem_loja, c_retorno})
    print(f"  ✅ Dashboard 3 (id={d3}): Financeiro")

    # ── 4. Canais e Leads ───────────────────────────────────────────────────
    c_leads_mes   = create_card(session, "Leads por Canal/Mês",     SQLS["leads_canal_mes"],          "line",  dated=True)
    c_conv_det    = create_card(session, "Conversão por Canal",      SQLS["conversao_canal_detalhe"],  "table", dated=True)
    c_agend_canal = create_card(session, "Agendamentos por Canal",   SQLS["agendamentos_por_canal"],   "bar",   dated=True)
    c_lv_canal    = create_card(session, "Leads e Vendas por Canal", SQLS["leads_vs_vendas_canal"],    "bar")

    d4 = create_dashboard(session, "Canais e Leads",
                          "Volume e conversão de leads por canal de origem")
    configure_dashboard(session, d4, [
        (c_leads_mes,    0,  0, 24, 10),
        (c_lv_canal,    10,  0, 12, 9),
        (c_agend_canal, 10, 12, 12, 9),
        (c_conv_det,    19,  0, 24, 8),
    ], dated_card_ids={c_leads_mes, c_conv_det, c_agend_canal})
    print(f"  ✅ Dashboard 4 (id={d4}): Canais e Leads")

    # ── 5. Estoque e Marca ──────────────────────────────────────────────────
    c_marca     = create_card(session, "Vendas por Marca",           SQLS["vendas_por_marca"],         "bar",   dated=True)
    c_modelos   = create_card(session, "Top 20 Modelos Vendidos",    SQLS["top_modelos"],              "row",   dated=True)
    c_marca_mes = create_card(session, "Vendas por Marca/Mês",       SQLS["marca_por_mes"],            "line",  dated=True)
    c_perfil    = create_card(session, "Perfil do Veículo Vendido",  SQLS["perfil_veiculo_vendido"],   "table", dated=True)

    d5 = create_dashboard(session, "Estoque e Marca",
                          "Market share por marca, top modelos e perfil dos veículos vendidos")
    configure_dashboard(session, d5, [
        (c_marca,      0,  0, 12, 10),
        (c_marca_mes,  0, 12, 12, 10),
        (c_modelos,   10,  0, 12, 12),
        (c_perfil,    10, 12, 12, 12),
    ], dated_card_ids={c_marca, c_modelos, c_marca_mes, c_perfil})
    print(f"  ✅ Dashboard 5 (id={d5}): Estoque e Marca")

    print(f"\nAcesse: http://localhost:3000")


if __name__ == "__main__":
    s = login("ggguarda@gmail.com", "crm@2026")
    build_all(s)
    print("Concluído.")
