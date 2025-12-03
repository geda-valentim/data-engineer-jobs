# Planejamento: Script de Detecção de Skills para Software/Data Engineers

## 1. Contexto e Objetivo

### Objetivo
Desenvolver um script Python para identificar e extrair skills técnicas de vagas de emprego para Software Engineers e Data Engineers a partir de arquivos Parquet contendo job postings.

### Dados Disponíveis
- **Fonte**: Arquivos Parquet no diretório `tmp/`
- **Registros**: 36 vagas (35 com descrições completas)
- **Formato**: Parquet (Snappy compression)

## 2. Análise dos Dados Disponíveis

### Campos Relevantes (ordenados por importância)

| Campo | Disponibilidade | Uso para Skills |
|-------|----------------|-----------------|
| `job_description_text` | 35/36 (97%) | **PRIMÁRIO** - Texto completo com skills, requisitos e responsabilidades |
| `job_summary` | 35/36 (97%) | **SECUNDÁRIO** - Resumo condensado das principais skills |
| `job_title` | 35/36 (97%) | **CONTEXTO** - Indica área (Data Engineer, Azure Engineer, etc.) |
| `job_description_html` | 35/36 (97%) | **BACKUP** - Alternativa se texto falhar |
| `job_function` | 35/36 (97%) | **FILTRO** - Para segmentar por área (Engineering, etc.) |
| `job_seniority_level` | 35/36 (97%) | **CONTEXTO** - Senior, Associate, etc. |

### Tipos de Vagas Identificadas
```
- Data Engineer (genérico)
- Azure Data Engineer
- AWS Data Engineer
- Product Owner / Data Engineer
- Denodo Data Engineer
```

## 3. Estratégias de Identificação de Skills

### 3.1. Abordagem por Categorias

Organizar skills em categorias hierárquicas:

#### A. Cloud Platforms
- **Azure**: Azure Data Factory, Synapse, Databricks, Data Lake, Fabric, Purview, DevOps
- **AWS**: S3, Redshift, Glue, EMR, Lambda, Athena
- **GCP**: BigQuery, Dataflow, Cloud Storage, Dataproc

#### B. Linguagens de Programação
- Python, SQL, Scala, Java, R, JavaScript

#### C. Ferramentas de Dados
- **ETL/Orchestration**: Airflow, dbt, Dagster, Prefect, NiFi
- **Data Processing**: Spark, Kafka, Flink, Beam
- **Databases**: PostgreSQL, MySQL, MongoDB, Cassandra, Redis
- **Data Warehouses**: Snowflake, Redshift, BigQuery, Synapse

#### D. Frameworks e Bibliotecas
- Pandas, NumPy, PySpark, Polars, Delta Lake, Iceberg

#### E. Práticas e Conceitos
- CI/CD, DevOps, Data Governance, Data Quality, Data Lineage
- Medallion Architecture, Lakehouse, Data Mesh

#### F. Ferramentas de Visualização
- Power BI, Tableau, Looker, Metabase, Grafana

#### G. Versionamento e Deploy
- Git, GitHub, GitLab, Docker, Kubernetes, Terraform

### 3.2. Técnicas de Extração

#### Opção 1: Regex Pattern Matching (Baseline)
**Prós:**
- Simples e rápido
- Não requer dependências pesadas
- Fácil de debugar

**Contras:**
- Pode gerar falsos positivos
- Limitado a skills conhecidas
- Requer manutenção manual da lista

**Implementação:**
```python
# Exemplo de padrão
skills_patterns = {
    'python': r'\b(?i)python\b',
    'sql': r'\b(?i)sql\b',
    'azure_data_factory': r'\b(?i)(azure\s+data\s+factory|ADF)\b'
}
```

#### Opção 2: Named Entity Recognition (NER) - Avançado
**Prós:**
- Identifica skills não previstas
- Mais robusto

**Contras:**
- Requer modelo treinado
- Mais complexo
- Maior overhead computacional

**Bibliotecas:**
- spaCy (com custom NER)
- transformers (BERT-based)

#### Opção 3: Híbrida (RECOMENDADO)
Combinar regex para skills conhecidas + NER para descoberta de novas skills

### 3.3. Normalização de Skills

**Problemas a resolver:**
- Variações: "Azure Data Factory", "ADF", "Data Factory"
- Case sensitivity: "SQL" vs "sql"
- Plurais e singulares: "database" vs "databases"
- Sinônimos: "machine learning" vs "ML"

