import pandas as pd


def build_dim_canal(leads: pd.DataFrame, canais: pd.DataFrame) -> pd.DataFrame:
    """Builds dim_canal from unique canal values across leads and the canais dimension table."""
    vals = pd.concat([leads["canal"], canais["canal"]]).dropna().unique()
    dim = pd.DataFrame({"canal": vals}).reset_index(drop=True)
    dim["id_canal"] = dim.index + 1
    return dim
