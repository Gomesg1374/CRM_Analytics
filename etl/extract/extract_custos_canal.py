"""
Reads custos_plataforma.xlsx (wide format: Canal x months),
melts to long (canal, id_data, custo), saves to silver/custos_canal.parquet.
"""
import pandas as pd
from etl.config import OUTROS_PATH
from etl.utils import normalizar_texto, salvar_silver


def extract_custos_canal() -> pd.DataFrame:
    df = pd.read_excel(OUTROS_PATH / "custos_plataforma.xlsx")

    if "Canal" not in df.columns:
        raise ValueError("custos_plataforma.xlsx: coluna 'Canal' ausente")

    date_cols = [c for c in df.columns if c != "Canal"]
    if not date_cols:
        raise ValueError("custos_plataforma.xlsx: nenhuma coluna de data encontrada")

    df = df.melt(id_vars="Canal", value_vars=date_cols, var_name="data_ref", value_name="custo")
    df = df.dropna(subset=["custo"])

    df["canal"] = normalizar_texto(df["Canal"])

    df["id_data"] = pd.to_datetime(df["data_ref"], format="%d/%m/%Y", errors="coerce")
    df["id_data"] = pd.to_numeric(df["id_data"].dt.strftime("%Y%m%d"), errors="coerce").astype("Int64")

    df = df[["canal", "id_data", "custo"]].copy()
    df["custo"] = df["custo"].astype(float)

    salvar_silver(df, "custos_canal")
    print(f"  ✅ custos_canal                 {len(df):,} linhas")
    return df
