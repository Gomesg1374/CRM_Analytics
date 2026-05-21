import pandas as pd
import numpy as np
from datetime import datetime
import os
import glob
import unicodedata

# ==========================================
# FUNÇÕES
# ==========================================

def normalizar_texto(col):
    return (
        col.fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .apply(lambda x: unicodedata.normalize('NFKD', str(x)).encode('ascii', 'ignore').decode('utf-8'))
        .str.replace(r'[^a-z0-9 ]', '', regex=True)
        .str.replace(r'\s+', ' ', regex=True)
    )


# ==========================================
# ADICIONAR LOJA DO VENDEDOR (HISTÓRICO)
# ==========================================
# CORREÇÃO: o filtro de intervalo de datas antes usava df = df[condição], o que
# DROPAVA silenciosamente linhas sem match no histórico (ex: vendedor recém-contratado
# sem registro ainda). Agora usa merge com indicador + fillna(-1) para garantir
# que NENHUMA linha seja perdida — vendedores sem match ficam com id_loja = -1.

def adicionar_vendedor_loja(df, col_nome, col_data, dim_vendedores, hist_vendedor_loja, de_para_vend):

    # Normaliza nome do vendedor
    df = df.copy()
    df[col_nome] = normalizar_texto(df[col_nome])

    # De/para: padroniza variações de nome
    df = df.merge(de_para_vend, left_on=col_nome, right_on="nome_origem", how="left")
    df[col_nome] = df["nome_padrao"].fillna(df[col_nome])
    df = df.drop(columns=["nome_origem", "nome_padrao"])

    # Busca id_vendedor pelo nome padronizado
    df = df.merge(
        dim_vendedores[["id_vendedor", "nome"]],
        left_on=col_nome,
        right_on="nome",
        how="left"
    ).drop(columns=["nome"])

    # Garante que id_vendedor nulo vira -1 (desconhecido)
    df["id_vendedor"] = df["id_vendedor"].fillna(-1).astype(int)

    # Garante tipo datetime em ambos os lados
    df[col_data] = pd.to_datetime(df[col_data])
    hist = hist_vendedor_loja.copy()
    hist["data_inicio"] = pd.to_datetime(hist["data_inicio"])
    hist["data_fim"]    = pd.to_datetime(hist["data_fim"]).fillna(pd.Timestamp("2099-12-31"))

    # --- CORREÇÃO DO BUG ---
    # Antes: merge + df = df[filtro_data] → linhas sem match eram DROPADAS
    # Agora: merge com indicator → filtra só os que batem no período →
    #        reintegra os sem match com id_loja = -1 via combine_first
    df_idx = df.reset_index(drop=False).rename(columns={"index": "_orig_idx"})

    merged = df_idx.merge(
        hist[["id_vendedor", "id_loja", "data_inicio", "data_fim"]],
        on="id_vendedor",
        how="left",
        indicator=True
    )

    # Filtra apenas o intervalo correto
    no_match   = merged["_merge"] == "left_only"
    in_period  = (merged[col_data] >= merged["data_inicio"]) & (merged[col_data] <= merged["data_fim"])
    matched    = merged[in_period | no_match].copy()

    # Se um vendedor aparece em mais de um período (overlap), pega o mais recente
    matched = (
        matched
        .sort_values("data_inicio", ascending=False)
        .drop_duplicates(subset=["_orig_idx"])
    )

    # Garante que id_loja sem match fica -1
    matched["id_loja"] = matched["id_loja"].fillna(-1).astype(int)

    # Restaura o DataFrame original com a coluna id_loja resolvida
    df_final = df_idx.merge(
        matched[["_orig_idx", "id_loja"]],
        on="_orig_idx",
        how="left"
    ).drop(columns=["_orig_idx", "_merge"], errors="ignore")

    df_final["id_loja"] = df_final["id_loja"].fillna(-1).astype(int)

    return df_final


# ==========================================
# CONFIG
# ==========================================

RAW_PATH  = "data/raw/"
GOLD_PATH = "data/gold/"

os.makedirs(GOLD_PATH, exist_ok=True)


# ==========================================
# 1. LEADS
# ==========================================

print("📥 Lendo Leads...")
df = pd.read_excel(f"{RAW_PATH}Leads.xlsx")

df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
df.columns = [unicodedata.normalize('NFKD', col).encode('ascii','ignore').decode('utf-8') for col in df.columns]

