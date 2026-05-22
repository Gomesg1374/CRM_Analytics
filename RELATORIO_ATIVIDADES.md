# Relatório de Atividades — Projeto CRM Analytics

**Analista:** Gildo Gao  
**Data:** Maio de 2026  
**Área:** Dados e Inteligência Comercial

---

## 1. Contexto

A empresa opera uma rede de concessionárias de veículos com múltiplas lojas. O CRM utilizado (Pipedrive) armazena os dados de leads, atendimentos e conversões, mas não possui integração nativa com o sistema interno de vendas e controle de estoque. Os dados de comissão, custo de aquisição do veículo, marca e outros indicadores financeiros residem em sistemas separados.

Antes da construção deste projeto, toda a consolidação e análise desses dados era feita manualmente pelo analista, semana a semana, com risco elevado de inconsistências e sem rastreabilidade.

---

## 2. Processo Manual — Como era feito antes da automação

### 2.1 Download e coleta dos arquivos

A cada ciclo de análise (semanal ou mensal), as seguintes exportações precisavam ser feitas manualmente:

| Arquivo | Sistema de origem | Frequência de download |
|---|---|---|
| `Leads.xlsx` | CRM Pipedrive (exportação completa) | Semanal |
| `Vendas_YYYY.xlsx` | Sistema interno de vendas | Mensal (um arquivo por ano) |
| `dados_canais_YYYY.xlsx` | Sistema interno | Mensal |
| `gerencial_estoque.xlsx` | Sistema de gestão de estoque | Semanal |
| `Vendas_comissao_YYYY.xlsx` | Planilha financeira da empresa | Mensal |
| `Vendas_Marca_YYYY.xlsx` | Planilha financeira da empresa | Mensal |

Cada download exigia login em sistemas diferentes, aplicação de filtros específicos e salvamento local. O processo completo levava entre **2 e 4 horas** por ciclo.

### 2.2 Conferência e limpeza manual dos arquivos

Após o download, cada arquivo era aberto no Excel para conferência:

- **Leads:** Verificação de campos em branco, datas inválidas e registros duplicados. Leads com o campo "Conversão" incorreto (ex: lead convertido registrado como perdido) eram corrigidos manualmente.
- **Vendas:** Conferência do código do veículo (`Código`) em cada arquivo anual para garantir consistência entre os anos.
- **Canais:** Verificação de novos canais não mapeados (ex: uma nova campanha com nome diferente das anteriores).
- **Estoque:** Conferência de veículos sem marca definida — pesquisa manual para preenchimento.

### 2.3 Cruzamento manual de dados entre planilhas

O passo mais trabalhoso era consolidar as informações de fontes diferentes:

- **Vendedor × Loja × Data:** Cada venda precisava ser associada à loja correta do vendedor **na data da venda**, não à loja atual. Vendedores que trocaram de loja ao longo do tempo exigiam verificação manual do histórico.
- **Lead → Venda:** Cruzamento manual entre registros de leads e vendas para calcular taxa de conversão.
- **Agendamentos → Leads:** Identificação manual de qual agendamento correspondia a qual lead.
- **Comissão → Venda:** Junção manual entre a planilha financeira de comissões e os registros de venda.

Esse processo consumia entre **4 e 8 horas adicionais** por ciclo e era altamente suscetível a erros humanos.

---

## 3. Tabelas de Referência Construídas Manualmente

Para que a automação funcionasse com qualidade, foi necessário construir e manter seis tabelas de referência que não existiam nos sistemas originais. Cada uma representa um trabalho de curadoria específico:

### 3.1 `usuarios.xlsx` — Cadastro de Vendedores

**Localização:** `data/raw/usuarios.xlsx`  
**Registros:** 29 vendedores

Tabela com o cadastro completo de todos os vendedores que atuaram nas lojas desde 2022. Não havia nenhum cadastro centralizado disponível — os dados foram levantados consultando registros históricos de RH, contracheques e registros do CRM.

| Campo | Descrição |
|---|---|
| `id_usuario` | Identificador único do vendedor |
| `nome_usuario` | Nome completo padronizado |
| `data_admissao` | Data de entrada na empresa |
| `data_demissao` | Data de saída (em branco se ainda ativo) |
| `status` | Ativo / Inativo |

**Trabalho envolvido:** Identificação de todos os vendedores históricos, consulta a registros de RH para datas exatas, padronização dos nomes conforme grafias mais comuns.

---

### 3.2 `hist_vendedor_loja.xlsx` — Histórico de Lotação

**Localização:** `data/raw/hist_vendedor_loja.xlsx`  
**Registros:** 31 períodos

