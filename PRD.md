# PRD — CRM Analytics | Concessionária de Veículos

**Versão:** 2.0  
**Data:** 2026-05-19  
**Status:** Em elaboração

---

## 1. Contexto e Objetivo

Este projeto entrega uma plataforma de analytics de CRM para uma concessionária de veículos com múltiplas lojas e equipes comerciais. O objetivo é transformar dados brutos exportados do CRM em métricas confiáveis de desempenho comercial, acompanhamento de metas e análise de funil de conversão.

A solução deve ser **totalmente open source**, escalável, de fácil operação pelo cliente, e sem dependência de licenças proprietárias como Power BI.

---

## 2. Domínio de Negócio

### Entidades principais
- **Lojas**: múltiplas unidades, cada uma com sua equipe de vendedores
- **Vendedores**: mudam de loja ao longo do tempo — cada evento (lead, venda, agendamento) precisa refletir a loja do vendedor *na data do evento*
- **Leads**: oportunidades geradas por diferentes canais (mídias, indicação, site etc.)
- **Agendamentos**: visitas agendadas a partir de leads
- **Vendas**: negócios fechados com veículos do estoque
- **Veículos**: estoque com marca, modelo, ano, cor, tipo, placa
- **Metas**: por vendedor e por loja, com periodicidade mensal

### Fluxo do funil comercial
```
Lead → Agendamento → Visita → Venda
```

---

## 3. Fontes de dados

### 3.1 Camada raw — dados do CRM

| Arquivo | Descrição |
|---|---|
| `Leads.xlsx` | Base completa de leads |
| `Vendas_YYYY.xlsx` | Vendas por ano (2022–2026) — colunas: valor_venda, valor_compra, custos, situação |
| `dados_canais_YYYY.xlsx` | Canal de origem de cada venda por ano |
| `controleagendamentos.xlsx` | Registro de agendamentos e visitas |
| `gerencial_estoque.xlsx` | Estoque de veículos (sem marca) — colunas: Codigo, Modelo, Ano, Cor, Placa, Tipo, Situação |
| `usuarios.xlsx` | Cadastro de vendedores |
| `hist_vendedor_loja.xlsx` | Histórico de lotação vendedor → loja (com data_inicio e data_fim) |
| `meta_vendedor.xlsx` | Metas mensais por vendedor |
| `meta_loja.xlsx` | Metas mensais por loja |
| `de_para_canais.xlsx` | Tabela de padronização de nomes de canal |
| `de_para_vendedores.xlsx` | Tabela de padronização de nomes de vendedor |

### 3.2 Camada outros — dados complementares a integrar

Estes arquivos ficam separados porque são exportações de um módulo diferente do sistema, mas precisam ser incorporados ao pipeline:

| Arquivo | Conteúdo | O que entra no modelo |
|---|---|---|
| `gerencial_estoque_marca.xlsx` | Estoque com coluna **Marca** | `dim_veiculos.marca` |
| `Vendas_Marca_YYYY.xlsx` | Vendas 2022–2026 com coluna **Marca** | Enriquece `dim_veiculos.marca` para veículos históricos não encontrados no estoque atual |
| `Vendas_comissao_YYYY.xlsx` | Vendas 2022–2026 com **Comissão, Impostos, Lucro, Retorno** | `fato_vendas.comissao`, `.impostos`, `.lucro`, `.retorno` |

**Chave de junção em todos os casos:** coluna `Código` = `id_venda` (presente em todos os arquivos de vendas).

> **Por que dois arquivos de veículo?**  
> O `gerencial_estoque_marca.xlsx` traz o estoque atual com Marca. Para veículos vendidos em anos anteriores que já saíram do estoque, a Marca precisa ser buscada em `Vendas_Marca_YYYY.xlsx`. A estratégia é: primeiro tenta o estoque atual; se não encontrar pelo código, busca nos arquivos de vendas por marca.

---

## 4. Arquitetura atual

### 4.1 Estrutura de pastas

