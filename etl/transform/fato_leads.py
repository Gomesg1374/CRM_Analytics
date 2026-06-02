import pandas as pd
from etl.utils import adicionar_vendedor_loja

_OUTPUT_COLS = [
    "id", "id_vendedor", "id_loja", "id_canal",
    "id_estagio", "id_data", "id_data_ultima_integracao",
    "convertido_flag", "perdido_flag", "motivo", "link_post",
]


def build_dim_estagio(leads_raw: pd.DataFrame) -> pd.DataFrame:
    dim = leads_raw[["estagio"]].drop_duplicates().reset_index(drop=True)
    dim["id_estagio"] = dim.index + 1
    return dim


def build_fato_leads(
    leads_raw:        pd.DataFrame,
    dim_canal:        pd.DataFrame,
    dim_vendedores:    pd.DataFrame,
    hist:             pd.DataFrame,
    de_para_vend:     pd.DataFrame,
    dim_estagio:      pd.DataFrame,
    fato_agendamentos: pd.DataFrame | None = None,
    leads_link:        pd.DataFrame | None = None,
) -> pd.DataFrame:
    fl = adicionar_vendedor_loja(
        leads_raw, "atendente", "data_criacao",
        dim_vendedores, hist, de_para_vend,
    )

    fl = fl.merge(dim_canal, on="canal", how="left")
    fl = fl.merge(dim_estagio, on="estagio", how="left")

    present = [c for c in _OUTPUT_COLS if c in fl.columns]
    fl = fl[present].copy()

    # Propagate SDR (responsável pelo agendamento) back onto each lead
    if fato_agendamentos is not None:
        sdr = (
            fato_agendamentos[["id", "id_vendedor"]]
            .rename(columns={"id_vendedor": "id_sdr"})
            .drop_duplicates(subset=["id"])
        )
        fl = fl.merge(sdr, on="id", how="left")
        # NULL = sem agendamento (semanticamente correto, não usa -1)
        fl["id_sdr"] = fl["id_sdr"].astype("Int64")

    if leads_link is not None:
        fl = fl.merge(leads_link[["id", "link_post"]], on="id", how="left")

    return fl