**Solução:**
Criar dicionário de mapeamento:
```python
skill_mappings = {
    'azure_data_factory': ['azure data factory', 'adf', 'data factory'],
    'sql': ['sql', 't-sql', 'pl/sql', 'mysql', 'postgresql'],
    'python': ['python', 'python3', 'py']
}
```

## 4. Arquitetura do Script Proposto

### 4.1. Estrutura de Módulos

```
src/skills_detection/
├── __init__.py
├── config/
│   ├── __init__.py
│   └── skills_catalog.yaml          # Catálogo de skills por categoria
├── extractors/
│   ├── __init__.py
│   ├── base_extractor.py            # Interface base
│   ├── regex_extractor.py           # Extração por regex
│   └── ner_extractor.py             # NER (opcional, fase 2)
├── normalizers/
│   ├── __init__.py
│   └── skill_normalizer.py          # Normalização e deduplicação
├── processors/
│   ├── __init__.py
│   └── job_processor.py             # Processa cada vaga
└── main.py                           # Script principal
```

### 4.2. Fluxo de Dados

```
[Parquet Files]
    ↓
[Load Data] → DataFrame
    ↓
[For each job posting]
    ↓
[Extract Text] (job_description_text + job_summary)
    ↓
[Clean Text] (remove HTML entities, lowercase, etc.)
    ↓
[Apply Extractors] (regex patterns)
    ↓
[Normalize Skills] (map variations → canonical)
    ↓
[Categorize Skills] (cloud, language, tools, etc.)
    ↓
[Aggregate Results]
    ↓
[Output] → CSV/JSON/Parquet
```

### 4.3. Formato de Output

#### Output 1: Skills por Vaga (Detalhado)
```json
{
  "job_posting_id": "4319177210",
  "job_title": "Azure Data Engineer - MS Fabric",
  "company_name": "Gravity Infosolutions",
  "detected_skills": [
    {
      "skill": "azure_data_factory",
      "canonical_name": "Azure Data Factory",
      "category": "cloud_tools",
      "confidence": 1.0,
      "context": "...using Azure Data Factory, Synapse..."
    },
    {
      "skill": "python",
      "canonical_name": "Python",
      "category": "programming_language",
      "confidence": 0.9
    }
  ],
  "skill_count": 15,
  "seniority_level": "Associate"
}
```

#### Output 2: Ranking de Skills (Agregado)
```csv
skill_canonical,category,frequency,percentage,avg_seniority
Python,programming_language,28,80%,Mid-Level
SQL,programming_language,32,91%,Associate
Azure Data Factory,cloud_tools,18,51%,Mid-Level
Spark,data_processing,15,43%,Senior
```

#### Output 3: Matriz Vaga-Skill (para análise)
```
job_posting_id | python | sql | spark | azure | aws | ...
4319177210     |   1    |  1  |   1   |   1   |  0  | ...
4319177211     |   1    |  1  |   0   |   0   |  1  | ...
```

## 5. Catálogo de Skills (skills_catalog.yaml)

```yaml
cloud_platforms:
  azure:
    canonical: "Azure"
    variations: ["azure", "microsoft azure"]
    sub_skills:
      - canonical: "Azure Data Factory"
        variations: ["azure data factory", "adf", "data factory"]
      - canonical: "Azure Synapse"
        variations: ["synapse", "azure synapse", "synapse analytics"]
      - canonical: "Azure Databricks"
        variations: ["databricks", "azure databricks"]
      - canonical: "Microsoft Fabric"
        variations: ["fabric", "ms fabric", "microsoft fabric"]
      - canonical: "Azure Data Lake"
        variations: ["data lake", "adls", "azure data lake storage"]

  aws:
    canonical: "AWS"
    variations: ["aws", "amazon web services"]
    sub_skills:
      - canonical: "AWS S3"
        variations: ["s3", "simple storage service"]
      - canonical: "AWS Glue"
        variations: ["glue", "aws glue"]
      - canonical: "AWS Redshift"
        variations: ["redshift", "aws redshift"]

programming_languages:
  - canonical: "Python"
    variations: ["python", "python3", "py"]
  - canonical: "SQL"
    variations: ["sql", "t-sql", "pl/sql", "transact-sql"]
  - canonical: "Scala"
    variations: ["scala"]
  - canonical: "Java"
    variations: ["java"]

data_processing:
  - canonical: "Apache Spark"
    variations: ["spark", "pyspark", "apache spark"]
  - canonical: "Apache Kafka"
    variations: ["kafka", "apache kafka"]
  - canonical: "Delta Lake"
    variations: ["delta lake", "delta"]

bi_tools:
  - canonical: "Power BI"
    variations: ["power bi", "powerbi", "pbi"]
  - canonical: "Tableau"
    variations: ["tableau"]

practices:
  - canonical: "CI/CD"
    variations: ["ci/cd", "cicd", "continuous integration", "continuous deployment"]
  - canonical: "Data Governance"
    variations: ["data governance", "governance"]
  - canonical: "DevOps"
    variations: ["devops", "dev ops"]
```

