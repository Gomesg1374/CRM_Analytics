"""
Reads all dados_canais_YYYY.xlsx files, normalizes, applies de/para for canal (R3),
saves to silver/canais.parquet.
"""
import glob
import pandas as pd
from etl.config import RAW_PATH
from etl.utils import normalizar_colunas, normalizar_texto, salvar_silver, _validate_schema

REQUIRED = {"codigo", "canal"}


def extract_canais() -> pd.DataFrame:
    files = sorted(glob.glob(str(RAW_PATH / "dados_canais_*.xlsx")))
    if not files:
        raise ValueError("Nenhum arquivo dados_canais_*.xlsx encontrado em data/raw/")

    dfs = [normalizar_colunas(pd.read_excel(f)) for f in files]
    canais = pd.concat(dfs, ignore_index=True)
    _validate_schema(canais, REQUIRED, "dados_canais_*.xlsx")

    canais = canais[["codigo", "canal"]].dropna()
    canais["codigo"] = canais["codigo"].astype(int)
    canais = canais.drop_duplicates(subset=["codigo"])
    canais["canal"] = normalizar_texto(canais["canal"])

    # Apply de/para for canal before any join (R3)
    de_para = normalizar_colunas(pd.read_excel(RAW_PATH / "de_para_canais.xlsx"))
    de_para["canal_origem"] = normalizar_texto(de_para["canal_origem"])
    de_para["canal_padrao"] = normalizar_texto(de_para["canal_padrao"])

    canais = canais.merge(de_para, left_on="canal", right_on="canal_origem", how="left")
    canais["canal"] = canais["canal_padrao"].fillna(canais["canal"])
    canais = canais[["codigo", "canal"]]

    salvar_silver(canais, "canais")
    return canais
