# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

CRM Analytics ETL pipeline for a multi-store car dealership. Reads Excel exports from a CRM, transforms them into a star schema, writes Parquet files to `data/gold/`, and (planned) loads them into PostgreSQL for Metabase dashboards.

## Commands

```powershell
# Activate virtual environment (Windows)
.\.venv\Scripts\Activate.ps1

# Run the full ETL
python etl/transform.py

# Install dependencies
pip install -r requirements.txt
```

There are no tests yet. The PRD (see `PRD.md`) specifies pytest unit tests as a Fase 3 deliverable.

## Architecture

### Data layers

```
data/raw/        ← Excel source files (CRM exports + complementary data)
data/outros/     ← Supplementary files: gerencial_estoque_marca.xlsx, Vendas_Marca_YYYY.xlsx, Vendas_comissao_YYYY.xlsx
data/silver/     ← Planned: intermediate Parquets per entity (not yet implemented)
data/gold/       ← Final star-schema Parquets consumed by Metabase
```

### ETL entry point

Currently a single monolithic script: `etl/transform.py`. The planned refactor (Fase 3) splits it into:
- `etl/extract/<entity>.py` — reads one Excel source, validates schema, returns a DataFrame, writes to silver
- `etl/transform/<table>.py` — pure transformation functions, no file I/O
- `etl/load.py` — writes gold Parquets + upserts to PostgreSQL (`crm_analytics` db, schema `gold`)
- `etl/validate.py` — post-load quality report
- `etl/config.py` — path constants (`RAW_PATH`, `OTHERS_PATH`, `SILVER_PATH`, `GOLD_PATH`, PG credentials)
- `etl/run.py` — orchestrates the full pipeline

### Star schema (gold layer)

**Dimensions:** `dim_canal`, `dim_data`, `dim_vendedores`, `dim_lojas`, `dim_veiculos`, `dim_estagio`, `dim_vendedor_periodo`

**Facts:** `fato_leads`, `fato_vendas`, `fato_agendamentos`, `fato_meta_vendedor`, `fato_meta_loja`

Foreign key convention: `id_YYYYMMDD` integer → `dim_data.id_data`; all dimension FK integers.

## Key business rules — never break

| Rule | Detail | Implementation |
|---|---|---|
| R1 | A seller's store is resolved to the store they worked at **on the event date**, not their current store | `adicionar_vendedor_loja()` in `transform.py` |
| R2 | No rows are ever dropped for missing matches — unknown seller/store gets `id = -1` | Same function; uses `left join` + `fillna(-1)` |
| R3 | De/Para mappings (canais, vendedores) are applied **before** any join | Applied immediately after reading each source |
| R4 | `id_veiculo = Código` — consistent primary key across all sales files | `fato_vendas`, `dim_veiculos` |
| R5 | `dim_vendedor_periodo` is an audit table only — **do not use as a bridge table** in Metabase | Documented in `transform.py` comment |
| R6 | Commission join onto `fato_vendas` is always a left join — `fato_vendas` never loses rows | Planned: `transform/fato_vendas.py` |
| R7 | Brand (`marca`) enrichment priority: current stock file → historical sales files → "desconhecida" | Planned: `transform/dim_veiculos.py` |

## Current gaps (active work items)

- `dim_veiculos` lacks `marca` — needs join with `data/outros/gerencial_estoque_marca.xlsx` then fallback to `Vendas_Marca_YYYY.xlsx`
- `fato_vendas` lacks financial columns — needs join with `data/outros/Vendas_comissao_YYYY.xlsx`
- `dim_data` missing: `trimestre`, `semestre`, `dia_semana`, `fim_de_semana`, `dias_uteis_mes`
- ETL is monolithic (`etl/transform.py` ~500 lines) — refactor is Fase 3
- No PostgreSQL loader yet — Metabase requires it (Fase 2)
- `data/silver/` layer not yet written

## Infrastructure (planned, not yet running)

```bash
# PostgreSQL
docker run -d --name crm-postgres \
  -e POSTGRES_DB=crm_analytics -e POSTGRES_USER=crm -e POSTGRES_PASSWORD=crm123 \
  -p 5432:5432 postgres:16

# Metabase
docker run -d --name crm-metabase -p 3000:3000 metabase/metabase:latest
```

PostgreSQL tables mirror gold Parquets exactly, all in schema `gold`. Load strategy is truncate + insert (not incremental upsert) — dataset is small enough.

## normalizar_texto()

Central text normalization utility used before every join: strips whitespace, lowercases, removes accents via NFKD decomposition, removes non-alphanumeric characters, collapses whitespace. Must be applied to text columns before any merge to avoid mismatches.