## 6. Implementação Faseada

### Fase 1: MVP (Minimum Viable Product)
**Escopo:**
- Extração por regex de skills pré-definidas
- Categorias básicas (cloud, languages, tools)
- Output em CSV simples

**Entregáveis:**
- Script `extract_skills.py`
- Arquivo `skills_catalog.yaml` com 50-100 skills principais
- Output: `skills_detected.csv`

**Tempo estimado:** 1-2 dias

### Fase 2: Normalização e Análise
**Escopo:**
- Normalização avançada de variações
- Outputs múltiplos (JSON, agregações)
- Métricas de qualidade (confiança, coverage)

**Entregáveis:**
- Módulo de normalização
- Dashboard de análise (opcional)
- Relatório de skills mais demandadas

**Tempo estimado:** 2-3 dias

### Fase 3: ML/NER (Opcional)
**Escopo:**
- Identificação automática de novas skills
- Fine-tuning de modelo NER
- API para detecção online

**Entregáveis:**
- Modelo NER treinado
- API REST (FastAPI)

**Tempo estimado:** 5-7 dias

## 7. Métricas de Sucesso

### Cobertura
- **Target**: Detectar skills em >90% das vagas
- **Métrica**: `(vagas com skills / total vagas) * 100`

### Precisão
- **Target**: <5% de falsos positivos
- **Validação**: Amostragem manual de 20 vagas

### Diversidade
- **Target**: Identificar >50 skills únicas
- **Métrica**: Contagem de skills distintas

## 8. Melhorias Futuras

1. **Detecção de Contexto**: Diferenciar "required" vs "nice to have"
2. **Anos de Experiência**: Extrair "5+ years Python"
3. **Skills Relacionadas**: Identificar clusters (ex: Azure + Python + SQL)
4. **Tendências Temporais**: Analisar evolução de skills ao longo do tempo
5. **Benchmarking**: Comparar com outras fontes (Stack Overflow Survey, TIOBE Index)

## 9. Exemplo de Uso do Script

```bash
# Básico
python src/skills_detection/main.py \
  --input tmp/*.parquet \
  --output results/skills_detected.csv

# Com configuração customizada
python src/skills_detection/main.py \
  --input tmp/*.parquet \
  --config config/skills_catalog.yaml \
  --output results/ \
  --format json \
  --min-confidence 0.8

# Análise agregada
python src/skills_detection/main.py \
  --input tmp/*.parquet \
  --output results/ \
  --aggregate \
  --top-n 20
```

## 10. Dependências Necessárias

```toml
[tool.poetry.dependencies]
python = "^3.9"
pandas = "^2.0"
pyarrow = "^14.0"  # Para ler Parquet
pyyaml = "^6.0"    # Para carregar catalog
regex = "^2023.0"  # Regex avançado

# Opcionais (Fase 2/3)
spacy = { version = "^3.7", optional = true }
transformers = { version = "^4.35", optional = true }
fastapi = { version = "^0.104", optional = true }
```

## 11. Próximos Passos

1. ✅ Documentação do planejamento
2. ⬜ Criar `skills_catalog.yaml` com skills iniciais
3. ⬜ Implementar `regex_extractor.py` (MVP)
4. ⬜ Criar script `main.py` para processamento
5. ⬜ Testar com arquivo parquet atual
6. ⬜ Validar resultados manualmente
7. ⬜ Iterar e expandir catálogo de skills
8. ⬜ Gerar relatório de análise

---

**Documento criado em:** 2025-12-03
**Versão:** 1.0
**Autor:** Planejamento para detecção automática de skills em job postings