df["data_criacao"]      = pd.to_datetime(df["data_criacao"],      errors="coerce")
df["ultima_integracao"] = pd.to_datetime(df["ultima_integracao"], errors="coerce")

df["convertido_flag"] = np.where(df["conversao"].str.lower() == "ganho",    1, 0)
df["perdido_flag"]    = np.where(df["conversao"].str.lower() == "perdido",  1, 0)

df["id_data"] = pd.to_numeric(df["data_criacao"].dt.strftime("%Y%m%d"), errors="coerce")
df["id_data_ultima_integracao"] = pd.to_numeric(df["ultima_integracao"].dt.strftime("%Y%m%d"), errors="coerce")


# ==========================================
# 2. VENDAS
# ==========================================

print("💰 Lendo Vendas...")

arquivos_vendas = glob.glob(f"{RAW_PATH}Vendas_*.xlsx")

vendas = pd.concat([
    pd.read_excel(f).rename(columns=lambda x: x.strip().lower().replace(" ", "_"))
    for f in arquivos_vendas
], ignore_index=True)

vendas = vendas.rename(columns={
    "código":         "id_venda",
    "dt._venda":      "data_venda",
    "vendedor":       "nome_vendedor",
    "venda":          "valor_venda",
    "compra":         "valor_compra",
    "lançamentos":    "custos",
    "situação":       "situacao",
    "desconto_venda": "desconto",
    "data_compra":    "data_compra"
})

vendas["data_venda"] = pd.to_datetime(vendas["data_venda"], errors="coerce")
vendas["id_data"]    = pd.to_numeric(vendas["data_venda"].dt.strftime("%Y%m%d"), errors="coerce")
vendas["ano_mes"]    = vendas["data_venda"].dt.year * 100 + vendas["data_venda"].dt.month

# CORREÇÃO: adiciona id_data à meta para conectar via Int64 no Power BI
# (evita relacionamento por coluna DateTime que pode causar não-match)


# ==========================================
# 3. CANAIS
# ==========================================

print("📡 Lendo canais...")

arquivos_canais = glob.glob(f"{RAW_PATH}dados_canais_*.xlsx")

canais = pd.concat([pd.read_excel(f) for f in arquivos_canais], ignore_index=True)
canais.columns = canais.columns.str.strip().str.lower().str.replace(" ", "_")
canais.columns = [unicodedata.normalize('NFKD', col).encode('ascii','ignore').decode('utf-8') for col in canais.columns]

canais = canais[["codigo", "canal"]].dropna()
canais["codigo"] = canais["codigo"].astype(int)
canais = canais.drop_duplicates(subset=["codigo"])
canais["canal"] = normalizar_texto(canais["canal"])


# ==========================================
# DE/PARA
# ==========================================

de_para = pd.read_excel(f"{RAW_PATH}de_para_canais.xlsx")
de_para.columns = de_para.columns.str.lower().str.strip()
de_para["canal_origem"] = normalizar_texto(de_para["canal_origem"])
de_para["canal_padrao"] = normalizar_texto(de_para["canal_padrao"])

de_para_vend = pd.read_excel(f"{RAW_PATH}de_para_vendedores.xlsx")
de_para_vend.columns = de_para_vend.columns.str.lower().str.strip()
de_para_vend["nome_origem"] = normalizar_texto(de_para_vend["nome_origem"])
de_para_vend["nome_padrao"] = normalizar_texto(de_para_vend["nome_padrao"])

df["canal"]     = normalizar_texto(df["canal"])
df = df.merge(de_para, left_on="canal", right_on="canal_origem", how="left")
df["canal"]     = df["canal_padrao"].fillna(df["canal"])

canais = canais.merge(de_para, left_on="canal", right_on="canal_origem", how="left")
canais["canal"] = canais["canal_padrao"].fillna(canais["canal"])

vendas = vendas.merge(
    canais[["codigo", "canal"]],
    left_on="id_venda",
    right_on="codigo",
    how="left"
).drop(columns=["codigo"])


# ==========================================
# DIMENSÕES
# ==========================================

print("🏗 Criando dimensões...")

dim_canal = pd.DataFrame({
    "canal": pd.concat([df["canal"], vendas["canal"]]).dropna().unique()
})
dim_canal["id_canal"] = dim_canal.index + 1

# Vendedores
usuarios = pd.read_excel(f"{RAW_PATH}usuarios.xlsx")
usuarios.columns = usuarios.columns.str.lower().str.strip().str.replace(" ", "_")