```
CRM_Analytics/
├── data/
│   ├── raw/          # Excels do CRM (entrada do pipeline)
│   ├── silver/       # ⚠️ Existe como diretório mas não é utilizado
│   ├── gold/         # Parquets — star schema pronto para consumo
│   └── outros/       # Excels complementares (marca, comissão)
├── etl/
│   └── transform.py  # Script único que executa todo o ETL
└── requirements.txt
```

### 4.2 ETL atual — `etl/transform.py`

Script Python monolítico (pandas + numpy) que lê os Excels de `raw/`, processa tudo em memória e grava Parquets em `gold/`. Principais responsabilidades:

- **Normalização de texto**: remove acentos, espaços e caracteres especiais via `normalizar_texto()`
- **De/Para**: padroniza variações de nome de canal e vendedor antes de qualquer join
- **Resolução histórica de loja**: `adicionar_vendedor_loja()` determina, para cada evento, a loja correta do vendedor *na data do evento*, usando merge com indicador para não descartar linhas sem match (id = −1 para desconhecido)
- **Criação das dimensões e fato-tabelas**
- **Diagnóstico**: imprime ao final o percentual de linhas sem vendedor/loja identificados

### 4.3 Modelo estrela atual (star schema)

```
                    dim_data
                       │
dim_canal ─── fato_leads ─── dim_vendedores ─── dim_lojas
                    │
               dim_estagio

dim_canal ─── fato_vendas ─── dim_vendedores ─── dim_lojas
                    │
               dim_veiculos ← (sem Marca ainda)
                    │
                dim_data

         fato_agendamentos ─── dim_vendedores ─── dim_lojas
                    │
                dim_data ── dim_canal

         fato_meta_vendedor ─── dim_vendedores
         fato_meta_loja     ─── dim_lojas

         dim_vendedor_periodo   (auditoria do histórico — não expor como relacionamento)
```

### 4.4 Saídas atuais da camada gold

| Arquivo parquet | Tipo |
|---|---|
| `dim_canal.parquet` | Dimensão |
| `dim_data.parquet` | Dimensão |
| `dim_vendedores.parquet` | Dimensão |
| `dim_lojas.parquet` | Dimensão |
| `dim_veiculos.parquet` | Dimensão — **falta coluna `marca`** |
| `dim_estagio.parquet` | Dimensão |
| `dim_vendedor_periodo.parquet` | Dimensão de auditoria |
| `fato_leads.parquet` | Fato |
| `fato_vendas.parquet` | Fato — **faltam `comissao`, `impostos`, `retorno`** |
| `fato_agendamentos.parquet` | Fato |
| `fato_meta_vendedor.parquet` | Fato |
| `fato_meta_loja.parquet` | Fato |

### 4.5 Visualização atual
Power BI Desktop consumindo os Parquets da camada gold. A ser substituído por solução open source.

---

## 5. Problemas identificados

### No ETL
| # | Problema | Impacto |
|---|---|---|
| P1 | Script monolítico — tudo em um único `transform.py` | Difícil de testar, manter e escalar |
| P2 | Camada silver vazia — nenhuma transformação intermediária é persistida | Impossível auditar erros por etapa |
| P3 | Sem testes automatizados | Regressões silenciosas ao adicionar dados novos |
| P4 | Sem validação de schema nas entradas | Quebra silenciosa se o Excel mudar de estrutura |
| P5 | Execução manual — sem agendamento | Dados desatualizados dependem de ação humana |
| P6 | `dim_veiculos` sem coluna `Marca` | Impossível segmentar análises por fabricante |
| P7 | `fato_vendas` sem comissão, impostos e lucro real | Margem calculada incompleta |
| P8 | `dim_data` com campos básicos — campos como trimestre e dias úteis ficavam no Power BI | Lógica de negócio acoplada à ferramenta de BI |
| P9 | Dados em `data/outros/` não integrados | Análises de marca e rentabilidade indisponíveis |

