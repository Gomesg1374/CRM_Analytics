"""
Entry point for the CRM Analytics ETL pipeline.

Usage:
    python etl/run.py           # extract → silver → transform → gold → validate
    python etl/run.py --no-db   # skip PostgreSQL load step

Produces the same 12 Parquet files in data/gold/ as the legacy etl/transform.py.
"""
import argparse
import sys
import time
import traceback

import pandas as pd

from etl.config import GOLD_PATH

# Extract
from etl.extract.dimensoes_base import extract_dimensoes_base
from etl.extract.leads          import extract_leads
from etl.extract.vendas         import extract_vendas
from etl.extract.canais         import extract_canais
from etl.extract.agendamentos   import extract_agendamentos
from etl.extract.veiculos       import extract_veiculos
from etl.extract.comissoes      import extract_comissoes

# Transform
from etl.transform.dim_canal      import build_dim_canal
from etl.transform.dim_data       import build_dim_data
from etl.transform.dim_vendedores import build_dim_vendedores, build_dim_vendedor_periodo
from etl.transform.dim_lojas      import build_dim_lojas
from etl.transform.dim_veiculos   import build_dim_veiculos
from etl.transform.fato_leads     import build_dim_estagio, build_fato_leads
from etl.transform.fato_vendas    import build_fato_vendas
from etl.transform.fato_agendamentos import build_fato_agendamentos
from etl.transform.fato_metas    import build_fato_metas

from etl.validate import validate


def _build_success_summary(gold_tables: dict, n_vendas_raw: int,
                           failures: int, pg_result: str, duration_s: float) -> str:
    lines = [f"Duração: {duration_s:.0f}s", ""]

    lines.append("TABELAS (gold/)")
    total = 0
    for nome, df in gold_tables.items():
        lines.append(f"  {nome:<28} {len(df):,} linhas")
        total += len(df)
    lines.append(f"  {'─' * 44}")
    lines.append(f"  {'TOTAL':<28} {total:,} linhas em {len(gold_tables)} tabelas")

    lines += ["", "CRITÉRIOS DE ACEITE"]
    fv = gold_tables.get("fato_vendas")
    dv = gold_tables.get("dim_veiculos")
    dd = gold_tables.get("dim_data")

    if dv is not None:
        nao_dev = dv[dv["situacao"] != "devolvido"]
        pct = nao_dev["marca"].eq("desconhecida").mean()
        lines.append(f"  {'OK' if pct < 0.05 else 'FAIL'}  Marca desconhecida: {pct:.1%} em {len(nao_dev):,} veículos ativos (< 5%)")
    if fv is not None and "comissao" in fv.columns:
        cob = fv["comissao"].notna().mean()
        lines.append(f"  {'OK' if cob >= 0.90 else 'FAIL'}  Comissão: cobertura {cob:.1%} em {fv['comissao'].notna().sum():,}/{len(fv):,} linhas (>= 90%)")
    if dd is not None:
        d_min, d_max = dd["data"].min().date(), dd["data"].max().date()
        ok = str(d_min) == "2022-01-01" and str(d_max) == "2027-12-31"
        lines.append(f"  {'OK' if ok else 'FAIL'}  dim_data: {d_min} → {d_max}")
        nulls = dd[["trimestre", "semestre", "dia_semana", "dias_uteis_mes"]].isnull().sum().sum()
        lines.append(f"  {'OK' if nulls == 0 else 'FAIL'}  dim_data: {nulls} NULLs em colunas de calendário")
    if fv is not None:
        ok = len(fv) == n_vendas_raw
        lines.append(f"  {'OK' if ok else 'FAIL'}  fato_vendas: {len(fv):,} linhas — {'sem perda no join com comissao' if ok else f'esperado {n_vendas_raw:,}'}")

    passed = 5 - failures
    lines.append(f"  Resultado: {passed}/5 aprovados")

    lines += ["", "MATCH RATES"]
    for nome, label in [("fato_leads", "Leads"), ("fato_vendas", "Vendas"), ("fato_agendamentos", "Agendamentos")]:
        df = gold_tables.get(nome)
        if df is None:
            continue
        pv = df["id_vendedor"].eq(-1).mean() if "id_vendedor" in df.columns else float("nan")
        pl = df["id_loja"].eq(-1).mean()     if "id_loja"     in df.columns else float("nan")
        lines.append(f"  {label:<14} vendedor {pv:.1%} | loja {pl:.1%}")

    lines += ["", "POSTGRESQL", f"  {pg_result}"]

    return "\n".join(lines)


def _save_gold(tables: dict) -> None:
    for nome, df in tables.items():
        for col in ["id_vendedor", "id_loja", "id_canal"]:
            if col in df.columns:
                df[col] = df[col].fillna(-1).astype(int)
        df.to_parquet(GOLD_PATH / f"{nome}.parquet", index=False)
        print(f"  💾 {nome:<28} {len(df):,} linhas")


