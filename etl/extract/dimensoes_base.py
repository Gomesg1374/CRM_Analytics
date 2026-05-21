"""
Reads auxiliary dimension tables and de/para mappings.
Returns a dict with: usuarios, hist_vendedor_loja, meta_vendedor, meta_loja,
                     de_para_canais, de_para_vend
"""
import pandas as pd
from etl.config import RAW_PATH
from etl.utils import normalizar_colunas, normalizar_texto, salvar_silver


def extract_dimensoes_base() -> dict:
    usuarios = normalizar_colunas(pd.read_excel(RAW_PATH / "usuarios.xlsx"))
    usuarios = usuarios.rename(columns={"id_usuario": "id_vendedor", "nome_usuario": "nome"})
    usuarios["nome"] = normalizar_texto(usuarios["nome"])
    salvar_silver(usuarios, "usuarios")

    hist = normalizar_colunas(pd.read_excel(RAW_PATH / "hist_vendedor_loja.xlsx"))
    hist["data_inicio"] = pd.to_datetime(hist["data_inicio"])
    hist["data_fim"]    = pd.to_datetime(hist["data_fim"])
    salvar_silver(hist, "hist_vendedor_loja")

    meta_vend = normalizar_colunas(pd.read_excel(RAW_PATH / "meta_vendedor.xlsx"))
    meta_vend["ano_mes"] = meta_vend["ano_mes"].astype(int)
    salvar_silver(meta_vend, "meta_vendedor")

    meta_loja = normalizar_colunas(pd.read_excel(RAW_PATH / "meta_loja.xlsx"))
    meta_loja["ano_mes"] = meta_loja["ano_mes"].astype(int)
    salvar_silver(meta_loja, "meta_loja")

    de_para_canais = normalizar_colunas(pd.read_excel(RAW_PATH / "de_para_canais.xlsx"))
    de_para_canais["canal_origem"] = normalizar_texto(de_para_canais["canal_origem"])
    de_para_canais["canal_padrao"] = normalizar_texto(de_para_canais["canal_padrao"])

    de_para_vend = normalizar_colunas(pd.read_excel(RAW_PATH / "de_para_vendedores.xlsx"))
    de_para_vend["nome_origem"] = normalizar_texto(de_para_vend["nome_origem"])
    de_para_vend["nome_padrao"] = normalizar_texto(de_para_vend["nome_padrao"])

    return {
        "usuarios":           usuarios,
        "hist_vendedor_loja": hist,
        "meta_vendedor":      meta_vend,
        "meta_loja":          meta_loja,
        "de_para_canais":     de_para_canais,
        "de_para_vend":       de_para_vend,
    }