dim_vendedores = usuarios.rename(columns={
    "id_usuario":   "id_vendedor",
    "nome_usuario": "nome"
})

dim_vendedores = pd.concat([
    dim_vendedores,
    pd.DataFrame([{"id_vendedor": -1, "nome": "desconhecido"}])
])
dim_vendedores["nome"] = normalizar_texto(dim_vendedores["nome"])

# Histórico vendedor/loja
hist = pd.read_excel(f"{RAW_PATH}hist_vendedor_loja.xlsx")
hist.columns = hist.columns.str.lower().str.strip().str.replace(" ", "_")
hist["data_inicio"] = pd.to_datetime(hist["data_inicio"])
hist["data_fim"]    = pd.to_datetime(hist["data_fim"]).fillna(pd.Timestamp("2099-12-31"))

# ------------------------------------------------------------------
# dim_vendedor_periodo
# OBSERVAÇÃO: esta tabela é mantida no ETL para auditoria e para
# resolver o histórico nas fatos. Ela NÃO deve ser usada como bridge
# table no Power BI — o relacionamento M:M bidirecional deve ser
# REMOVIDO do modelo. O id_loja já vem resolvido historicamente em
# cada fato (fato_vendas, fato_leads, fato_agendamentos) pela função
# adicionar_vendedor_loja().
# ------------------------------------------------------------------
hist["mes_inicio"] = hist["data_inicio"].dt.to_period("M")
hist["mes_fim"]    = hist["data_fim"].dt.to_period("M")
hist["n_meses"]    = (hist["mes_fim"] - hist["mes_inicio"]).apply(lambda x: x.n) + 1

hist_exp = hist.loc[hist.index.repeat(hist["n_meses"])].copy()
hist_exp["mes_seq"] = hist_exp.groupby(level=0).cumcount()
hist_exp["ano_mes"] = (
    hist_exp["mes_inicio"] + hist_exp["mes_seq"]
).astype(str).str.replace("-", "").astype(int)

dim_vendedor_periodo = (
    hist_exp[["id_vendedor", "id_loja", "ano_mes"]]
    .drop_duplicates(subset=["id_vendedor", "ano_mes"])
)

dim_lojas = pd.concat([
    hist[["id_loja", "loja"]].drop_duplicates(),
    pd.DataFrame([{"id_loja": -1, "loja": "desconhecida"}])
])


# ==========================================
# DIM VEÍCULOS
# ==========================================

print("🚗 Criando dim_veiculos...")

arquivo_veiculos = glob.glob(f"{RAW_PATH}gerencial_estoque*.xlsx")[0]
veiculos = pd.read_excel(arquivo_veiculos)
veiculos.columns = veiculos.columns.str.strip().str.lower().str.replace(" ", "_")
veiculos.columns = [
    unicodedata.normalize('NFKD', col).encode('ascii','ignore').decode('utf-8')
    for col in veiculos.columns
]

dim_veiculos = veiculos[["codigo", "modelo", "ano", "cor", "tipo", "placa", "situacao"]].drop_duplicates()
dim_veiculos["id_veiculo"] = dim_veiculos["codigo"]

for col in ["modelo", "cor", "tipo", "situacao"]:
    dim_veiculos[col] = normalizar_texto(dim_veiculos[col])


# ==========================================
# AGENDAMENTOS
# ==========================================

print("📅 Criando fato_agendamentos...")

ag = pd.read_excel(f"{RAW_PATH}controleagendamentos.xlsx")
ag.columns = ag.columns.str.lower().str.strip().str.replace(" ", "_")
ag.columns = [unicodedata.normalize('NFKD', c).encode('ascii','ignore').decode('utf-8') for c in ag.columns]

ag["criacao_agendamento"] = pd.to_datetime(ag["criacao_agendamento"], errors="coerce")
ag["agendado_para"]       = pd.to_datetime(ag["agendado_para"],       errors="coerce")

ag["id_data_agendamento"] = pd.to_numeric(ag["criacao_agendamento"].dt.strftime("%Y%m%d"), errors="coerce")
ag["id_data_visita"]      = pd.to_numeric(ag["agendado_para"].dt.strftime("%Y%m%d"),       errors="coerce")

ag["flag_agendamento"] = np.where(ag["flag_agendamento"].str.lower() == "sim", 1, 0)
ag["flag_visita"]      = np.where(ag["flag_visita"].str.lower()       == "sim", 1, 0)