Uma das tabelas mais críticas do projeto. Documenta em qual loja cada vendedor trabalhava em cada período de tempo. Sem ela, seria impossível atribuir corretamente as vendas e leads à loja certa quando um vendedor mudou de unidade.

| Campo | Descrição |
|---|---|
| `id_vendedor` | FK para `usuarios` |
| `id_loja` | FK para a loja |
| `loja` | Nome da loja |
| `data_inicio` | Início do período nessa loja |
| `data_fim` | Fim do período (em branco se ainda ativo) |

**Trabalho envolvido:** Levantamento junto à gestão de todas as transferências de vendedores entre lojas desde 2022, com datas exatas. Alguns casos exigiram pesquisa em e-mails e registros físicos.

---

### 3.3 `de_para_canais.xlsx` — Padronização de Canais

**Localização:** `data/raw/de_para_canais.xlsx`  
**Registros:** 17 mapeamentos

O CRM e o sistema interno de vendas registravam o mesmo canal de diferentes formas. Por exemplo: "VISITA A LOJA", "Porta / Loja" e "PORTA (LOJA)" eram o mesmo canal, digitado de formas diferentes por usuários distintos ao longo do tempo.

| Campo | Descrição |
|---|---|
| `canal_origem` | Nome exatamente como aparece nos dados brutos |
| `canal_padrao` | Nome padronizado usado no modelo |

**Exemplos de mapeamento:**

| De (canal_origem) | Para (canal_padrao) |
|---|---|
| VISITA A LOJA | PORTA (LOJA) |
| POR TELEFONE | PORTA (LOJA) |
| INDICAÇÃO CLIENTE | INDICACAO CLIENTE ALTOMANI |
| INTERNET | PESQUISA GOOGLE |
| MERCADO LIVRE | MERCADOLIVRE |

**Trabalho envolvido:** Análise de todos os valores únicos de canal em cada fonte de dados, decisão sobre o agrupamento correto com a gestão comercial, e manutenção contínua sempre que um novo canal aparecia.

---

### 3.4 `de_para_vendedores.xlsx` — Padronização de Nomes de Vendedores

**Localização:** `data/raw/de_para_vendedores.xlsx`  
**Registros:** 27 mapeamentos

O nome do mesmo vendedor aparecia grafado de formas diferentes em cada sistema: CRM, sistema de vendas e planilha de comissões. Sem essa tabela, a junção entre os sistemas resultaria em vendas e leads não atribuídos ao vendedor correto.

| Campo | Descrição |
|---|---|
| `nome_origem` | Nome exatamente como aparece nos dados brutos |
| `nome_padrao` | Nome padronizado (mesma grafia de `usuarios.xlsx`) |

**Exemplos de mapeamento:**

| De (nome_origem) | Para (nome_padrao) |
|---|---|
| DANILO DE OLIVEIRA C... | Danilo Oliveira Colamego |
| LUIS MAXIMIANO DA SI... | Luis Maximiano |
| BRUNO DENADAI CAJARA... | Bruno Denadai Cajarana |
| MARCELO ALTOMANI | Marcelo Altomani |

**Trabalho envolvido:** Comparação linha a linha dos nomes em cada fonte de dados, identificação de todos os vendedores que apareciam com grafia diferente, e padronização com base no cadastro de `usuarios.xlsx`.

---

### 3.5 `controleagendamentos.xlsx` — Controle de Agendamentos

**Localização:** `data/raw/controleagendamentos.xlsx`  
**Registros:** 254 agendamentos

O CRM não registrava agendamentos de visita à concessionária de forma estruturada. Para analisar a efetividade do processo de agendamento (taxa de comparecimento, conversão pós-visita, canal de origem), foi necessário criar e manter manualmente essa planilha de controle.

| Campo | Descrição |
|---|---|
| `Id` | Identificador do lead no CRM |
| `Cliente` | Nome do cliente |
| `Canal` | Canal de origem do lead |
| `Responsavel_agendamento` | Quem realizou o agendamento (SDR) |
| `criacao_agendamento` | Data/hora em que o agendamento foi feito |
| `Agendado_para` | Data/hora da visita agendada |
| `Flag_agendamento` | Sim/Não — o agendamento foi confirmado? |
| `Flag_visita` | Sim/Não — o cliente compareceu? |
| `Responsavel` | Vendedor responsável pelo atendimento na visita |
| `Status` | Resultado final (Ganho, Perdido, etc.) |
| `Motivo` | Motivo de perda (quando aplicável) |
| `id_venda` | FK para a venda gerada (quando aplicável) |

**Trabalho envolvido:** Preenchimento manual a cada agendamento realizado, acompanhamento diário do status de cada visita, e atualização do resultado após o atendimento.

