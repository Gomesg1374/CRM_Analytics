# CLAUDE.md

**Analista:** Gildo Gomes Guarda

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

CRM Analytics ETL pipeline for a multi-store car dealership. Reads Excel exports from a CRM (Revenda+), transforms them into a star schema, writes Parquet files to `data/gold/`, and loads them into PostgreSQL for Metabase dashboards.

## Commands

```powershell
# Activate virtual environment (Windows)
.\.venv\Scripts\Activate.ps1

# Run the full ETL
python -m etl.run

# Run without PostgreSQL load
python -m etl.run --no-db

# Install dependencies
pip install -r requirements.txt
```

The scheduled task (`scheduler/run_etl.ps1`) runs daily at 10:00 via Windows Task Scheduler and starts Docker containers automatically if needed.

## Architecture

### Data layers

```
data/raw/        ← Excel source files (CRM exports + complementary data)
data/outros/     ← Supplementary files: gerencial_estoque_marca.xlsx, Vendas_Marca_YYYY.xlsx, Vendas_comissao_YYYY.xlsx
data/silver/     ← Intermediate Parquets per entity (10 files)
data/gold/       ← Final star-schema Parquets consumed by Metabase (12 files)
```

### ETL structure

- `etl/run.py` — orchestrates the full pipeline
- `etl/extract/<entity>.py` — reads one Excel source, validates schema, writes to silver
- `etl/transform/<table>.py` — pure transformation functions, no file I/O
- `etl/load.py` — truncate + insert into PostgreSQL schema `gold`
- `etl/validate.py` — post-load quality report (5 acceptance criteria)
- `etl/notify.py` — sends email notification on completion/failure
- `etl/config.py` — path constants (`RAW_PATH`, `OTHERS_PATH`, `SILVER_PATH`, `GOLD_PATH`, PG credentials)
- `etl/utils.py` — shared utilities including `normalizar_texto()`

### Star schema (gold layer)

**Dimensions:** `dim_canal`, `dim_data`, `dim_vendedores`, `dim_lojas`, `dim_veiculos`, `dim_estagio`, `dim_vendedor_periodo`

**Facts:** `fato_leads`, `fato_vendas`, `fato_agendamentos`, `fato_meta_vendedor`, `fato_meta_loja`

Foreign key convention: `id_YYYYMMDD` integer → `dim_data.id_data`; all dimension FK integers.

## Key business rules — never break

| Rule | Detail | Implementation |
|---|---|---|
| R1 | A seller's store is resolved to the store they worked at **on the event date**, not their current store | `etl/transform/fato_leads.py`, `fato_vendas.py`, `fato_agendamentos.py` |
| R2 | No rows are ever dropped for missing matches — unknown seller/store gets `id = -1` | All fato transforms; uses left join + `fillna(-1)` |
| R3 | De/Para mappings (canais, vendedores) are applied **before** any join | Applied in `etl/extract/` immediately after reading each source |
| R4 | `id_veiculo = Código` — consistent primary key across all sales files | `etl/transform/fato_vendas.py`, `dim_veiculos.py` |
| R5 | `dim_vendedor_periodo` is an audit table only — **do not use as a bridge table** in Metabase | Documented in `etl/run.py` |
| R6 | Commission join onto `fato_vendas` is always a left join — `fato_vendas` never loses rows | `etl/transform/fato_vendas.py` |
| R7 | Brand (`marca`) enrichment priority: current stock file → historical sales files → "desconhecida" | `etl/transform/dim_veiculos.py` |

## Infrastructure

```
# PostgreSQL — running via Docker
docker run -d --name crm-postgres \
  -e POSTGRES_DB=crm_analytics -e POSTGRES_USER=crm -e POSTGRES_PASSWORD=crm123 \
  -p 5432:5432 postgres:16

# Metabase — running via Docker at http://localhost:3000
docker run -d --name crm-metabase -p 3000:3000 metabase/metabase:latest
```

PostgreSQL tables mirror gold Parquets exactly, all in schema `gold`. Load strategy is truncate + insert — dataset is small enough.

## normalizar_texto()

Central text normalization utility in `etl/utils.py` used before every join: strips whitespace, lowercases, removes accents via NFKD decomposition, removes non-alphanumeric characters, collapses whitespace. Must be applied to text columns before any merge to avoid mismatches.
