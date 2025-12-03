# Insights do Dataset Atual - Skills de Data Engineers

## Análise do Dataset (36 vagas)

### Top Skills Identificadas

Com base na análise do arquivo parquet atual, identificamos as seguintes skills mais demandadas:

| Ranking | Skill | Frequência | Percentual | Categoria |
|---------|-------|------------|------------|-----------|
| 1 | **Azure** | 27/35 vagas | 77.1% | Cloud Platform |
| 2 | **Spark** | 26/35 vagas | 74.3% | Data Processing |
| 3 | **ETL** | 25/35 vagas | 71.4% | Practice |
| 4 | **Python** | 22/35 vagas | 62.9% | Programming Language |
| 5 | **CI/CD** | 16/35 vagas | 45.7% | DevOps Practice |
| 6 | **Databricks** | 15/35 vagas | 42.9% | Data Platform |
| 7 | **SQL** | 14/35 vagas | 40.0% | Query Language |
| 8 | **AWS** | 14/35 vagas | 40.0% | Cloud Platform |
| 9 | **GCP** | 14/35 vagas | 40.0% | Cloud Platform |
| 10 | **DevOps** | 13/35 vagas | 37.1% | Practice |

## Insights Principais

### 1. Dominância do Azure
- **77% das vagas** mencionam Azure, indicando forte demanda no ecossistema Microsoft
- Ferramentas Azure específicas:
  - Azure Data Factory: 11.4%
  - Synapse: 11.4%
  - Microsoft Fabric: 5.7% (tecnologia emergente)

### 2. Multi-Cloud é Comum
- **40% das vagas** mencionam tanto Azure quanto AWS
- **40% das vagas** mencionam GCP
- Sugestão: Profissionais com experiência multi-cloud têm vantagem

### 3. Spark é Essencial
- **74% das vagas** requerem Spark/PySpark
- Confirma que processamento distribuído é skill fundamental

### 4. Python > SQL (?)
- Python: 62.9%
- SQL: 40.0%
- **Nota**: Pode haver subdetecção de SQL (muito genérico, pode estar implícito)

### 5. DevOps/DataOps é Esperado
- CI/CD: 45.7%
- DevOps: 37.1%
- Docker: 37.1%
- Kubernetes: 8.6%

### 6. Ferramentas Modernas
- Databricks: 42.9%
- Snowflake: 31.4%
- Airflow: 34.3%
- dbt: 5.7% (crescendo)

## Recomendações para o Script

### 1. Priorizar Detecção de Cloud Skills
Dado que 77% das vagas são Azure-centric, expandir o catálogo de Azure skills:

```yaml
azure_skills:
  - Azure Data Factory (ADF)
  - Azure Synapse Analytics
  - Azure Databricks
  - Azure Data Lake Storage (ADLS)
  - Microsoft Fabric
  - Azure DevOps
  - Azure Functions
  - Azure Purview
  - Delta Lake (Azure)
```

### 2. Melhorar Detecção de SQL
SQL pode aparecer em variações:
- T-SQL (Microsoft)
- PL/SQL (Oracle)
- MySQL
- PostgreSQL
- "SQL Server"

Considerar contexto: "5+ years of SQL" vs "MySQL database"

### 3. Detectar Combinações de Skills
Clusters comuns identificados:
- **Azure Stack**: Azure + Databricks + Spark + Python
- **AWS Stack**: AWS + Glue + S3 + Python
- **Modern Data Stack**: dbt + Snowflake + Airflow

### 4. Níveis de Proficiência
Extrair quando possível:
- "5+ years of Python" → Python (Senior)
- "Familiarity with Spark" → Spark (Junior/Nice-to-have)
- "Expert in Azure" → Azure (Expert)

## Skills Ausentes/Raras (< 5%)

Estas skills não aparecem ou são muito raras no dataset atual:

- **Kafka**: Apenas indiretamente mencionado
- **Flink**: 0%
- **Presto/Trino**: 0%
- **Tableau**: 0%
- **Looker**: 0%
- **Grafana**: 0%
- **Go/Golang**: 0%
- **Rust**: 0%

**Ação**: Incluir no catálogo, mas não esperar alta detecção inicial.

## Exemplo: Vaga Típica de Data Engineer

Baseado nas frequências, uma vaga "típica" pede:

```
Título: Data Engineer (Azure/Cloud)

Skills Essenciais:
✓ Azure (77%)
✓ Spark/PySpark (74%)
✓ ETL pipelines (71%)
✓ Python (63%)

Skills Importantes:
✓ CI/CD (46%)
✓ Databricks (43%)
✓ SQL (40%)
✓ AWS ou GCP (40%)
✓ DevOps (37%)

Skills Desejáveis:
✓ Airflow (34%)
✓ Snowflake (31%)
✓ Data Governance (37%)
✓ Docker (37%)
```

## Próximo Passo: Catálogo Inicial de Skills

Com base na análise, criar arquivo `config/skills_catalog.yaml` com pelo menos:

### Categorias Prioritárias

1. **Cloud Platforms** (3 principais)
   - Azure (+ 8-10 sub-skills)
   - AWS (+ 6-8 sub-skills)
   - GCP (+ 4-6 sub-skills)

2. **Programming Languages** (4 principais)
   - Python
   - SQL (+ variações)
   - Scala
   - Java

3. **Data Processing** (6 ferramentas)
   - Spark/PySpark
   - Databricks
   - Kafka
   - Flink
   - Airflow
   - dbt

4. **Data Warehouses** (3 principais)
   - Snowflake
   - BigQuery
   - Redshift

5. **DevOps/Practices** (5 skills)
   - CI/CD
   - DevOps
   - Docker
   - Kubernetes
   - Git

### Expansão Futura

Após validar MVP, adicionar:
- Frameworks (Pandas, NumPy, etc.)
- BI Tools (Power BI, Tableau, Looker)
- Conceitos (Data Mesh, Medallion Architecture, etc.)
- Certificações (Azure DP-203, AWS Data Analytics, etc.)

## Métricas de Validação

Para o dataset atual, esperamos:

| Métrica | Target | Atual |
|---------|--------|-------|
| Cobertura | >90% | ✓ 97% (34/35 vagas com skills) |
| Diversidade | >50 skills | ✗ 26 skills (expandir catálogo) |
| Precisão | <5% falsos positivos | A validar manualmente |

## Próxima Ação

1. ✅ Análise exploratória concluída
2. ⬜ Criar `config/skills_catalog.yaml` com 100+ skills
3. ⬜ Implementar `regex_extractor.py`
4. ⬜ Testar com 5 vagas manualmente
5. ⬜ Validar precisão
6. ⬜ Processar todas as 35 vagas
7. ⬜ Gerar relatório CSV/JSON

---

**Nota**: Este documento complementa [skills_detection_plan.md](skills_detection_plan.md) com dados reais do dataset.