---

### 3.6 `acerto_leads.xlsx` — Correções Pontuais de Leads

**Localização:** `data/outros/acerto_leads.xlsx`  
**Registros:** variável (atualmente 18)

O CRM nem sempre registrava as conversões corretamente. Em alguns casos, leads que foram convertidos em venda permaneciam com status "Em aberto" ou "Perdido" no sistema, por falha no preenchimento no momento do fechamento. Esse arquivo contém as correções identificadas e validadas pelo analista.

| Campo | Descrição |
|---|---|
| `Id` | Identificador do lead no CRM (chave de substituição) |
| Demais campos | Todos os dados corretos do lead (substitui a linha inteira) |

**Processo de correção:**
1. Identificação do lead com dados incorretos (via cruzamento com dados de venda ou relato do vendedor)
2. Verificação do histórico no CRM
3. Preenchimento da linha correta em `acerto_leads.xlsx`
4. Na próxima execução do ETL, a linha original é substituída automaticamente

**Trabalho envolvido:** Curadoria contínua, investigação de inconsistências entre leads e vendas, e validação com a equipe comercial.

---

## 4. Desafios Técnicos Enfrentados

| Desafio | Impacto | Solução adotada |
|---|---|---|
| Vendedores com grafias diferentes em cada sistema | Leads e vendas não associados ao vendedor correto | `de_para_vendedores.xlsx` aplicado antes de qualquer join |
| Canais com nomes inconsistentes por digitação livre | Análise de canal fragmentada em dezenas de valores | `de_para_canais.xlsx` com mapeamento completo |
| Vendedores que trocaram de loja | Atribuição incorreta de receita e leads por loja | `hist_vendedor_loja.xlsx` com períodos exatos |
| Leads convertidos não atualizados no CRM | Taxa de conversão subestimada | `acerto_leads.xlsx` com correções manuais validadas |
| Marca do veículo ausente no estoque ativo | Análise de mix de marcas incompleta | Enriquecimento em três etapas: estoque → histórico de vendas → "desconhecida" |
| Agendamentos não estruturados no CRM | Impossibilidade de medir efetividade do SDR | `controleagendamentos.xlsx` preenchido manualmente |
| CRM e sistema de vendas sem chave comum | Join impossível por ID | Uso do código do veículo (`Código`) como chave universal |

---

## 5. Solução Construída

Com base em todo o conhecimento de dados e regras de negócio levantados durante o processo manual, foi desenvolvido um pipeline ETL automatizado em Python que:

- **Extrai** automaticamente todos os arquivos Excel das pastas configuradas
- **Aplica** todos os mapeamentos De/Para e regras de negócio de forma consistente
- **Transforma** os dados em um modelo estrela com 7 dimensões e 5 tabelas fato
- **Carrega** os dados no PostgreSQL diariamente às 10h
- **Valida** automaticamente 5 critérios de qualidade a cada execução
- **Notifica** por e-mail em caso de sucesso ou falha

---

## 6. Ganhos Obtidos com a Automação

| Dimensão | Antes | Depois |
|---|---|---|
| **Tempo de atualização dos dados** | 6 a 12 horas por ciclo (manual) | ~5 minutos (automático, diário) |
| **Frequência de atualização** | Semanal ou mensal | Diária (10h automático) |
| **Risco de erro humano** | Alto — junções manuais em Excel | Mínimo — critérios automáticos de aceite |
| **Rastreabilidade** | Inexistente — sem histórico de execuções | Total — logs com timestamp por execução |
| **Consistência dos dados** | Variável — dependia de quem fez a consolidação | Garantida — mesmas regras aplicadas em todo run |
| **Visualização** | Planilhas estáticas enviadas por e-mail | Dashboards interativos no Metabase (sempre atualizados) |
| **Auditabilidade** | Impossível — arquivo final sobrescrevia o anterior | Total — Parquets silver e gold mantêm histórico |
| **Escalabilidade** | Limitada — cada nova loja ou vendedor exigia ajustes manuais | Alta — novas lojas/vendedores são adicionados nas tabelas de referência |

---

## 7. Conclusão

O projeto CRM Analytics consolidou e automatizou um trabalho analítico complexo que antes dependia inteiramente de esforço manual intensivo e conhecimento tácito do analista. As tabelas de referência construídas durante a fase manual — resultado de meses de curadoria, investigação e alinhamento com as áreas de negócio — são a espinha dorsal do modelo e garantem a qualidade dos dados entregues aos dashboards.

A automação não apenas elimina o trabalho repetitivo, mas também torna o processo auditável, reproduzível e escalável para novas lojas, vendedores ou fontes de dados que venham a ser incorporadas futuramente.
