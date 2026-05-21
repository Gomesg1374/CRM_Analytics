"""
Entry point for the CRM Analytics ETL pipeline.

Usage:
    python etl/run.py           # extract → silver → transform → gold → validate
    python etl/run.py --no-db   # skip PostgreSQL load step

Produces the same 12 Parquet files in data/gold/ as the legacy etl/transform.py.
"""
import argparse
import sys
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


def _save_gold(tables: dict) -> None:
    for nome, df in tables.items():
        for col in ["id_vendedor", "id_loja", "id_canal"]:
            if col in df.columns:
                df[col] = df[col].fillna(-1).astype(int)
        df.to_parquet(GOLD_PATH / f"{nome}.parquet", index=False)
        print(f"  💾 {nome:<28} {len(df):,} linhas")


def main(load_db: bool = True) -> int:
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
    if load_db:
        try:
            from etl.load import load
            print("\n🗄  CARREGANDO NO POSTGRESQL")
            load()
        except Exception as exc:
            print(f"  ⚠️  Carga no PostgreSQL falhou: {exc}")
            print("      Execute 'python etl/load.py' após verificar a conexão.")

    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CRM Analytics ETL pipeline")
    parser.add_argument("--no-db", action="store_true", help="Pula a carga no PostgreSQL")
    args = parser.parse_args()

    from etl.notify import send_failure_email

    failures = 0
    try:
        failures = main(load_db=not args.no_db)
    except Exception:
        tb = traceback.format_exc()
        print(f"\n❌ Erro inesperado:\n{tb}")
        send_failure_email("Erro inesperado no ETL", tb)
        sys.exit(1)

    if failures > 0:
        send_failure_email(
            f"ETL concluído com {failures} critério(s) não aprovado(s)",
            f"{failures} critério(s) de qualidade falharam.\n"
            "Verifique os logs em logs/ para detalhes.",
        )

    sys.exit(0 if failures == 0 else 1)