### Na visualização
| # | Problema | Impacto |
|---|---|---|
| V1 | Power BI requer licença e conhecimento da ferramenta | Dependência e custo para o cliente |
| V2 | Lógica de calendário em Power Query M dentro do .pbix | Lógica de negócio presa no relatório |

---

## 6. Arquitetura proposta

### 6.1 Stack open source

```
Excel (raw + outros)
       │
       ▼
Python ETL (pandas)        ← único processador, modularizado
       │
       ├── data/silver/    ← intermediários persistidos (novo)
       │
       ▼
data/gold/ (Parquet)
       │
       ▼
    DuckDB                 ← banco analítico zero-config, lê Parquet nativamente
       │
       ▼
    Metabase               ← visualização open source, amigável para não-técnicos
```

### 6.2 Por que DuckDB?

- Lê arquivos Parquet diretamente, sem ETL adicional
- SQL completo, zero configuração de servidor
- Rodas local junto com o ETL
- Suportado nativamente pelo Metabase via driver JDBC

### 6.3 Por que Metabase?

O Metabase é a alternativa open source mais indicada para o perfil do cliente:

| Critério | Metabase |
|---|---|
| Interface visual | ✅ Menus e filtros, sem SQL obrigatório |
| Compartilhamento | ✅ Link direto, sem instalar nada |
| Alertas | ✅ E-mail quando métrica ultrapassa limite |
| Custo | ✅ Gratuito na Community Edition |
| Hospedagem | ✅ Docker local ou servidor simples |
| Curva de aprendizado | ✅ Mais baixa do mercado open source |

Comparativo entre opções open source:

| Ferramenta | Facilidade | Ideal para |
|---|---|---|
| **Metabase** | ⭐⭐⭐⭐⭐ | Usuários de negócio — **recomendado** |
| Apache Superset | ⭐⭐⭐ | Analistas técnicos |
| Redash | ⭐⭐⭐ | Times que preferem escrever SQL |
| Evidence.dev | ⭐⭐ | Devs (Markdown + SQL) |
| Grafana | ⭐⭐ | Métricas operacionais em tempo real |

---

## 7. Refatoração do ETL

### 7.1 Estrutura de pastas proposta

```
CRM_Analytics/
├── data/
│   ├── raw/                      # Excels do CRM — entrada, não modificar
│   ├── outros/                   # Excels complementares — entrada, não modificar
│   ├── silver/                   # Intermediários persistidos por entidade
│   └── gold/                     # Star schema final — Parquets para consumo
│
├── etl/
│   ├── config.py                 # Caminhos, constantes, parâmetros globais
│   ├── utils.py                  # normalizar_texto(), adicionar_vendedor_loja()
│   ├── extract/
│   │   ├── __init__.py
│   │   ├── leads.py              # Lê e valida Leads.xlsx
│   │   ├── vendas.py             # Lê e valida Vendas_YYYY.xlsx (todos os anos)
│   │   ├── canais.py             # Lê e valida dados_canais_YYYY.xlsx
│   │   ├── agendamentos.py       # Lê e valida controleagendamentos.xlsx
│   │   ├── veiculos.py           # Lê gerencial_estoque + gerencial_estoque_marca
│   │   ├── comissoes.py          # Lê Vendas_comissao_YYYY.xlsx (todos os anos)
│   │   └── dimensoes_base.py     # Lê usuarios, hist_vendedor_loja, metas, de_para
│   │
│   ├── transform/
│   │   ├── __init__.py
│   │   ├── dim_veiculos.py       # Merge estoque + marca → dim_veiculos com Marca
│   │   ├── dim_data.py           # dim_data completa (trimestre, dias úteis, etc.)
│   │   ├── dim_canal.py
│   │   ├── dim_vendedores.py
│   │   ├── dim_lojas.py
│   │   ├── fato_leads.py
│   │   ├── fato_vendas.py        # Inclui join com comissoes → comissao, impostos, lucro
│   │   ├── fato_agendamentos.py
│   │   └── fato_metas.py
│   │
│   ├── load.py                   # Salva Parquets em gold/ + cria/atualiza DuckDB
│   ├── validate.py               # Validações de schema e diagnóstico pós-carga
│   └── run.py                    # Entry point: chama extract → transform → load → validate
│
├── tests/
│   ├── test_utils.py
│   ├── test_dim_veiculos.py
│   └── test_fato_vendas.py
│
└── requirements.txt
```

