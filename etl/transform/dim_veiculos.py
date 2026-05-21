import pandas as pd
from etl.utils import normalizar_texto

_TEXT_COLS = ["marca", "modelo", "cor", "tipo", "situacao"]


def build_dim_veiculos(veiculos_enriched: pd.DataFrame) -> pd.DataFrame:
    """Finalizes dim_veiculos: selects schema columns and normalizes text fields."""
    cols = ["id_veiculo", "marca", "modelo", "ano", "cor", "tipo", "placa", "situacao"]
    dim = veiculos_enriched[cols].copy()
    for col in _TEXT_COLS:
        dim[col] = normalizar_texto(dim[col])
    return dim
