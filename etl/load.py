import os
import pandas as pd
from sqlalchemy import create_engine, text, inspect

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB   = os.getenv("PG_DB",   "crm_analytics")
PG_USER = os.getenv("PG_USER", "crm")
PG_PASS = os.getenv("PG_PASS", "crm123")
SCHEMA    = "gold"
GOLD_PATH = "data/gold/"

# Dimensions first so FK lookups work during manual queries
TABLE_ORDER = [
    "dim_canal",
    "dim_data",
    "dim_vendedores",
    "dim_lojas",
    "dim_veiculos",
    "dim_estagio",
    "dim_vendedor_periodo",
    "fato_leads",
    "fato_vendas",
    "fato_agendamentos",
    "fato_meta_vendedor",
    "fato_meta_loja",
]


def _engine():
    url = f"postgresql+psycopg2://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    return create_engine(url, future=True)


def _carregar_tabela(engine, table, df):
    insp = inspect(engine)
    exists = insp.has_table(table, schema=SCHEMA)

    if exists:
        with engine.begin() as conn:
            conn.execute(text(f'TRUNCATE TABLE {SCHEMA}."{table}"'))
        df.to_sql(table, engine, schema=SCHEMA, if_exists="append", index=False)
    else:
        df.to_sql(table, engine, schema=SCHEMA, if_exists="replace", index=False)


def load():
    engine = _engine()

    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))

    print(f"Conectado: {PG_DB} — schema: {SCHEMA}\n")

    total_rows = 0
    for table in TABLE_ORDER:
        path = f"{GOLD_PATH}{table}.parquet"
        if not os.path.exists(path):
            print(f"  ⚠️  {table}.parquet não encontrado — pulando")
            continue

        df = pd.read_parquet(path)
        _carregar_tabela(engine, table, df)
        total_rows += len(df)
        print(f"  ✅ {table:<25} {len(df):,} linhas")

    print(f"\n  Total: {total_rows:,} linhas em {len(TABLE_ORDER)} tabelas")

    # Verify row counts in DB match parquets
    print("\n📂 VERIFICAÇÃO PÓS-CARGA:")
    all_ok = True
    with engine.connect() as conn:
        for table in TABLE_ORDER:
            path = f"{GOLD_PATH}{table}.parquet"
            if not os.path.exists(path):
                continue
            expected = len(pd.read_parquet(path))
            result = conn.execute(text(f'SELECT COUNT(*) FROM {SCHEMA}."{table}"'))
            actual = result.scalar()
            ok = actual == expected
            all_ok = all_ok and ok
            mark = "✅" if ok else "❌"
            print(f"  {mark} {table:<25} parquet={expected:,}  postgres={actual:,}")

    print()
    if all_ok:
        print("✅ Carga no PostgreSQL concluída — todos os counts batem")
    else:
        print("⚠️  Divergência de counts — verificar logs acima")


if __name__ == "__main__":
    load()
