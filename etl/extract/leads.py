"""
Reads Leads.xlsx, validates schema, applies de/para for canal (R3),
computes flags and id_data, saves to silver/leads.parquet.
"""
import pandas as pd
from etl.config import RAW_PATH
from etl.utils import normalizar_colunas, normalizar_texto, salvar_silver, _validate_schema

REQUIRED = {"id", "cliente", "canal", "atendente", "conversao", "motivo", "data_criacao", "ultima_integracao"}


def extract_leads() -> pd.DataFrame:
    df = normalizar_colunas(pd.read_excel(RAW_PATH / "Leads.xlsx"))
    _validate_schema(df, REQUIRED, "Leads.xlsx")

    df["data_criacao"]      = pd.to_datetime(df["data_criacao"],      errors="coerce")
    df["ultima_integracao"] = pd.to_datetime(df["ultima_integracao"], errors="coerce")

    df["convertido_flag"] = (df["conversao"].str.lower() == "ganho").astype(int)
    df["perdido_flag"]    = (df["conversao"].str.lower() == "perdido").astype(int)

    df["id_data"] = pd.to_numeric(
        df["data_criacao"].dt.strftime("%Y%m%d"), errors="coerce"
    )
    df["id_data_ultima_integracao"] = pd.to_numeric(
        df["ultima_integracao"].dt.strftime("%Y%m%d"), errors="coerce"
    )

    # Apply de/para for canal before any join (R3)
    de_para = normalizar_colunas(pd.read_excel(RAW_PATH / "de_para_canais.xlsx"))
    de_para["canal_origem"] = normalizar_texto(de_para["canal_origem"])
    de_para["canal_padrao"] = normalizar_texto(de_para["canal_padrao"])

    df["canal"] = normalizar_texto(df["canal"])
    df = df.merge(de_para, left_on="canal", right_on="canal_origem", how="left")
    df["canal"] = df["canal_padrao"].fillna(df["canal"])
    df = df.drop(columns=["canal_origem", "canal_padrao"], errors="ignore")

    salvar_silver(df, "leads")
    return df
