import unicodedata
import pandas as pd
from etl.config import SILVER_PATH


def normalizar_texto(col: pd.Series) -> pd.Series:
    return (
        col.fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .apply(lambda x: unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode("utf-8"))
        .str.replace(r"[^a-z0-9 ]", "", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_", regex=False)
    df.columns = [
        unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode("utf-8")
        for c in df.columns
    ]
    return df


def salvar_silver(df: pd.DataFrame, nome: str) -> None:
    df = df.copy()
    # Coerce object columns with mixed scalar types to str to prevent pyarrow ArrowTypeError
    for col in df.select_dtypes(include="object").columns:
        if df[col].map(type).nunique() > 1:
            df[col] = df[col].astype(str)
    df.to_parquet(SILVER_PATH / f"{nome}.parquet", index=False)


def _validate_schema(df: pd.DataFrame, required: set, source: str) -> None:
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{source}: colunas obrigatórias ausentes: {sorted(missing)}")


def adicionar_vendedor_loja(df, col_nome, col_data, dim_vendedores, hist_vendedor_loja, de_para_vend):
    """
    Resolve id_vendedor e id_loja para cada linha usando o histórico de lotação.
    Garante que nenhuma linha seja descartada: vendedores/lojas sem match recebem id = -1 (R1, R2).
    """
    df = df.copy()
    df[col_nome] = normalizar_texto(df[col_nome])

    # De/Para de vendedores (R3)
    df = df.merge(de_para_vend, left_on=col_nome, right_on="nome_origem", how="left")
    df[col_nome] = df["nome_padrao"].fillna(df[col_nome])
    df = df.drop(columns=["nome_origem", "nome_padrao"])

    # Resolve id_vendedor pelo nome padronizado
    df = df.merge(
        dim_vendedores[["id_vendedor", "nome"]],
        left_on=col_nome,
        right_on="nome",
        how="left",
    ).drop(columns=["nome"])

    df["id_vendedor"] = df["id_vendedor"].fillna(-1).astype(int)

    df[col_data] = pd.to_datetime(df[col_data])
    hist = hist_vendedor_loja.copy()
    hist["data_inicio"] = pd.to_datetime(hist["data_inicio"])
    hist["data_fim"]    = pd.to_datetime(hist["data_fim"]).fillna(pd.Timestamp("2099-12-31"))

    df_idx = df.reset_index(drop=False).rename(columns={"index": "_orig_idx"})

    merged = df_idx.merge(
        hist[["id_vendedor", "id_loja", "data_inicio", "data_fim"]],
        on="id_vendedor",
        how="left",
        indicator=True,
    )

    no_match  = merged["_merge"] == "left_only"
    in_period = (merged[col_data] >= merged["data_inicio"]) & (merged[col_data] <= merged["data_fim"])
    matched = merged[in_period | no_match].copy()

    matched = (
        matched
        .sort_values("data_inicio", ascending=False)
        .drop_duplicates(subset=["_orig_idx"])
    )

    matched["id_loja"] = matched["id_loja"].fillna(-1).astype(int)

    df_final = df_idx.merge(
        matched[["_orig_idx", "id_loja"]],
        on="_orig_idx",
        how="left",
    ).drop(columns=["_orig_idx", "_merge"], errors="ignore")

    df_final["id_loja"] = df_final["id_loja"].fillna(-1).astype(int)

    return df_final
