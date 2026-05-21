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

RAW_PATH    = "data/raw/"
OUTROS_PATH = "data/outros/"
GOLD_PATH   = "data/gold/"

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

def _normalizar_colunas(df):
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    df.columns = [unicodedata.normalize('NFKD', c).encode('ascii','ignore').decode('utf-8') for c in df.columns]
    return df

veiculos = _normalizar_colunas(pd.read_excel(f"{RAW_PATH}gerencial_estoque.xlsx"))

dim_veiculos = veiculos[["codigo", "modelo", "ano", "cor", "tipo", "placa", "situacao"]].drop_duplicates().copy()
dim_veiculos["id_veiculo"] = dim_veiculos["codigo"]

# --- Enriquecimento de marca (R7): estoque atual → histórico de vendas → "desconhecida" ---

# Passo 1: gerencial_estoque_marca.xlsx (cobertura: estoque atual)
em = _normalizar_colunas(pd.read_excel(f"{OUTROS_PATH}gerencial_estoque_marca.xlsx"))
em = em[["codigo", "marca"]].dropna(subset=["codigo", "marca"]).drop_duplicates(subset=["codigo"])
em["codigo"] = pd.to_numeric(em["codigo"], errors="coerce").astype("Int64")
dim_veiculos = dim_veiculos.merge(em.rename(columns={"marca": "_marca_estoque"}), on="codigo", how="left")
dim_veiculos["marca"] = dim_veiculos["_marca_estoque"]
dim_veiculos = dim_veiculos.drop(columns=["_marca_estoque"])

# Passo 2: Vendas_Marca_YYYY.xlsx — marca mais recente por Código para os ainda sem marca
vendas_marca_files = glob.glob(f"{OUTROS_PATH}Vendas_Marca_*.xlsx")
if vendas_marca_files:
    vm = pd.concat([_normalizar_colunas(pd.read_excel(f)) for f in vendas_marca_files], ignore_index=True)
    date_col = next((c for c in vm.columns if c.startswith("dt")), None)
    vm["_dt_venda"] = pd.to_datetime(vm[date_col], errors="coerce") if date_col else pd.NaT
    vm["codigo"] = pd.to_numeric(vm["codigo"], errors="coerce")
    vm = vm.dropna(subset=["codigo", "marca"])
    vm["codigo"] = vm["codigo"].astype("Int64")
    vm_latest = (
        vm.sort_values("_dt_venda", ascending=False)
        .drop_duplicates(subset=["codigo"])
        [["codigo", "marca"]]
    )
    dim_veiculos = dim_veiculos.merge(vm_latest.rename(columns={"marca": "_marca_hist"}), on="codigo", how="left")
    dim_veiculos["marca"] = dim_veiculos["marca"].fillna(dim_veiculos["_marca_hist"])
    dim_veiculos = dim_veiculos.drop(columns=["_marca_hist"])

# Passo 3: restantes sem marca
dim_veiculos["marca"] = dim_veiculos["marca"].fillna("desconhecida")

for col in ["marca", "modelo", "cor", "tipo", "situacao"]:
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
]].copy()

# --- F1.2: enriquecer fato_vendas com dados financeiros (R6: left join, nunca perde linhas) ---
arquivos_comissao = glob.glob(f"{OUTROS_PATH}Vendas_comissao_*.xlsx")
if arquivos_comissao:
    comissoes = pd.concat(
        [_normalizar_colunas(pd.read_excel(f)) for f in arquivos_comissao],
        ignore_index=True
    )
    comissoes = (
        comissoes[["codigo", "comissao", "impostos", "lucro", "retorno"]]
        .rename(columns={"codigo": "id_venda"})
        .dropna(subset=["id_venda"])
        .drop_duplicates(subset=["id_venda"])
    )
    comissoes["id_venda"] = pd.to_numeric(comissoes["id_venda"], errors="coerce")
    for col in ["comissao", "impostos", "lucro", "retorno"]:
        comissoes[col] = pd.to_numeric(comissoes[col], errors="coerce")
    fato_vendas = fato_vendas.merge(comissoes, on="id_venda", how="left")
else:
    for col in ["comissao", "impostos", "lucro", "retorno"]:
        fato_vendas[col] = np.nan


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

from datetime import date as _date

_MESES_PT = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
             "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
_DIAS_PT  = ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"]

def _dias_uteis_mes(ano, mes):
    inicio = _date(ano, mes, 1)
    fim    = _date(ano + 1, 1, 1) if mes == 12 else _date(ano, mes + 1, 1)
    return int(np.busday_count(inicio, fim))

dim_data = pd.DataFrame({
    "data": pd.date_range(start="2022-01-01", end="2027-12-31")
})

