"""
Reads all Vendas_retorno_YYYY.xlsx files from data/outros/.
Applies de_para_financeira mapping to 'financeira' column (R3).
Returns DataFrame with [placa, id_data, valor_financiado, tipo_retorno, financeira].
Saves to silver/retorno.parquet.
"""
import glob
import pandas as pd
from etl.config import OUTROS_PATH, RAW_PATH
from etl.utils import normalizar_colunas, normalizar_texto, salvar_silver

_RENAME = {
    "dt._venda":    "data_venda",
    "placa/chassi": "placa",
    "financiado":   "valor_financiado",
    "tp._ret.":     "tipo_retorno",
}

_COLS_OUT = ["placa", "id_data", "valor_financiado", "tipo_retorno", "financeira"]


def extract_retorno() -> pd.DataFrame:
    files = sorted(glob.glob(str(OUTROS_PATH / "Vendas_retorno_*.xlsx")))

    if not files:
        empty = pd.DataFrame(columns=_COLS_OUT)
        salvar_silver(empty, "retorno")
        return empty

    dfs = [normalizar_colunas(pd.read_excel(f)) for f in files]
    ret = pd.concat(dfs, ignore_index=True).rename(columns=_RENAME)

    # Aplicar de/para financeira (R3 — antes de qualquer join)
    de_para = normalizar_colunas(pd.read_excel(RAW_PATH / "de_para_financeira.xlsx"))
    de_para["financeira_origem"] = normalizar_texto(de_para["financeira_origem"])
    de_para["financeira_padrao"] = normalizar_texto(de_para["financeira_padrao"])
    ret["financeira"] = normalizar_texto(ret["financeira"])
    ret = ret.merge(de_para, left_on="financeira", right_on="financeira_origem", how="left")
    ret["financeira"] = ret["financeira_padrao"].fillna(ret["financeira"])
    ret = ret.drop(columns=["financeira_origem", "financeira_padrao"], errors="ignore")

    ret["placa"] = normalizar_texto(ret["placa"])
    ret["data_venda"] = pd.to_datetime(ret["data_venda"], errors="coerce")
    ret["id_data"] = pd.to_numeric(ret["data_venda"].dt.strftime("%Y%m%d"), errors="coerce")

    ret["valor_financiado"] = pd.to_numeric(ret["valor_financiado"], errors="coerce")
    ret["tipo_retorno"] = pd.to_numeric(ret["tipo_retorno"], errors="coerce").astype("Int64")
    ret = ret.dropna(subset=["placa", "id_data"])
    ret = ret.drop_duplicates(subset=["placa", "id_data"])

    present = [c for c in _COLS_OUT if c in ret.columns]
    salvar_silver(ret[present], "retorno")
    return ret[present]