### 7.2 Mudanças-chave no ETL

#### `dim_veiculos` — adicionando Marca

```
Estratégia de enriquecimento:
1. Lê gerencial_estoque.xlsx          → base sem Marca
2. Lê gerencial_estoque_marca.xlsx    → join por Código → preenche Marca
3. Lê Vendas_Marca_YYYY.xlsx (todos os anos)
   → para veículos não encontrados no passo 2 (históricos),
     busca Marca pelo Código da venda
4. Veículos ainda sem Marca → valor "desconhecida"
```

Colunas resultantes em `dim_veiculos`:

| Coluna | Fonte |
|---|---|
| `id_veiculo` | `gerencial_estoque.Codigo` |
| `marca` | `gerencial_estoque_marca.Marca` ou `Vendas_Marca.Marca` |
| `modelo` | `gerencial_estoque.Modelo` |
| `ano` | `gerencial_estoque.Ano` |
| `cor` | `gerencial_estoque.Cor` |
| `tipo` | `gerencial_estoque.Tipo` |
| `placa` | `gerencial_estoque.Placa` |
| `situacao` | `gerencial_estoque.Situação` |

#### `fato_vendas` — adicionando Comissão e métricas financeiras

```
Estratégia:
1. Lê Vendas_comissao_YYYY.xlsx para todos os anos (2022–2026)
2. Concat em um único DataFrame
3. Seleciona colunas: Código, Comissão, Impostos, Retorno
4. Join com fato_vendas por id_venda = Código
5. Valores não encontrados → NaN (nenhuma linha descartada)
```

Colunas adicionadas em `fato_vendas`:

| Coluna | Fonte | Descrição |
|---|---|---|
| `comissao` | `Vendas_comissao.Comissão` | Comissão paga ao vendedor |
| `impostos` | `Vendas_comissao.Impostos` | Impostos incidentes na operação |
| `retorno` | `Vendas_comissao.Retorno` | Retorno financeiro bruto |

#### `dim_data` — campos completos no ETL

Campos a gerar em Python (não mais no Power BI):

| Campo | Descrição |
|---|---|
| `id_data` | YYYYMMDD (chave inteira) |
| `data` | Date |
| `ano` | Inteiro |
| `mes` | Inteiro |
| `ano_mes` | YYYYMM |
| `nome_mes` | "Janeiro" etc. |
| `ano_mes_desc` | "2025-01" |
| `trimestre` | 1, 2, 3 ou 4 |
| `semestre` | 1 ou 2 |
| `dia_semana` | "Segunda" etc. |
| `fim_de_semana` | 0 ou 1 |
| `dias_uteis_mes` | Count de dias úteis no mês |

---

## 8. Modelo estrela final (após refatoração)

```
                         dim_data
                            │
dim_canal ──── fato_leads ──┼── dim_vendedores ── dim_lojas
                    │       │
               dim_estagio  │

dim_canal ──── fato_vendas ─┼── dim_vendedores ── dim_lojas
                    │       │
               dim_veiculos │   (agora com Marca)
               (+ comissão, impostos, lucro, retorno)

         fato_agendamentos ─┼── dim_vendedores ── dim_lojas
                    │       │
                dim_canal   │

         fato_meta_vendedor ── dim_vendedores
         fato_meta_loja     ── dim_lojas
```

---

## 9. Métricas de negócio esperadas nos dashboards

### Funil de conversão
- Taxa de conversão Lead → Agendamento
- Taxa de conversão Agendamento → Venda
- Taxa de conversão Lead → Venda (direta)
- Motivos de perda mais frequentes por canal e por loja

