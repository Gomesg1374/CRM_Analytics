# PRD — CRM Analytics | Concessionária de Veículos

**Versão:** 3.0  
**Data:** 2026-05-19  
**Status:** Ativo

---

## 1. Objetivo

Transformar exports Excel do CRM de uma concessionária de veículos com múltiplas lojas em uma plataforma analítica open source — com ETL Python, banco PostgreSQL e dashboards no Metabase — capaz de acompanhar funil de vendas, metas, comissões e performance por loja, vendedor, canal e marca.

### Stack final

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
           Metabase          ← dashboards open source para o cliente
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
| `gerencial_estoque.xlsx` | Codigo, Modelo, Ano, Cor, Placa, Tipo, Situação | **Não tem Marca** |
| `usuarios.xlsx` | id_usuario, nome_usuario | Cadastro de vendedores |
| `hist_vendedor_loja.xlsx` | id_vendedor, id_loja, loja, data_inicio, data_fim | Histórico de lotação |
| `meta_vendedor.xlsx` | id_vendedor, ano_mes, meta_qtd | Metas mensais |
| `meta_loja.xlsx` | id_loja, ano_mes, meta_qtd | Metas mensais |
| `de_para_canais.xlsx` | canal_origem, canal_padrao | Padronização de nomes |
| `de_para_vendedores.xlsx` | nome_origem, nome_padrao | Padronização de nomes |

### 2.2 `data/outros/` — dados complementares (a integrar)

| Arquivo | Colunas relevantes | Destino no modelo |
|---|---|---|
| `gerencial_estoque_marca.xlsx` | Código, Marca, Modelo, Ano, Cor, Placa, Tipo | `dim_veiculos.marca` — fonte primária |
| `Vendas_Marca_YYYY.xlsx` | Código, Dt. Venda, Marca, Modelo, Ano, Cor, Placa, Tipo, Compra, Venda, Lançamentos, Vendedor | `dim_veiculos.marca` — fallback para veículos históricos fora do estoque atual |
| `Vendas_comissao_YYYY.xlsx` | Código, Comissão, Impostos, Lucro, Retorno | `fato_vendas.comissao / .impostos / .lucro / .retorno` |

**Chave de junção universal:** `Código` em todos os arquivos de vendas = `id_venda` em `fato_vendas`.

---

## 3. Estado atual — o que existe e o que falta

### O que já funciona
- `etl/transform.py` processa Leads, Vendas, Canais, Agendamentos, Metas e gera 12 Parquets na camada gold
- Resolução histórica de loja por data do evento (`adicionar_vendedor_loja`)
- Padronização de texto e de/para antes de qualquer join
- Diagnóstico de linhas sem match ao final de cada execução

### O que está incompleto

| Lacuna | Detalhe |
|---|---|
| `dim_veiculos` sem `marca` | `gerencial_estoque.xlsx` não tem a coluna; ela existe em `gerencial_estoque_marca.xlsx` e em `Vendas_Marca_YYYY.xlsx` |
| `fato_vendas` sem financeiro | `comissao`, `impostos`, `lucro` e `retorno` estão em `Vendas_comissao_YYYY.xlsx`, não integrados ainda |
| `dim_data` incompleta | Faltam: `trimestre`, `semestre`, `dia_semana`, `fim_de_semana`, `dias_uteis_mes` |
| ETL monolítico | Um único script de 500 linhas — sem separação de responsabilidades, sem testes |
| Sem validação de entrada | Mudança de coluna no Excel quebra silenciosamente |
| Camada silver vazia | Intermediários não são persistidos — impossível auditar por etapa |
| Sem banco — só Parquets | Metabase precisa de um banco SQL; hoje só há Parquets |

---

## 4. O que construir — especificações

---

### 4.1 Enriquecer `dim_veiculos` com Marca

**Problema:** `gerencial_estoque.xlsx` (fonte atual) não tem coluna `Marca`. Ela existe em dois outros arquivos.

**Lógica de enriquecimento (ordem de prioridade):**

```
1. Lê gerencial_estoque.xlsx          → base sem Marca (Codigo, Modelo, Ano, Cor, Placa, Tipo, Situação)
2. Lê gerencial_estoque_marca.xlsx    → join por Código → preenche Marca (cobertura: estoque atual)
3. Lê Vendas_Marca_YYYY.xlsx (2022–2026) concat
   → para cada Código ainda sem Marca, busca no histórico de vendas
   → pega a Marca mais recente por Código (sort Dt.Venda desc + drop_duplicates)
4. Veículos ainda sem Marca → "desconhecida"
```

**Schema resultante de `dim_veiculos`:**

