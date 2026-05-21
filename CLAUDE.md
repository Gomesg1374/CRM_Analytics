# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CRM Analytics Data Warehouse for a multi-store vehicle dealership ("Concessionária de Veículos"). Transforms Excel source files into a Parquet-based star schema for BI consumption (currently Power BI; migration to Metabase+DuckDB is planned). The authoritative specification is **PRD.md** — read it before making structural changes.

## Commands

```powershell
# Activate virtual environment (Windows)
.\.venv\Scripts\Activate.ps1

# Run the full ETL pipeline
python etl/transform.py

# dbt commands (run from crm_analytics_dbt/)
dbt run
dbt test
dbt run --select staging    # run only staging models
```

There is no test suite yet (P3 in PRD.md). No Makefile or CI pipeline.

## Architecture

### Data Flow

```
data/raw/      (22 Excel files — leads, vendas, agendamentos, de_para tables, metas)
data/outros/   (11 Excel files — vendas_marca, comissão; NOT yet integrated)
      ↓
etl/transform.py   (pandas-based ETL, ~500 lines, single entry point)
      ↓
data/silver/   (empty — planned intermediate layer)
      ↓
data/gold/     (13 Parquet files — star schema)
      ↓
[Future] DuckDB + Metabase (Docker)
```

### Star Schema (`data/gold/`)

- **Dimensions:** `dim_canal`, `dim_data`, `dim_vendedores`, `dim_lojas`, `dim_veiculos`, `dim_estagio`, `dim_vendedor_periodo`
- **Facts:** `fato_leads`, `fato_vendas`, `fato_agendamentos`, `fato_meta_vendedor`, `fato_meta_loja`

### dbt Layer (`crm_analytics_dbt/`)

Secondary/alternative transformation layer using DuckDB adapter. Models mirror the Python ETL:
- `models/staging/` → `stg_leads`, `stg_agendamentos`
- `models/dimensions/` → `dim_data`, `dim_atendente`, `dim_canal`, `dim_empresa`
- `models/marts/` → `fato_leads`, `fato_agendamentos`

The Python ETL in `etl/transform.py` is the currently active pipeline; the dbt layer is in parallel development.

## Critical Business Rules

These invariants must be preserved in any refactor:

1. **Resolve seller's store at event date** — use `dim_vendedor_periodo` (audit table of seller↔store history) to assign the correct store for each event, not the seller's current store.
2. **Never drop rows for unknown seller/store** — unknown entities get `id = -1`.
3. **Apply de/para standardization before any joins** — raw Excel text is inconsistent; normalization via the de_para lookup tables must happen first.
4. **`id_veiculo` = Código field** — the vehicle key is consistent across all sales files.
5. **`dim_vendedor_periodo` is audit-only** — not a bridge table; do not use it as a standard dimension.

## Known Gaps (from PRD.md)

| ID | Issue |
|----|-------|
| P1 | `etl/transform.py` is monolithic (no extract/transform/load separation) |
| P2 | Silver layer is empty |
| P3 | No automated tests or schema validation |
| P6 | `dim_veiculos` missing `Marca` column |
| P7 | `fato_vendas` missing comissão, impostos, lucro fields |
| P8 | `dim_data` incomplete (trimestre, dias_uteis missing) |
| P9 | `data/outros/` files not yet integrated |

The PRD.md roadmap defines 4 phases for resolving these — check it before planning new features.
