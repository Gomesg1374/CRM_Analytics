import pandas as pd


def build_fato_metas(
    meta_vendedor:       pd.DataFrame,
    meta_loja:           pd.DataFrame,
    dim_vendedor_periodo: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    fmv = meta_vendedor.copy()
    fmv["data_meta"] = pd.to_datetime(fmv["ano_mes"].astype(str) + "01", format="%Y%m%d")
    fmv["id_data"]   = (fmv["ano_mes"].astype(str) + "01").astype(int)

    fmv = fmv.merge(
        dim_vendedor_periodo[["id_vendedor", "ano_mes", "id_loja"]],
        on=["id_vendedor", "ano_mes"],
        how="left",
    )
    fmv = fmv[["id_vendedor", "ano_mes", "data_meta", "id_data", "id_loja", "meta_qtd"]]

    fml = meta_loja.copy()
    fml["data_meta"] = pd.to_datetime(fml["ano_mes"].astype(str) + "01", format="%Y%m%d")
    fml["id_data"]   = (fml["ano_mes"].astype(str) + "01").astype(int)
    fml = fml[["id_loja", "ano_mes", "data_meta", "id_data", "meta_qtd"]]

    return fmv, fml
