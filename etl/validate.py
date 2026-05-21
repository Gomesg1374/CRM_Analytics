"""
Post-load quality report. Checks acceptance criteria from PRD F1.4
and verifies gold Parquet row counts match in-memory DataFrames.
"""
import pandas as pd
from etl.config import GOLD_PATH


def _check(label: str, passed: bool, detail: str = "") -> bool:
    mark   = "✅ PASS" if passed else "❌ FAIL"
    suffix = f"  ({detail})" if detail else ""
    print(f"  {mark}  {label}{suffix}")
    return passed


def validate(gold_tables: dict, n_vendas_raw: int | None = None) -> int:
    """
    Runs all quality checks against the in-memory gold tables.
    Prints a report and returns the number of failed checks.

    gold_tables: {table_name: DataFrame}
    n_vendas_raw: row count of vendas before the comissão join, used to verify R6.
    """
    failures = 0

    # ----------------------------------------------------------------
    # F1.4 acceptance criteria
    # ----------------------------------------------------------------
    print("\n📋 CRITÉRIOS DE ACEITE (F1.4):")

    fv  = gold_tables.get("fato_vendas")
    dv  = gold_tables.get("dim_veiculos")
    dd  = gold_tables.get("dim_data")

    # Marca: < 5% "desconhecida" excluding returned vehicles
    if dv is not None:
        nao_devolvido   = dv[dv["situacao"] != "devolvido"]
        pct_desc        = nao_devolvido["marca"].eq("desconhecida").mean()
        failures       += 0 if _check(
            "Marca: desconhecida < 5% (excl. Devolvido)",
            pct_desc < 0.05,
            f"{pct_desc:.1%} desconhecida em {len(nao_devolvido):,} veículos ativos",
        ) else 1

    # Comissão: >= 90% coverage in fato_vendas
    if fv is not None and "comissao" in fv.columns:
        cob      = fv["comissao"].notna().mean()
        failures += 0 if _check(
            "Comissão: cobertura >= 90% em fato_vendas",
            cob >= 0.90,
            f"{cob:.1%}  ({fv['comissao'].notna().sum():,}/{len(fv):,} linhas)",
        ) else 1

    # dim_data: range 2022-01-01 → 2027-12-31
    if dd is not None:
        d_min = dd["data"].min().date()
        d_max = dd["data"].max().date()
        failures += 0 if _check(
            "dim_data: cobre 2022-01-01 a 2027-12-31",
            str(d_min) == "2022-01-01" and str(d_max) == "2027-12-31",
            f"{d_min} → {d_max}",
        ) else 1

        nulls    = dd[["trimestre", "semestre", "dia_semana", "dias_uteis_mes"]].isnull().sum().sum()
        failures += 0 if _check(
            "dim_data: sem NULLs em trimestre / semestre / dia_semana / dias_uteis_mes",
            nulls == 0,
            f"{nulls} NULLs",
        ) else 1

    # R6: fato_vendas never loses rows from the comissão left join
    if fv is not None and n_vendas_raw is not None:
        failures += 0 if _check(
            "fato_vendas: join com comissão não descartou linhas (R6)",
            len(fv) == n_vendas_raw,
            f"{len(fv):,} linhas  (esperado {n_vendas_raw:,})",
        ) else 1

    # ----------------------------------------------------------------
    # Match rates
    # ----------------------------------------------------------------
    print("\n🔍 MATCH RATES:")
    for nome, label in [
        ("fato_leads",        "Leads"),
        ("fato_vendas",       "Vendas"),
        ("fato_agendamentos", "Agendamentos"),
    ]:
        df = gold_tables.get(nome)
        if df is None:
            continue
        pv = df["id_vendedor"].eq(-1).mean() if "id_vendedor" in df.columns else float("nan")
        pl = df["id_loja"].eq(-1).mean()     if "id_loja"     in df.columns else float("nan")
        print(f"  {label:<14} vendedor sem match {pv:.1%}  |  loja sem match {pl:.1%}")

    # ----------------------------------------------------------------
    # Row counts
    # ----------------------------------------------------------------
    print("\n📊 CONTAGENS:")
    for nome, df in gold_tables.items():
        print(f"  {nome:<28} {len(df):,}")

    # ----------------------------------------------------------------
    # Parquet verification
    # ----------------------------------------------------------------
    print("\n📂 VERIFICAÇÃO PÓS-SAVE (parquet vs memória):")
    all_parquet_ok = True
    for nome, df in gold_tables.items():
        path = GOLD_PATH / f"{nome}.parquet"
        if not path.exists():
            print(f"  ⚠️  {nome}.parquet não encontrado")
            all_parquet_ok = False
            continue
        saved_len = len(pd.read_parquet(path))
        ok        = saved_len == len(df)
        all_parquet_ok = all_parquet_ok and ok
        print(f"  {'✅' if ok else '❌'}  {nome:<28} memória={len(df):,}  parquet={saved_len:,}")

    if not all_parquet_ok:
        failures += 1

    # ----------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------
    total_checks = 5 + (1 if not all_parquet_ok else 0)
    passed       = total_checks - failures
    print(f"\n{'✅' if failures == 0 else '⚠️ '} Resultado: {passed}/{total_checks} critérios aprovados")
    return failures