| Coluna | Tipo | Fonte | Obrigatório |
|---|---|---|---|
| `id_veiculo` | int | `gerencial_estoque.Codigo` | ✅ |
| `marca` | str | `estoque_marca.Marca` ou `Vendas_Marca.Marca` | fallback "desconhecida" |
| `modelo` | str | `gerencial_estoque.Modelo` — normalizado | ✅ |
| `ano` | str | `gerencial_estoque.Ano` | ✅ |
| `cor` | str | `gerencial_estoque.Cor` — normalizado | ✅ |
| `tipo` | str | `gerencial_estoque.Tipo` — normalizado | ✅ |
| `placa` | str | `gerencial_estoque.Placa` | ✅ |
| `situacao` | str | `gerencial_estoque.Situação` — normalizado | ✅ |

**Critério de aceite:** nenhum `id_veiculo` com `marca = NULL`; proporção de "desconhecida" < 5% do total.

---

### 4.2 Enriquecer `fato_vendas` com dados financeiros

**Problema:** `fato_vendas` tem valor de venda e compra, mas não tem comissão, impostos nem lucro real — que estão em `Vendas_comissao_YYYY.xlsx`.

**Lógica de integração:**

```
1. Lê Vendas_comissao_YYYY.xlsx para cada ano (2022–2026) → concat
2. Normaliza colunas: Código → id_venda, Comissão → comissao, etc.
3. Left join com fato_vendas por id_venda = Código
4. Linhas sem match → NaN (nenhuma linha descartada da fato_vendas)
```

**Colunas adicionadas em `fato_vendas`:**

| Coluna nova | Tipo | Fonte | Descrição |
|---|---|---|---|
| `comissao` | float | `Vendas_comissao.Comissão` | Comissão paga ao vendedor na operação |
| `impostos` | float | `Vendas_comissao.Impostos` | Impostos incidentes |
| `lucro` | float | `Vendas_comissao.Lucro` | Lucro líquido da venda |
| `retorno` | float | `Vendas_comissao.Retorno` | Retorno financeiro bruto |

**Schema completo de `fato_vendas` após enriquecimento:**

| Coluna | Tipo |
|---|---|
| `id_venda` | int — chave |
| `id_veiculo` | int — FK dim_veiculos |
| `id_vendedor` | int — FK dim_vendedores |
| `id_loja` | int — FK dim_lojas |
| `id_canal` | int — FK dim_canal |
| `id_data` | int — FK dim_data (YYYYMMDD) |
| `ano_mes` | int — YYYYMM |
| `placa` | str |
| `modelo` | str |
| `cliente` | str |
| `valor_venda` | float |
| `valor_compra` | float |
| `custos` | float |
| `desconto` | float |
| `situacao` | str |
| `comissao` | float ← **novo** |
| `impostos` | float ← **novo** |
| `lucro` | float ← **novo** |
| `retorno` | float ← **novo** |

**Critério de aceite:** cobertura de `comissao` não-nula ≥ 90% das linhas de `fato_vendas`.

---

### 4.3 Completar `dim_data`

**Problema:** `dim_data` é gerada com campos básicos; campos derivados de calendário ficavam no Power BI e precisam agora estar no ETL.

**Schema completo de `dim_data`:**

| Coluna | Tipo | Lógica |
|---|---|---|
| `id_data` | int | `YYYYMMDD` — chave |
| `data` | date | |
| `ano` | int | `.dt.year` |
| `mes` | int | `.dt.month` |
| `ano_mes` | int | `ano * 100 + mes` |
| `nome_mes` | str | "Janeiro" … "Dezembro" |
| `ano_mes_desc` | str | "2025-01" |
| `trimestre` | int | `ceil(mes / 3)` |
| `semestre` | int | `1 if mes <= 6 else 2` |
| `dia_semana` | str | "Segunda" … "Domingo" — em português |
| `num_dia_semana` | int | 0 = Segunda … 6 = Domingo |
| `fim_de_semana` | int | `1 if num_dia_semana >= 5 else 0` |
| `dias_uteis_mes` | int | Dias úteis no mês (seg–sex, sem feriados nacionais) |

**Critério de aceite:** cobertura de 2022-01-01 a 2027-12-31; `trimestre` e `semestre` sem NULL.

---

### 4.4 Refatorar o ETL

**Problema:** `transform.py` é um script monolítico de ~500 linhas — impossível testar por entidade, adicionar novos dados sem risco de regressão, ou auditar erros por etapa.

**Estrutura de pastas proposta:**

