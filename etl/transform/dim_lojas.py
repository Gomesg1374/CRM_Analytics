import pandas as pd


def build_dim_lojas(hist: pd.DataFrame) -> pd.DataFrame:
    """Builds dim_lojas from hist_vendedor_loja, adding the sentinel row id = -1."""
    dim = pd.concat([
        hist[["id_loja", "loja"]].drop_duplicates(),
        pd.DataFrame([{"id_loja": -1, "loja": "desconhecida"}]),
    ], ignore_index=True)
    return dim
