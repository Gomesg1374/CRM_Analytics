import numpy as np
import pandas as pd
from datetime import date as _date

_MESES_PT = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
_DIAS_PT  = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def _dias_uteis_mes(ano: int, mes: int) -> int:
    inicio = _date(ano, mes, 1)
    fim    = _date(ano + 1, 1, 1) if mes == 12 else _date(ano, mes + 1, 1)
    return int(np.busday_count(inicio, fim))


def build_dim_data(start: str = "2022-01-01", end: str = "2027-12-31") -> pd.DataFrame:
    dim = pd.DataFrame({"data": pd.date_range(start=start, end=end)})

    dim["id_data"]        = dim["data"].dt.strftime("%Y%m%d").astype(int)
    dim["ano"]            = dim["data"].dt.year
    dim["mes"]            = dim["data"].dt.month
    dim["ano_mes"]        = dim["ano"] * 100 + dim["mes"]
    dim["nome_mes"]       = dim["mes"].apply(lambda m: _MESES_PT[m - 1])
    dim["ano_mes_desc"]   = dim["data"].dt.strftime("%Y-%m")
    dim["trimestre"]      = ((dim["mes"] - 1) // 3) + 1
    dim["semestre"]       = (dim["mes"] > 6).astype(int) + 1
    dim["num_dia_semana"] = dim["data"].dt.dayofweek
    dim["dia_semana"]     = dim["num_dia_semana"].apply(lambda d: _DIAS_PT[d])
    dim["fim_de_semana"]  = (dim["num_dia_semana"] >= 5).astype(int)

    uteis = (
        dim[["ano", "mes"]].drop_duplicates()
        .assign(dias_uteis_mes=lambda df: df.apply(
            lambda r: _dias_uteis_mes(int(r["ano"]), int(r["mes"])), axis=1
        ))
    )
    dim = dim.merge(uteis, on=["ano", "mes"], how="left")

    return dim
