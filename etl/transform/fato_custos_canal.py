import pandas as pd
from etl.utils import normalizar_texto


def build_fato_custos_canal(custos_raw: pd.DataFrame, dim_canal: pd.DataFrame) -> pd.DataFrame:
    df = custos_raw.copy()

    dc = dim_canal[["canal", "id_canal"]].copy()
    dc["canal"] = normalizar_texto(dc["canal"])

    df = df.merge(dc, on="canal", how="left")

    sem_match = df["id_canal"].isna().sum()
    if sem_match:
        canais_invalidos = df.loc[df["id_canal"].isna(), "canal"].unique().tolist()
        print(f"  ⚠️  fato_custos_canal: {sem_match} linhas sem match em dim_canal: {canais_invalidos}")

    df["id_canal"] = df["id_canal"].fillna(-1).astype(int)

    return df[["id_canal", "id_data", "custo"]].copy()