dim_data["id_data"]        = dim_data["data"].dt.strftime("%Y%m%d").astype(int)
dim_data["ano"]            = dim_data["data"].dt.year
dim_data["mes"]            = dim_data["data"].dt.month
dim_data["ano_mes"]        = dim_data["ano"] * 100 + dim_data["mes"]
dim_data["nome_mes"]       = dim_data["mes"].apply(lambda m: _MESES_PT[m - 1])
dim_data["ano_mes_desc"]   = dim_data["data"].dt.strftime("%Y-%m")
dim_data["trimestre"]      = ((dim_data["mes"] - 1) // 3) + 1
dim_data["semestre"]       = (dim_data["mes"] > 6).astype(int) + 1
dim_data["num_dia_semana"] = dim_data["data"].dt.dayofweek   # 0=Segunda … 6=Domingo
dim_data["dia_semana"]     = dim_data["num_dia_semana"].apply(lambda d: _DIAS_PT[d])
dim_data["fim_de_semana"]  = (dim_data["num_dia_semana"] >= 5).astype(int)

_ano_mes_uteis = (
    dim_data[["ano", "mes"]].drop_duplicates()
    .assign(dias_uteis_mes=lambda df: df.apply(
        lambda r: _dias_uteis_mes(int(r["ano"]), int(r["mes"])), axis=1
    ))
)
dim_data = dim_data.merge(_ano_mes_uteis, on=["ano", "mes"], how="left")


# ==========================================
# DIAGNÓSTICO
# ==========================================

def _check(label, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    suffix = f"  ({detail})" if detail else ""
    print(f"  {status}  {label}{suffix}")
    return passed

print("\n🔍 DIAGNÓSTICO — match rates:")
print(f"  Leads:        vendedor sem match {fato_leads['id_vendedor'].eq(-1).mean():.1%} | loja sem match {fato_leads['id_loja'].eq(-1).mean():.1%}")
print(f"  Vendas:       vendedor sem match {fato_vendas['id_vendedor'].eq(-1).mean():.1%} | loja sem match {fato_vendas['id_loja'].eq(-1).mean():.1%}")
print(f"  Agendamentos: vendedor sem match {fato_agendamentos['id_vendedor'].eq(-1).mean():.1%} | loja sem match {fato_agendamentos['id_loja'].eq(-1).mean():.1%}")

print("\n📊 CONTAGENS:")
print(f"  fato_leads:         {len(fato_leads):,}")
print(f"  fato_vendas:        {len(fato_vendas):,}")
print(f"  fato_agendamentos:  {len(fato_agendamentos):,}")
print(f"  dim_veiculos:       {len(dim_veiculos):,}")
print(f"  dim_data:           {len(dim_data):,}")

# --- F1.4: critérios de aceite ---
print("\n✔️  F1.4 — CRITÉRIOS DE ACEITE:")
checks = []

# Marca: < 5% desconhecida entre veículos não-devolvidos
nao_devolvido = dim_veiculos[dim_veiculos["situacao"] != "devolvido"]
marca_desc_pct = nao_devolvido["marca"].eq("desconhecida").mean()
checks.append(_check(
    f"Marca: desconhecida < 5% (excl. Devolvido)",
    marca_desc_pct < 0.05,
    f"{marca_desc_pct:.1%} desconhecida entre {len(nao_devolvido):,} veículos ativos"
))

# Comissão: cobertura >= 90%
comissao_cob = fato_vendas["comissao"].notna().mean()
checks.append(_check(
    "Comissão: cobertura >= 90% em fato_vendas",
    comissao_cob >= 0.90,
    f"{comissao_cob:.1%} ({fato_vendas['comissao'].notna().sum():,}/{len(fato_vendas):,} linhas)"
))

# dim_data: intervalo 2022-01-01 a 2027-12-31
data_min = dim_data["data"].min().date()
data_max = dim_data["data"].max().date()
checks.append(_check(
    "dim_data: cobre 2022-01-01 a 2027-12-31",
    str(data_min) == "2022-01-01" and str(data_max) == "2027-12-31",
    f"{data_min} → {data_max}"
))

# dim_data: sem NULLs em trimestre, semestre, dia_semana, dias_uteis_mes
cols_obrig = ["trimestre", "semestre", "dia_semana", "dias_uteis_mes"]
nulls = dim_data[cols_obrig].isnull().sum().sum()
checks.append(_check(
    "dim_data: sem NULLs em trimestre/semestre/dia_semana/dias_uteis_mes",
    nulls == 0,
    f"{nulls} NULLs encontrados"
))

# fato_vendas: nenhuma linha perdida (mesmo tamanho do DataFrame de vendas antes do join)
checks.append(_check(
    "fato_vendas: join com comissão não descartou linhas (R6)",
    len(fato_vendas) == len(vendas),
    f"{len(fato_vendas):,} linhas (esperado {len(vendas):,})"
))

n_pass = sum(checks)
print(f"\n  Resultado: {n_pass}/{len(checks)} critérios aprovados")


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

print("\n📂 VERIFICAÇÃO PÓS-SAVE (row counts gold vs memória):")
_gold_tables = {
    "dim_canal":           dim_canal,
    "dim_data":            dim_data,
    "dim_vendedores":      dim_vendedores,
    "dim_lojas":           dim_lojas,
    "dim_veiculos":        dim_veiculos,
    "dim_estagio":         dim_estagio,
    "dim_vendedor_periodo":dim_vendedor_periodo,
    "fato_leads":          fato_leads,
    "fato_vendas":         fato_vendas,
    "fato_agendamentos":   fato_agendamentos,
    "fato_meta_vendedor":  fato_meta_vendedor,
    "fato_meta_loja":      fato_meta_loja,
}
_all_match = True
for _nome, _df in _gold_tables.items():
    _saved = pd.read_parquet(f"{GOLD_PATH}{_nome}.parquet")
    _ok = len(_saved) == len(_df)
    _all_match = _all_match and _ok
    _mark = "✅" if _ok else "❌"
    print(f"  {_mark} {_nome:<25} memória={len(_df):,}  parquet={len(_saved):,}")

print()
if _all_match and n_pass == len(checks):
    print("✅ FINALIZADO COM SUCESSO — todos os critérios aprovados")
else:
    print(f"⚠️  FINALIZADO COM AVISOS — {n_pass}/{len(checks)} critérios | parquets {'OK' if _all_match else 'DIVERGENTES'}")