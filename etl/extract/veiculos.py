"""
Reads gerencial_estoque.xlsx as the base and enriches with Marca (R7):
  1. gerencial_estoque_marca.xlsx — current stock (primary source)
  2. Vendas_Marca_YYYY.xlsx concat — historical fallback (most recent sale)
  3. "desconhecida" for any remaining without brand

Saves to silver/veiculos.parquet.
"""
import glob
import pandas as pd
from etl.config import RAW_PATH, OUTROS_PATH
from etl.utils import normalizar_colunas, salvar_silver, _validate_schema

REQUIRED = {"codigo", "modelo", "ano", "cor", "tipo", "placa", "situacao"}


def extract_veiculos() -> pd.DataFrame:
    base = normalizar_colunas(pd.read_excel(RAW_PATH / "gerencial_estoque.xlsx"))
    _validate_schema(base, REQUIRED, "gerencial_estoque.xlsx")

    dim = base[["codigo", "modelo", "ano", "cor", "tipo", "placa", "situacao"]].drop_duplicates().copy()
    dim["id_veiculo"] = dim["codigo"]
    dim["marca"]      = None

    # Step 1: gerencial_estoque_marca.xlsx (current stock — highest priority)
    marca_path = OUTROS_PATH / "gerencial_estoque_marca.xlsx"
    if marca_path.exists():
        em = normalizar_colunas(pd.read_excel(marca_path))
        em = em[["codigo", "marca"]].dropna(subset=["codigo", "marca"]).drop_duplicates(subset=["codigo"])
        em["codigo"] = pd.to_numeric(em["codigo"], errors="coerce").astype("Int64")
        dim = dim.merge(em.rename(columns={"marca": "_marca_est"}), on="codigo", how="left")
        dim["marca"] = dim["_marca_est"]
        dim = dim.drop(columns=["_marca_est"])

    # Step 2: Vendas_Marca_YYYY.xlsx — most-recent sale per Código for remaining
    vm_files = sorted(glob.glob(str(OUTROS_PATH / "Vendas_Marca_*.xlsx")))
    if vm_files:
        vm = pd.concat([normalizar_colunas(pd.read_excel(f)) for f in vm_files], ignore_index=True)
        date_col = next((c for c in vm.columns if c.startswith("dt")), None)
        vm["_dt"] = pd.to_datetime(vm[date_col], errors="coerce") if date_col else pd.NaT
        vm["codigo"] = pd.to_numeric(vm["codigo"], errors="coerce").astype("Int64")
        vm = vm.dropna(subset=["codigo", "marca"])
        vm_latest = (
            vm.sort_values("_dt", ascending=False)
            .drop_duplicates(subset=["codigo"])[["codigo", "marca"]]
        )
        dim = dim.merge(vm_latest.rename(columns={"marca": "_marca_hist"}), on="codigo", how="left")
        dim["marca"] = dim["marca"].fillna(dim["_marca_hist"])
        dim = dim.drop(columns=["_marca_hist"])

    # Step 3: fallback
    dim["marca"] = dim["marca"].fillna("desconhecida")

    salvar_silver(dim, "veiculos")
    return dim
