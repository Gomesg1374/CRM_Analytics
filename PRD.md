# PRD — CRM Analytics | Concessionária de Veículos

**Versão:** 4.0  
**Data:** 2026-05-21  
**Status:** Ativo

---

## 1. Objetivo

Transformar exports Excel do CRM de uma concessionária de veículos com múltiplas lojas em uma plataforma analítica open source — com ETL Python, banco PostgreSQL e dashboards no Metabase — capaz de acompanhar funil de vendas, metas, comissões e performance por loja, vendedor, canal e marca.

### Stack

```
Excel (raw/ + outros/)
        │
        ▼
  Python ETL            ← pandas, modularizado por entidade
        │
        ├─► data/silver/    ← intermediários por entidade (auditoria)
        │
        └─► data/gold/      ← Parquets — star schema
                │
                ▼
          PostgreSQL         ← banco analítico, carregado pelo ETL
                │
                ▼
           Metabase          ← dashboards open source (construídos manualmente na UI)
```

---

## 2. Fontes de dados

### 2.1 `data/raw/` — dados do CRM (entrada principal)

| Arquivo | Colunas relevantes | Observação |
|---|---|---|
| `Leads.xlsx` | id, cliente, canal, atendente, conversão, motivo, data_criacao, ultima_integracao | Base completa de leads |
| `Vendas_YYYY.xlsx` | Código, Dt. Venda, Vendedor, Venda, Compra, Lançamentos, Situação, Desconto | Um arquivo por ano, 2022–2026 |
| `dados_canais_YYYY.xlsx` | codigo, canal | Canal por código de venda, um arquivo por ano |
| `controleagendamentos.xlsx` | id, responsavel_agendamento, canal, criacao_agendamento, agendado_para, flag_agendamento, flag_visita, campanha, status, motivo, id_venda | |
| `gerencial_estoque.xlsx` | Codigo, Modelo, Ano, Cor, Placa, Tipo, Situação | Não tem Marca |
| `usuarios.xlsx` | id_usuario, nome_usuario | Cadastro de vendedores |
| `hist_vendedor_loja.xlsx` | id_vendedor, id_loja, loja, data_inicio, data_fim | Histórico de lotação |
| `meta_vendedor.xlsx` | id_vendedor, ano_mes, meta_qtd | Metas mensais |
| `meta_loja.xlsx` | id_loja, ano_mes, meta_qtd | Metas mensais |
| `de_para_canais.xlsx` | canal_origem, canal_padrao | Padronização de nomes |
| `de_para_vendedores.xlsx` | nome_origem, nome_padrao | Padronização de nomes |

### 2.2 `data/outros/` — dados complementares

| Arquivo | Colunas relevantes | Destino no modelo |
|---|---|---|
| `gerencial_estoque_marca.xlsx` | Código, Marca, Modelo, Ano, Cor, Placa, Tipo | `dim_veiculos.marca` — fonte primária |
| `Vendas_Marca_YYYY.xlsx` | Código, Dt. Venda, Marca, Modelo, Ano, Cor, Placa, Tipo, Compra, Venda, Lançamentos, Vendedor | `dim_veiculos.marca` — fallback para veículos históricos |
| `Vendas_comissao_YYYY.xlsx` | Código, Comissão, Impostos, Lucro, Retorno | `fato_vendas.comissao / .impostos / .lucro / .retorno` |

**Chave de junção universal:** `Código` em todos os arquivos de vendas = `id_venda` em `fato_vendas`.

---

## 3. Estado atual

### O que está funcionando

- Pipeline modular completo: `etl/extract/` (7 módulos) + `etl/transform/` (9 módulos) + `etl/load.py`
- `dim_veiculos` com `marca` — prioridade: estoque atual → histórico de vendas → "desconhecida" (0% desconhecida sobre veículos ativos)
- `fato_vendas` com dados financeiros — `comissao`, `impostos`, `lucro`, `retorno` (100% de cobertura)
- `dim_data` completa com `trimestre`, `semestre`, `dia_semana`, `fim_de_semana`, `dias_uteis_mes`
- Camada silver persistida (10 Parquets intermediários)
- 12 Parquets na camada gold (star schema completo)
- PostgreSQL rodando via Docker (`crm-postgres`, porta 5432), schema `gold` com 12 tabelas carregadas
- Metabase rodando via Docker (`crm-metabase`, porta 3000), conectado ao PostgreSQL
- Task Scheduler executa o ETL diariamente às 10:00, iniciando Docker automaticamente se necessário
- Notificação por e-mail em caso de falha

### O que ainda falta

| Item | Detalhe |
|---|---|
| Dashboards no Metabase | Serão construídos manualmente na UI — primeiro prototipados no Power BI |
| Testes de integração | `tests/test_utils.py` cobre utilitários; módulos extract/transform sem testes |

---

## 4. Modelo estrela (gold layer)

**Dimensions:** `dim_canal`, `dim_data`, `dim_vendedores`, `dim_lojas`, `dim_veiculos`, `dim_estagio`, `dim_vendedor_periodo`

**Facts:** `fato_leads`, `fato_vendas`, `fato_agendamentos`, `fato_meta_vendedor`, `fato_meta_loja`

