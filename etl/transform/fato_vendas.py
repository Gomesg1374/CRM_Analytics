import pandas as pd
from etl.utils import adicionar_vendedor_loja, normalizar_texto

_OUTPUT_COLS = [
    "id_venda", "id_veiculo", "id_vendedor", "id_loja",
    "id_canal", "id_data", "ano_mes",
    "placa", "modelo", "cliente",
    "valor_venda", "valor_compra", "custos",
    "situacao", "data_compra", "desconto",
    "comissao", "impostos", "lucro", "retorno",
    "valor_financiado", "tipo_retorno", "financeira",
]


def build_fato_vendas(
    vendas_raw:    pd.DataFrame,
    canais_raw:    pd.DataFrame,
    dim_canal:     pd.DataFrame,
    dim_vendedores: pd.DataFrame,
    hist:          pd.DataFrame,
    de_para_vend:  pd.DataFrame,
    dim_veiculos:  pd.DataFrame,
    comissoes:     pd.DataFrame,
    retorno_fin:   pd.DataFrame,
) -> pd.DataFrame:
    fv = vendas_raw.copy()

    # Enrich canal: canal is determined by the vehicle code (id_venda = Código)
    fv = fv.merge(
        canais_raw[["codigo", "canal"]],
        left_on="id_venda", right_on="codigo",
        how="left",
    ).drop(columns=["codigo"], errors="ignore")
    fv["canal"] = normalizar_texto(fv["canal"].fillna(""))

    fv = fv.merge(dim_canal, on="canal", how="left")

    fv = adicionar_vendedor_loja(
        fv, "nome_vendedor", "data_venda",
        dim_vendedores, hist, de_para_vend,
    )

    # id_veiculo: vehicle code from dim_veiculos (R4)
    fv = fv.merge(
        dim_veiculos[["id_veiculo"]],
        left_on="id_venda", right_on="id_veiculo",
        how="left",
    )

    # F1.2: enrich with financial data (R6: left join — fato_vendas never loses rows)
    fv = fv.merge(comissoes, on="id_venda", how="left")

    # Enrich with retorno financeiro — join on placa (normalized) + id_data (left join, R6)
    fv["_placa_norm"] = normalizar_texto(fv["placa"].fillna(""))
    fv = fv.merge(
        retorno_fin,
        left_on=["_placa_norm", "id_data"],
        right_on=["placa", "id_data"],
        how="left",
        suffixes=("", "_ret"),
    )
    fv = fv.drop(columns=["_placa_norm", "placa_ret"], errors="ignore")

    present = [c for c in _OUTPUT_COLS if c in fv.columns]
    return fv[present].copy()
