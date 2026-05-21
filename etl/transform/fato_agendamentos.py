import pandas as pd
from etl.utils import adicionar_vendedor_loja

_OUTPUT_COLS = [
    "id", "id_vendedor", "id_loja", "id_canal",
    "id_data_agendamento", "id_data_visita",
    "flag_agendamento", "flag_visita", "campanha", "status", "motivo", "id_venda",
]


def build_fato_agendamentos(
    ag_raw:        pd.DataFrame,
    dim_canal:     pd.DataFrame,
    dim_vendedores: pd.DataFrame,
    hist:          pd.DataFrame,
    de_para_vend:  pd.DataFrame,
) -> pd.DataFrame:
    ag = ag_raw.copy()

    ag = ag.merge(dim_canal, on="canal", how="left")

    ag = adicionar_vendedor_loja(
        ag, "responsavel_agendamento", "criacao_agendamento",
        dim_vendedores, hist, de_para_vend,
    )

    present = [c for c in _OUTPUT_COLS if c in ag.columns]
    return ag[present].copy()