```
                          dim_data
                             │
dim_canal ── fato_leads ─────┤──── dim_vendedores ──── dim_lojas
                 │           │            │
            dim_estagio      │     dim_vendedor_periodo
                             │     (auditoria — não relacionar no BI)
dim_canal ── fato_vendas ────┤──── dim_vendedores ──── dim_lojas
                 │           │
            dim_veiculos     │
                             │
     fato_agendamentos ──────┤──── dim_vendedores ──── dim_lojas
            │                │
        dim_canal            │
                             │
     fato_meta_vendedor ─────┴──── dim_vendedores
     fato_meta_loja         ────── dim_lojas
```

Foreign key convention: `id_YYYYMMDD` integer → `dim_data.id_data`; todas as FKs de dimensão são inteiros.

---

## 5. Regras de negócio — nunca quebrar

| # | Regra | Implementação |
|---|---|---|
| R1 | A loja de um vendedor num evento é a loja dele **na data do evento**, não a atual | `etl/transform/fato_leads.py`, `fato_vendas.py`, `fato_agendamentos.py` |
| R2 | Nenhuma linha é descartada por falta de match — vendedor/loja desconhecido recebe `id = −1` | Todos os módulos fato; left join + `fillna(-1)` |
| R3 | De/Para de canais e vendedores é aplicado **antes** de qualquer join | Módulos `etl/extract/` |
| R4 | `id_veiculo = Código` — chave consistente em todos os arquivos de vendas | `etl/transform/fato_vendas.py`, `dim_veiculos.py` |
| R5 | `dim_vendedor_periodo` é tabela de auditoria — **não usar como bridge** no Metabase | Documentado em `etl/run.py` |
| R6 | Join com comissões é `left join` — `fato_vendas` nunca perde linhas | `etl/transform/fato_vendas.py` |
| R7 | Marca em `dim_veiculos`: estoque atual → histórico de vendas → "desconhecida" | `etl/transform/dim_veiculos.py` |

---

## 6. Critérios de aceite (validados a cada execução)

| Critério | Threshold | Status |
|---|---|---|
| Marca desconhecida em veículos ativos | < 5% | ✅ 0.0% |
| Cobertura de comissão em `fato_vendas` | ≥ 90% | ✅ 100% |
| `dim_data` cobre 2022-01-01 a 2027-12-31 | sem gaps | ✅ |
| `dim_data` sem NULLs em trimestre/semestre/dia_semana/dias_uteis_mes | 0 NULLs | ✅ |
| `fato_vendas` não perde linhas no join com comissão (R6) | 0 linhas descartadas | ✅ |

---

## 7. Infraestrutura

### Containers Docker (em execução)

```bash
# PostgreSQL
docker run -d --name crm-postgres \
  -e POSTGRES_DB=crm_analytics -e POSTGRES_USER=crm -e POSTGRES_PASSWORD=crm123 \
  -p 5432:5432 postgres:16

# Metabase (http://localhost:3000)
docker run -d --name crm-metabase -p 3000:3000 metabase/metabase:latest
```

### Agendamento

`scheduler/run_etl.ps1` é executado diariamente às 10:00 pelo Windows Task Scheduler. O script inicia o Docker Desktop e os containers automaticamente caso não estejam rodando, aguarda o PostgreSQL aceitar conexões e então executa `python -m etl.run`.

---

## 8. Roadmap

### Fase 1 — Enriquecimento do modelo ✅
- [x] **F1.1** `dim_veiculos` com `marca` (prioridade: estoque atual → histórico → "desconhecida")
- [x] **F1.2** `fato_vendas` com dados financeiros (comissao, impostos, lucro, retorno)
- [x] **F1.3** `dim_data` completa (trimestre, semestre, dia_semana, fim_de_semana, dias_uteis_mes)
- [x] **F1.4** Critérios de aceite validados automaticamente pelo pipeline

### Fase 2 — Banco de dados e visualização ✅ (parcial)
- [x] **F2.1** PostgreSQL via Docker
- [x] **F2.2** `etl/load.py` — truncate + insert em schema `gold`
- [x] **F2.3** Metabase conectado ao PostgreSQL
- [ ] **F2.4** Dashboards — protótipo no Power BI, depois reproduzir manualmente no Metabase
- [ ] **F2.5** Treinamento do cliente no Metabase

### Fase 3 — Refatoração do ETL ✅
- [x] **F3.1** Estrutura modular: `extract/`, `transform/`, `load.py`, `validate.py`, `run.py`
- [x] **F3.2** Módulos `extract/` com validação de schema e persistência em `data/silver/`
- [x] **F3.3** Módulos `transform/` — funções puras, sem I/O
- [x] **F3.4** `validate.py` com diagnóstico de qualidade pós-carga
- [x] **F3.5** Testes unitários para `normalizar_texto()` e utilitários
- [x] **F3.6** Camada silver persistida (10 Parquets intermediários)

### Fase 4 — Orquestração ✅
- [x] **F4.1** Task Scheduler (Windows) com execução diária às 10:00
- [x] **F4.2** Notificação por e-mail em caso de falha
- [x] **F4.3** Início automático do Docker e containers no agendamento

---

## 9. Dependências

| Componente | Ferramenta | Versão |
|---|---|---|
| Python | Runtime | 3.13 |
| pandas | Processamento | 3.x |
| numpy | Cálculos | 2.x |
| psycopg2-binary | Conexão PostgreSQL | 2.9+ |
| sqlalchemy | ORM / carga | 2.x |
| PostgreSQL | Banco analítico | 16 (Docker) |
| Metabase CE | Dashboards | 0.61 (Docker) |
| Docker | Containers | 24+ |
