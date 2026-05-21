"""
Reads all Vendas_comissao_YYYY.xlsx files.
Returns a DataFrame with [id_venda, comissao, impostos, lucro, retorno].
If no files are found, returns an empty DataFrame with those columns.
Saves to silver/comissoes.parquet.
"""
import glob
import pandas as pd
from etl.config import OUTROS_PATH
from etl.utils import normalizar_colunas, salvar_silver

_COLS = ["comissao", "impostos", "lucro", "retorno"]


def extract_comissoes() -> pd.DataFrame:
    files = sorted(glob.glob(str(OUTROS_PATH / "Vendas_comissao_*.xlsx")))

    if not files:
        empty = pd.DataFrame(columns=["id_venda"] + _COLS)
        salvar_silver(empty, "comissoes")
        return empty

    dfs = [normalizar_colunas(pd.read_excel(f)) for f in files]
    comissoes = pd.concat(dfs, ignore_index=True)

    comissoes = (
        comissoes[["codigo"] + _COLS]
        .rename(columns={"codigo": "id_venda"})
        .dropna(subset=["id_venda"])
        .drop_duplicates(subset=["id_venda"])
    )
    comissoes["id_venda"] = pd.to_numeric(comissoes["id_venda"], errors="coerce")
    for col in _COLS:
        comissoes[col] = pd.to_numeric(comissoes[col], errors="coerce")

    salvar_silver(comissoes, "comissoes")
    return comissoes
