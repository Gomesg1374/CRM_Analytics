"""
Reads all Vendas_YYYY.xlsx files, normalizes and validates schema,
computes id_data and ano_mes, saves to silver/vendas.parquet.
"""
import glob
import pandas as pd
from etl.config import RAW_PATH
from etl.utils import normalizar_colunas, salvar_silver, _validate_schema

REQUIRED = {"id_venda", "data_venda", "nome_vendedor", "valor_venda", "valor_compra"}

_RENAME = {
    "codigo":        "id_venda",
    "dt._venda":     "data_venda",
    "vendedor":      "nome_vendedor",
    "venda":         "valor_venda",
    "compra":        "valor_compra",
    "lancamentos":   "custos",
    "desconto_venda": "desconto",
}


def extract_vendas() -> pd.DataFrame:
    files = sorted(glob.glob(str(RAW_PATH / "Vendas_*.xlsx")))
    if not files:
        raise ValueError("Nenhum arquivo Vendas_*.xlsx encontrado em data/raw/")

    dfs = [normalizar_colunas(pd.read_excel(f)) for f in files]
    vendas = pd.concat(dfs, ignore_index=True)
    vendas = vendas.rename(columns=_RENAME)
    _validate_schema(vendas, REQUIRED, "Vendas_*.xlsx")

    vendas["data_venda"] = pd.to_datetime(vendas["data_venda"], errors="coerce")
    vendas["id_data"]    = pd.to_numeric(
        vendas["data_venda"].dt.strftime("%Y%m%d"), errors="coerce"
    )
    vendas["ano_mes"] = vendas["data_venda"].dt.year * 100 + vendas["data_venda"].dt.month

    salvar_silver(vendas, "vendas")
    return vendas
