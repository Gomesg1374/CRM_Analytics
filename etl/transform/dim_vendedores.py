import pandas as pd


def build_dim_vendedores(usuarios: pd.DataFrame) -> pd.DataFrame:
    """Builds dim_vendedores from usuarios, adding the sentinel row id = -1."""
    dim = pd.concat([
        usuarios,
        pd.DataFrame([{"id_vendedor": -1, "nome": "desconhecido"}]),
    ], ignore_index=True)
    return dim


def build_dim_vendedor_periodo(hist: pd.DataFrame) -> pd.DataFrame:
    """
    Expands hist_vendedor_loja into one row per (vendedor, ano_mes).
    Audit table only — do not use as a bridge table in Metabase (R5).
    """
    hist = hist.copy()
    hist["data_fim"] = hist["data_fim"].fillna(pd.Timestamp("2099-12-31"))
    hist["mes_inicio"] = hist["data_inicio"].dt.to_period("M")
    hist["mes_fim"]    = hist["data_fim"].dt.to_period("M")
    hist["n_meses"]    = (hist["mes_fim"] - hist["mes_inicio"]).apply(lambda x: x.n) + 1

    exp = hist.loc[hist.index.repeat(hist["n_meses"])].copy()
    exp["mes_seq"] = exp.groupby(level=0).cumcount()
    exp["ano_mes"] = (
        exp["mes_inicio"] + exp["mes_seq"]
    ).astype(str).str.replace("-", "").astype(int)

    return (
        exp[["id_vendedor", "id_loja", "ano_mes"]]
        .drop_duplicates(subset=["id_vendedor", "ano_mes"])
        .reset_index(drop=True)
    )
