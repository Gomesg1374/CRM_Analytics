"""
Reads controleagendamentos.xlsx, validates schema, applies de/para for canal (R3),
converts boolean flags, computes id_data columns, saves to silver/agendamentos.parquet.
"""
import numpy as np
import pandas as pd
from etl.config import RAW_PATH
from etl.utils import normalizar_colunas, normalizar_texto, salvar_silver, _validate_schema

REQUIRED = {
    "id", "responsavel_agendamento", "canal",
    "criacao_agendamento", "agendado_para",
    "flag_agendamento", "flag_visita",
}


def extract_agendamentos() -> pd.DataFrame:
    ag = normalizar_colunas(pd.read_excel(RAW_PATH / "controleagendamentos.xlsx"))
    _validate_schema(ag, REQUIRED, "controleagendamentos.xlsx")

    ag["criacao_agendamento"] = pd.to_datetime(ag["criacao_agendamento"], errors="coerce")
    ag["agendado_para"]       = pd.to_datetime(ag["agendado_para"],       errors="coerce")

    ag["id_data_agendamento"] = pd.to_numeric(
        ag["criacao_agendamento"].dt.strftime("%Y%m%d"), errors="coerce"
    )
    ag["id_data_visita"] = pd.to_numeric(
        ag["agendado_para"].dt.strftime("%Y%m%d"), errors="coerce"
    )

    ag["flag_agendamento"] = np.where(ag["flag_agendamento"].astype(str).str.lower() == "sim", 1, 0)
    ag["flag_visita"]      = np.where(ag["flag_visita"].astype(str).str.lower()       == "sim", 1, 0)

    # Apply de/para for canal before any join (R3)
    de_para = normalizar_colunas(pd.read_excel(RAW_PATH / "de_para_canais.xlsx"))
    de_para["canal_origem"] = normalizar_texto(de_para["canal_origem"])
    de_para["canal_padrao"] = normalizar_texto(de_para["canal_padrao"])

    ag["canal"] = normalizar_texto(ag["canal"])
    ag = ag.merge(de_para, left_on="canal", right_on="canal_origem", how="left")
    ag["canal"] = ag["canal_padrao"].fillna(ag["canal"])
    ag = ag.drop(columns=["canal_origem", "canal_padrao"], errors="ignore")

    salvar_silver(ag, "agendamentos")
    return ag