```
etl/
├── config.py                   # RAW_PATH, OUTROS_PATH, SILVER_PATH, GOLD_PATH, PG_*
├── utils.py                    # normalizar_texto(), adicionar_vendedor_loja()
│
├── extract/
│   ├── leads.py                # Lê Leads.xlsx → valida schema → retorna DataFrame
│   ├── vendas.py               # Lê Vendas_YYYY.xlsx (todos os anos) → concat → valida
│   ├── canais.py               # Lê dados_canais_YYYY.xlsx (todos os anos) → concat
│   ├── agendamentos.py         # Lê controleagendamentos.xlsx → valida
│   ├── veiculos.py             # Lê gerencial_estoque.xlsx + estoque_marca + Vendas_Marca
│   ├── comissoes.py            # Lê Vendas_comissao_YYYY.xlsx (todos os anos) → concat
│   └── dimensoes_base.py       # Lê usuarios, hist_vendedor_loja, metas, de_para_*
│
├── transform/
│   ├── dim_veiculos.py         # Merge estoque + marca (lógica da seção 4.1)
│   ├── dim_data.py             # Gera dim_data completa (lógica da seção 4.3)
│   ├── dim_canal.py
│   ├── dim_vendedores.py
│   ├── dim_lojas.py
│   ├── fato_leads.py
│   ├── fato_vendas.py          # Inclui join com comissoes (lógica da seção 4.2)
│   ├── fato_agendamentos.py
│   └── fato_metas.py
│
├── load.py                     # Salva Parquets em gold/ + upsert no PostgreSQL
├── validate.py                 # Checa schemas de entrada e diagnóstico pós-carga
└── run.py                      # Entry point: extract → silver → transform → gold → load → validate
```

**Contrato de cada módulo extract:**
- Recebe: nenhum argumento (lê de `config.RAW_PATH` / `config.OUTROS_PATH`)
- Retorna: DataFrame com colunas validadas e normalizadas
- Lança: `ValueError` descritivo se coluna obrigatória não for encontrada no Excel
- Persiste: uma cópia do resultado em `data/silver/<entidade>.parquet` (antes de qualquer join)

**Contrato de cada módulo transform:**
- Recebe: DataFrames do extract e dimensões necessárias como parâmetros
- Retorna: DataFrame final pronto para carga
- Não lê arquivos — apenas transforma

**Critério de aceite do refactor:** `python etl/run.py` produz os mesmos 12 Parquets com os mesmos valores; cada módulo tem pelo menos um teste unitário; `validate.py` imprime relatório de qualidade ao final.

---

### 4.5 Carregar dados no PostgreSQL

**Problema:** Metabase precisa de um banco SQL com conector nativo; hoje só existem Parquets.

**Estratégia de carga:**

- ETL grava Parquets em `data/gold/` (mantido para auditoria e backup)
- `load.py` também faz upsert de cada Parquet no PostgreSQL após a geração
- Estratégia de upsert: truncate + insert (dados não são grandes o suficiente para precisar de merge incremental)
- Banco: `crm_analytics`, schema: `gold`

**Tabelas no PostgreSQL** (espelham exatamente os Parquets):

```
gold.dim_canal
gold.dim_data
gold.dim_vendedores
gold.dim_lojas
gold.dim_veiculos
gold.dim_estagio
gold.dim_vendedor_periodo
gold.fato_leads
gold.fato_vendas
gold.fato_agendamentos
gold.fato_meta_vendedor
gold.fato_meta_loja
```

**Dependências:** `psycopg2-binary` ou `sqlalchemy` + driver PostgreSQL adicionados ao `requirements.txt`.

**Setup local (Docker):**

```bash
docker run -d \
  --name crm-postgres \
  -e POSTGRES_DB=crm_analytics \
  -e POSTGRES_USER=crm \
  -e POSTGRES_PASSWORD=crm123 \
  -p 5432:5432 \
  postgres:16
```

**Critério de aceite:** `load.py` conclui sem erros; row count no PostgreSQL bate com row count dos Parquets; Metabase consegue executar uma query de teste em `gold.fato_vendas`.

---

### 4.6 Configurar Metabase

**Setup local (Docker):**

```bash
docker run -d \
  --name crm-metabase \
  -p 3000:3000 \
  metabase/metabase:latest
```

**Conexão com PostgreSQL:** acessar `localhost:3000` → Admin → Databases → Add → PostgreSQL → apontar para o container `crm-postgres`.

**Dashboards prioritários a construir:**

| Dashboard | Métricas principais |
|---|---|
| **Funil Comercial** | Leads recebidos, agendamentos, visitas, vendas; taxas de conversão por etapa; motivos de perda |
| **Performance de Vendas** | Vendas vs. meta por vendedor e loja; ticket médio; desconto médio; margem bruta (`valor_venda − valor_compra − custos`) |
| **Financeiro** | Lucro líquido, comissões pagas, impostos; margem líquida por loja e por vendedor |
| **Canais e Leads** | Volume de leads por canal ao longo do tempo; conversão por canal |
| **Estoque e Marca** | Vendas por marca e modelo; participação de mercado por marca |

**Critério de aceite:** cliente consegue navegar nos dashboards, aplicar filtros de data/loja/vendedor e exportar um relatório sem assistência.