ag["canal"] = normalizar_texto(ag["canal"])
ag = ag.merge(de_para, left_on="canal", right_on="canal_origem", how="left")
ag["canal"] = ag["canal_padrao"].fillna(ag["canal"])
ag = ag.merge(dim_canal, on="canal", how="left")

ag = adicionar_vendedor_loja(
    ag, "responsavel_agendamento", "criacao_agendamento",
    dim_vendedores, hist, de_para_vend
)

fato_agendamentos = ag[[
    "id", "id_vendedor", "id_loja", "id_canal",
    "id_data_agendamento", "id_data_visita",
    "flag_agendamento", "flag_visita", "campanha", "status", "motivo", "id_venda"
]]


# ==========================================
# LEADS
# ==========================================

print("🎯 Criando fato_leads...")

fato_leads = adicionar_vendedor_loja(
    df, "atendente", "data_criacao",
    dim_vendedores, hist, de_para_vend
)

fato_leads = fato_leads.merge(dim_canal, on="canal", how="left")

dim_estagio = df[["estagio"]].drop_duplicates()
dim_estagio["id_estagio"] = range(1, len(dim_estagio) + 1)
fato_leads = fato_leads.merge(dim_estagio, on="estagio", how="left")

fato_leads = fato_leads[[
    "id", "id_vendedor", "id_loja", "id_canal",
    "id_estagio", "id_data", "id_data_ultima_integracao",
    "convertido_flag", "perdido_flag", "motivo"
]]

# Propaga SDR para leads
print("🔗 Propagando SDR para leads...")
sdr_por_lead = (
    fato_agendamentos[["id", "id_vendedor"]]
    .rename(columns={"id_vendedor": "id_sdr"})
    .drop_duplicates(subset=["id"])
)
fato_leads = fato_leads.merge(sdr_por_lead, on="id", how="left")


# ==========================================
# VENDAS
# ==========================================

print("💰 Criando fato_vendas...")

vendas["canal"] = normalizar_texto(vendas["canal"])
vendas = vendas.merge(dim_canal, on="canal", how="left")

vendas = adicionar_vendedor_loja(
    vendas, "nome_vendedor", "data_venda",
    dim_vendedores, hist, de_para_vend
)

vendas = vendas.merge(
    dim_veiculos[["id_veiculo"]],
    left_on="id_venda",
    right_on="id_veiculo",
    how="left"
)

fato_vendas = vendas[[
    "id_venda", "id_veiculo", "id_vendedor", "id_loja",
    "id_canal", "id_data", "ano_mes",
    "placa", "modelo", "cliente",
    "valor_venda", "valor_compra", "custos",
    "situacao", "data_compra", "desconto"
]]


# ==========================================
# METAS
# CORREÇÃO: adicionada coluna id_data (Int64 YYYYMMDD) em ambas as
# tabelas de meta, para substituir o relacionamento via DateTime
# no Power BI. No modelo, usar id_data → dim_data[id_data].
# ==========================================

print("🎯 Criando fato_meta_vendedor...")

meta_vend = pd.read_excel(f"{RAW_PATH}meta_vendedor.xlsx")
meta_vend.columns = meta_vend.columns.str.lower().str.strip()
meta_vend["ano_mes"] = meta_vend["ano_mes"].astype(int)
meta_vend["data_meta"] = pd.to_datetime(meta_vend["ano_mes"].astype(str) + "01", format="%Y%m%d")
meta_vend["id_data"] = (meta_vend["ano_mes"].astype(str) + "01").astype(int)

fato_meta_vendedor = meta_vend.merge(
    dim_vendedor_periodo[['id_vendedor', 'ano_mes', 'id_loja']],
    on=['id_vendedor', 'ano_mes'],
    how='left'
)

# ✅ linha 415 — trocar meta_vend por fato_meta_vendedor
fato_meta_vendedor = fato_meta_vendedor[["id_vendedor", "ano_mes", "data_meta", "id_data", "id_loja", "meta_qtd"]]

sem_loja = fato_meta_vendedor["id_loja"].isna().sum()
if sem_loja > 0:
    print(f"  ⚠️  {sem_loja} linha(s) sem id_loja — vendedor sem período em dim_vendedor_periodo")
else:
    print(f"  ✅ {len(fato_meta_vendedor)} linhas OK")



print("🎯 Criando fato_meta_loja...")