def main(load_db: bool = True) -> tuple[int, str]:
    t0 = time.time()
    # ------------------------------------------------------------------
    # 1. Extract  (writes silver/)
    # ------------------------------------------------------------------
    print("\n📥 EXTRACT")
    base        = extract_dimensoes_base()
    leads_raw   = extract_leads()
    vendas_raw  = extract_vendas()
    canais_raw  = extract_canais()
    ag_raw      = extract_agendamentos()
    veic_raw    = extract_veiculos()
    com_raw     = extract_comissoes()

    hist        = base["hist_vendedor_loja"]
    de_para_vend = base["de_para_vend"]

    # ------------------------------------------------------------------
    # 2. Build dimensions
    # ------------------------------------------------------------------
    print("\n🏗  DIMENSÕES")
    dim_canal            = build_dim_canal(leads_raw, canais_raw)
    dim_data             = build_dim_data()
    dim_vendedores       = build_dim_vendedores(base["usuarios"])
    dim_lojas            = build_dim_lojas(hist)
    dim_veiculos         = build_dim_veiculos(veic_raw)
    dim_estagio          = build_dim_estagio(leads_raw)
    dim_vendedor_periodo = build_dim_vendedor_periodo(hist)

    # ------------------------------------------------------------------
    # 3. Build facts  (agendamentos first — needed for SDR propagation)
    # ------------------------------------------------------------------
    print("\n⚙️  FATOS")
    fato_agendamentos  = build_fato_agendamentos(ag_raw, dim_canal, dim_vendedores, hist, de_para_vend)
    fato_leads         = build_fato_leads(leads_raw, dim_canal, dim_vendedores, hist, de_para_vend, dim_estagio, fato_agendamentos)
    fato_vendas        = build_fato_vendas(vendas_raw, canais_raw, dim_canal, dim_vendedores, hist, de_para_vend, dim_veiculos, com_raw)
    fato_meta_vendedor, fato_meta_loja = build_fato_metas(base["meta_vendedor"], base["meta_loja"], dim_vendedor_periodo)

    # ------------------------------------------------------------------
    # 4. Save gold Parquets
    # ------------------------------------------------------------------
    print("\n💾 GOLD")
    gold_tables = {
        "dim_canal":            dim_canal,
        "dim_data":             dim_data,
        "dim_vendedores":       dim_vendedores,
        "dim_lojas":            dim_lojas,
        "dim_veiculos":         dim_veiculos,
        "dim_estagio":          dim_estagio,
        "dim_vendedor_periodo": dim_vendedor_periodo,
        "fato_leads":           fato_leads,
        "fato_vendas":          fato_vendas,
        "fato_agendamentos":    fato_agendamentos,
        "fato_meta_vendedor":   fato_meta_vendedor,
        "fato_meta_loja":       fato_meta_loja,
    }
    _save_gold(gold_tables)

    # ------------------------------------------------------------------
    # 5. Validate
    # ------------------------------------------------------------------
    failures = validate(gold_tables, n_vendas_raw=len(vendas_raw))

    # ------------------------------------------------------------------
    # 6. Load to PostgreSQL (optional)
    # ------------------------------------------------------------------
    pg_result = "pulado (--no-db)"
    if load_db:
        try:
            from etl.load import load
            print("\n🗄  CARREGANDO NO POSTGRESQL")
            load()
            total = sum(len(df) for df in gold_tables.values())
            pg_result = f"OK — {total:,} linhas em {len(gold_tables)} tabelas, todos os counts batem"
        except Exception as exc:
            print(f"  ⚠️  Carga no PostgreSQL falhou: {exc}")
            print("      Execute 'python etl/load.py' após verificar a conexão.")
            pg_result = f"FALHOU — {exc}"

    summary = _build_success_summary(
        gold_tables, len(vendas_raw), failures, pg_result, time.time() - t0
    )
    return failures, summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CRM Analytics ETL pipeline")
    parser.add_argument("--no-db", action="store_true", help="Pula a carga no PostgreSQL")
    args = parser.parse_args()

    from etl.notify import send_failure_email, send_success_email

    failures, summary = 0, ""
    try:
        failures, summary = main(load_db=not args.no_db)
    except Exception:
        tb = traceback.format_exc()
        print(f"\n❌ Erro inesperado:\n{tb}")
        send_failure_email("Erro inesperado no ETL", tb)
        sys.exit(1)

    if failures > 0:
        send_failure_email(
            f"ETL concluído com {failures} critério(s) não aprovado(s)",
            f"{failures} critério(s) de qualidade falharam.\nVerifique os logs em logs/ para detalhes.\n\n{summary}",
        )
    else:
        send_success_email(summary)

    sys.exit(0 if failures == 0 else 1)