---

## 5. Modelo estrela final

```
                              dim_data
                                 │
dim_canal ──── fato_leads ───────┤──── dim_vendedores ──── dim_lojas
                    │            │            │
               dim_estagio       │     dim_vendedor_periodo
                                 │     (auditoria — não relacionar no BI)
dim_canal ──── fato_vendas ──────┤──── dim_vendedores ──── dim_lojas
                    │            │
               dim_veiculos      │    (agora com Marca + dados financeiros)
                                 │
        fato_agendamentos ───────┤──── dim_vendedores ──── dim_lojas
               │                 │
           dim_canal             │
                                 │
        fato_meta_vendedor ──────┴──── dim_vendedores
        fato_meta_loja          ────── dim_lojas
```

---

## 6. Regras de negócio — não quebrar

| # | Regra | Onde está implementada |
|---|---|---|
| R1 | A loja de um vendedor num evento é a loja dele **na data do evento**, não a atual | `utils.adicionar_vendedor_loja()` |
| R2 | Nenhuma linha é descartada por falta de match — vendedor/loja desconhecido recebe `id = −1` | `utils.adicionar_vendedor_loja()` |
| R3 | De/Para de canais e vendedores é aplicado **antes** de qualquer join | Módulos `extract/` |
| R4 | `id_veiculo = Código` — chave consistente em todos os arquivos de vendas | `fato_vendas`, `dim_veiculos` |
| R5 | `dim_vendedor_periodo` é tabela de auditoria — **não usar como bridge** no Metabase | Documentação de modelo |
| R6 | Join com comissões é `left join` — `fato_vendas` nunca perde linhas por falta de comissão | `transform/fato_vendas.py` |
| R7 | Join de Marca em `dim_veiculos` segue prioridade: estoque atual → histórico de vendas → "desconhecida" | `transform/dim_veiculos.py` |

---

## 7. Roadmap

### Fase 1 — Enriquecimento do modelo (sem refatorar estrutura)
> Objetivo: fechar as lacunas de dados sem mudar a arquitetura do `transform.py` ainda.
> Entrega: rodar o script atual e ter `marca` e dados financeiros disponíveis.

- [ ] **F1.1** Adicionar lógica de Marca em `dim_veiculos` no `transform.py` (seção 4.1)
- [ ] **F1.2** Adicionar colunas financeiras em `fato_vendas` no `transform.py` (seção 4.2)
- [ ] **F1.3** Completar `dim_data` com trimestre, semestre, dia da semana e dias úteis (seção 4.3)
- [ ] **F1.4** Validar: row counts, cobertura de marca ≥ 95%, cobertura de comissão ≥ 90%

### Fase 2 — Banco de dados e visualização
> Objetivo: ter Metabase funcionando com dados reais, substituindo Power BI.

- [ ] **F2.1** Subir PostgreSQL via Docker
- [ ] **F2.2** Criar script `load.py` que lê Parquets de `gold/` e faz upsert no PostgreSQL
- [ ] **F2.3** Conectar Metabase ao PostgreSQL
- [ ] **F2.4** Construir os 5 dashboards prioritários (seção 4.6)
- [ ] **F2.5** Treinamento básico do cliente no Metabase

### Fase 3 — Refatoração do ETL
> Objetivo: deixar o código sustentável para novas entidades e novos colaboradores.

- [x] **F3.1** Criar estrutura de pastas `extract/`, `transform/`, `load.py`, `validate.py`, `run.py`
- [x] **F3.2** Extrair cada entidade para seu módulo em `extract/` com validação de schema
- [x] **F3.3** Extrair cada tabela para seu módulo em `transform/`
- [x] **F3.4** Implementar `validate.py` com diagnóstico de qualidade pós-carga
- [x] **F3.5** Escrever testes unitários para `normalizar_texto()` e `adicionar_vendedor_loja()`
- [x] **F3.6** Implementar persistência da camada silver (um Parquet por entidade raw limpa)

### Fase 4 — Orquestração
> Objetivo: eliminar execução manual do ETL.

- [ ] **F4.1** Configurar execução automática via cron ou Task Scheduler (Windows)
- [ ] **F4.2** Adicionar notificação por e-mail em caso de falha

---

## 8. Dependências

| Componente | Ferramenta | Versão |
|---|---|---|
| Python | Runtime | 3.11+ |
| pandas | Processamento | 3.x |
| numpy | Cálculos | 2.x |
| psycopg2-binary | Conexão PostgreSQL | 2.9+ |
| sqlalchemy | ORM / upsert | 2.x |
| PostgreSQL | Banco analítico | 16 (Docker) |
| Metabase CE | Dashboards | 0.49+ (Docker) |
| Docker | Containers | 24+ |