meta_loja = pd.read_excel(f"{RAW_PATH}meta_loja.xlsx")
meta_loja.columns = meta_loja.columns.str.lower().str.strip()
meta_loja["ano_mes"] = meta_loja["ano_mes"].astype(int)
meta_loja["data_meta"] = pd.to_datetime(meta_loja["ano_mes"].astype(str) + "01", format="%Y%m%d")
# Nova coluna id_data para relacionamento correto com dim_data
meta_loja["id_data"] = (meta_loja["ano_mes"].astype(str) + "01").astype(int)

fato_meta_loja = meta_loja[["id_loja", "ano_mes", "data_meta", "id_data", "meta_qtd"]]


# ==========================================
# DIM DATA
# ==========================================

print("📅 Criando dim_data...")

dim_data = pd.DataFrame({
    "data": pd.date_range(start="2022-01-01", end="2026-12-31")
})

dim_data["id_data"]      = dim_data["data"].dt.strftime("%Y%m%d").astype(int)
dim_data["ano"]          = dim_data["data"].dt.year
dim_data["mes"]          = dim_data["data"].dt.month
dim_data["ano_mes"]      = dim_data["ano"] * 100 + dim_data["mes"]
dim_data["nome_mes"]     = dim_data["data"].dt.strftime("%B")
dim_data["ano_mes_desc"] = dim_data["data"].dt.strftime("%Y-%m")

dim_data = dim_data.drop_duplicates(subset=["id_data"])

# Nota: as colunas extras (trimestre, semestre, feriados, dias úteis etc.)
# são geradas via Power Query M no próprio Power BI — ver dim_data_M_completo.pq


# ==========================================
# DIAGNÓSTICO
# ==========================================

print("\n🔍 DIAGNÓSTICO:")
print(f"  Leads sem vendedor:          {fato_leads['id_vendedor'].eq(-1).mean():.1%}")
print(f"  Leads sem loja:              {fato_leads['id_loja'].eq(-1).mean():.1%}")
print(f"  Vendas sem vendedor:         {fato_vendas['id_vendedor'].eq(-1).mean():.1%}")
print(f"  Vendas sem loja:             {fato_vendas['id_loja'].eq(-1).mean():.1%}")
print(f"  Agendamentos sem vendedor:   {fato_agendamentos['id_vendedor'].eq(-1).mean():.1%}")
print(f"  Agendamentos sem loja:       {fato_agendamentos['id_loja'].eq(-1).mean():.1%}")
print(f"  Total leads:                 {len(fato_leads):,}")
print(f"  Total vendas:                {len(fato_vendas):,}")
print(f"  Total agendamentos:          {len(fato_agendamentos):,}")


# ==========================================
# SAVE
# ==========================================

print("\n💾 Salvando parquets...")

# Garante tipos corretos antes de salvar
for col in ["id_vendedor", "id_loja", "id_canal"]:
    for df_fato in [fato_leads, fato_vendas, fato_agendamentos]:
        if col in df_fato.columns:
            df_fato[col] = df_fato[col].fillna(-1).astype(int)

dim_canal.to_parquet(            f"{GOLD_PATH}dim_canal.parquet",             index=False)
dim_data.to_parquet(             f"{GOLD_PATH}dim_data.parquet",              index=False)
dim_vendedores.to_parquet(       f"{GOLD_PATH}dim_vendedores.parquet",        index=False)
dim_lojas.to_parquet(            f"{GOLD_PATH}dim_lojas.parquet",             index=False)
dim_vendedor_periodo.to_parquet( f"{GOLD_PATH}dim_vendedor_periodo.parquet",  index=False)
dim_estagio.to_parquet(          f"{GOLD_PATH}dim_estagio.parquet",           index=False)
dim_veiculos.to_parquet(         f"{GOLD_PATH}dim_veiculos.parquet",          index=False)

fato_leads.to_parquet(           f"{GOLD_PATH}fato_leads.parquet",            index=False)
fato_vendas.to_parquet(          f"{GOLD_PATH}fato_vendas.parquet",           index=False)
fato_agendamentos.to_parquet(    f"{GOLD_PATH}fato_agendamentos.parquet",     index=False)
fato_meta_vendedor.to_parquet(   f"{GOLD_PATH}fato_meta_vendedor.parquet",    index=False)
fato_meta_loja.to_parquet(       f"{GOLD_PATH}fato_meta_loja.parquet",        index=False)

print("✅ FINALIZADO COM SUCESSO")