### Performance comercial
- Vendas realizadas vs. meta por vendedor e por loja
- Ticket médio por loja / canal / vendedor / marca
- Margem bruta (`valor_venda − valor_compra − custos`)
- Margem líquida real (`lucro` da comissão)
- Comissão total paga por período
- Desconto médio concedido

### Leads e canais
- Volume de leads por canal ao longo do tempo
- Tempo médio lead → venda
- Custo por conversão por canal (quando disponível)

### Estoque e veículos
- Veículos mais vendidos por marca, modelo, cor, tipo
- Participação de mercado por marca
- Giro médio do estoque por marca/tipo

---

## 10. Roadmap

### Fase 1 — Integração dos dados faltantes (prioridade alta)
**Objetivo:** fechar as lacunas mais críticas do modelo atual sem mudar a estrutura geral.

- [ ] Enriquecer `dim_veiculos` com coluna `marca` (cruzar `gerencial_estoque_marca` + `Vendas_Marca_YYYY`)
- [ ] Adicionar `comissao`, `impostos`, `retorno` em `fato_vendas` (cruzar `Vendas_comissao_YYYY`)
- [ ] Completar `dim_data` com trimestre, semestre, dia da semana, fim de semana, dias úteis

### Fase 2 — Refatoração do ETL (prioridade média)
**Objetivo:** tornar o código escalável, testável e fácil de evoluir.

- [ ] Separar `transform.py` nos módulos propostos (extract / transform / load / validate)
- [ ] Implementar `validate.py` com checagens de schema nos Excels de entrada
- [ ] Escrever testes unitários para `normalizar_texto()` e `adicionar_vendedor_loja()`
- [ ] Criar `run.py` como entry point único do pipeline
- [ ] Persistir camada silver (dados limpos por entidade, antes dos joins)

### Fase 3 — Migração da visualização (prioridade média)
**Objetivo:** substituir Power BI por Metabase sem perda de análises.

- [ ] Instalar Metabase via Docker
- [ ] Conectar ao DuckDB apontando para `data/gold/`
- [ ] Replicar os dashboards existentes do Power BI no Metabase
- [ ] Treinar o cliente no uso básico do Metabase

### Fase 4 — Orquestração (prioridade baixa)
**Objetivo:** eliminar a necessidade de execução manual do ETL.

- [ ] Configurar execução automática via cron (simples) ou Prefect (robusto)
- [ ] Adicionar notificação por e-mail em caso de falha no pipeline

---

## 11. Dependências técnicas

| Componente | Ferramenta | Versão mínima |
|---|---|---|
| Linguagem | Python | 3.11+ |
| Processamento | pandas, numpy | conforme `requirements.txt` |
| Banco analítico | DuckDB | 0.10+ |
| Visualização | Metabase CE | 0.49+ |
| Runtime BI | Docker | 24+ (para Metabase) |
| Dados de entrada | Microsoft Excel (.xlsx) | — |

---

## 12. Regras de negócio críticas (não quebrar)

1. **Resolução histórica de loja**: cada evento (lead, agendamento, venda) deve refletir a loja do vendedor *na data do evento*, não a loja atual. Implementado via `adicionar_vendedor_loja()`.

2. **Vendedor/loja desconhecido = −1**: nenhuma linha deve ser descartada por falta de match. Linhas sem correspondência recebem `id_vendedor = −1` e `id_loja = −1`.

3. **De/Para antes de qualquer join**: a padronização de nomes de canal e vendedor deve ocorrer antes dos joins para evitar multiplicidade de registros.

4. **`dim_vendedor_periodo` é apenas para auditoria**: esta tabela não deve ser usada como bridge em relacionamentos M:M na camada de visualização. O `id_loja` já vem resolvido em cada fato.

5. **Chave de veículo**: `id_veiculo = Código` — a mesma chave aparece em `Vendas_*.xlsx`, `Vendas_Marca_*.xlsx`, `Vendas_comissao_*.xlsx` e `gerencial_estoque*.xlsx`. Todos os joins de veículo devem usar este campo.
