# Silver Layer Schema: `jobs_postings`

## Overview
Tabela dimensional de vagas de emprego normalizada e enriquecida da camada Bronze.

## Table Schema

### Primary Key & Identification
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `job_posting_id` | STRING | NOT NULL | Business key única da vaga (PK) |
| `source_system` | STRING | NOT NULL | Sistema de origem (ex: "linkedin", "indeed") |
| `source_url` | STRING | NULL | URL original da vaga na fonte |
| `ingestion_timestamp` | TIMESTAMP | NOT NULL | Timestamp de ingestão do Bronze |

### Company Information
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `company_name` | STRING | NOT NULL | Nome da empresa |
| `company_id` | STRING | NULL | ID da empresa no sistema de origem |
| `company_url` | STRING | NULL | URL do perfil da empresa |

### Job Core Attributes
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `job_title` | STRING | NOT NULL | Título da vaga |
| `job_seniority_level` | STRING | NULL | Nível de senioridade (Junior, Mid, Senior, Lead, etc) |
| `job_function` | STRING | NULL | Área funcional (Engineering, Sales, Marketing, etc) |
| `job_employment_type` | STRING | NULL | Tipo de contrato (Full-time, Part-time, Contract, etc) |
| `job_industries` | ARRAY<STRING> | NULL | Indústrias relacionadas |

### Location
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `job_location` | STRING | NULL | Localização em texto livre |
| `country_code` | STRING | NULL | Código ISO 3166-1 alpha-2 do país (ex: "BR", "US") |
| `city` | STRING | NULL | Cidade extraída/normalizada |
| `state` | STRING | NULL | Estado/província |
| `is_remote` | BOOLEAN | NULL | Flag se a vaga é remota |

### Posting Dates
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `job_posted_at` | TIMESTAMP | NULL | Data/hora de publicação da vaga |
| `job_posted_date` | DATE | NULL | Data de publicação (sem hora) |

### Application Information
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `application_available` | BOOLEAN | NULL | Se é possível aplicar |
| `apply_link` | STRING | NULL | Link para aplicação |
| `num_applicants` | INTEGER | NULL | Número de candidatos |

### Compensation
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `salary_min` | DECIMAL(12,2) | NULL | Salário mínimo |
| `salary_max` | DECIMAL(12,2) | NULL | Salário máximo |
| `salary_currency` | STRING | NULL | Moeda (ISO 4217: "BRL", "USD", etc) |
| `salary_period` | STRING | NULL | Período (hourly, monthly, yearly) |

### Job Poster
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `poster_name` | STRING | NULL | Nome do recrutador/poster |
| `poster_title` | STRING | NULL | Cargo do poster |
| `poster_profile_url` | STRING | NULL | URL do perfil do poster |

### Job Description & Content
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `job_summary` | STRING | NULL | Resumo/snippet da vaga |
| `job_description_html` | STRING | NULL | Descrição completa em HTML |
| `job_description_text` | STRING | NULL | Descrição em texto plano (para NLP/ATS) |

### Metadata & Audit
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `created_at` | TIMESTAMP | NOT NULL | Timestamp de criação do registro Silver |
| `updated_at` | TIMESTAMP | NOT NULL | Timestamp da última atualização |
| `data_quality_score` | DECIMAL(3,2) | NULL | Score de qualidade dos dados (0.00-1.00) |
| `is_duplicate` | BOOLEAN | NOT NULL | Flag se é duplicata identificada |

---

## Partitioning Strategy

### Hive-style Partitioning
```
year=YYYY/month=MM/day=DD/hour=HH
```

- **Partition Keys**: `year`, `month`, `day`, `hour`
- **Based on**: `ingestion_timestamp` (quando o dado foi coletado)
- **Granularity**: Hourly
- **Format**: `s3://bucket/silver/jobs_postings/year=2025/month=12/day=03/hour=14/`

### Clustering (optional for query optimization)
- Primary: `source_system`
- Secondary: `country_code`, `job_posted_date`

---

## Data Quality Rules

1. **NOT NULL Constraints**: `job_posting_id`, `source_system`, `ingestion_timestamp`, `company_name`, `job_title`
2. **Deduplication**: Based on (`job_posting_id`, `source_system`)
3. **Date Validation**: `job_posted_at` <= `ingestion_timestamp`
4. **Salary Validation**: `salary_min` <= `salary_max` (when both present)
5. **Country Code**: Must match ISO 3166-1 alpha-2 if present

---

## SCD Type

**Type 1 (Overwrite)**: Sempre sobrescreve com os dados mais recentes. Não mantém histórico de mudanças.

Para tracking de mudanças, consultar a camada Bronze com `ingestion_timestamp`.

---

## Storage Format

- **Format**: Parquet
- **Compression**: Snappy
- **Estimated Size**: ~500 bytes/row (compressed)
- **Retention**: 2 years in S3 Standard, then Glacier

---

## Indexes & Performance

### Recommended Indexes (if using database)
- Primary: `job_posting_id`
- Secondary: `(source_system, job_posted_date)`
- Full-text: `job_description_text`, `job_title`

### Query Optimization
- Partition pruning on date ranges
- Predicate pushdown on `source_system`, `country_code`
