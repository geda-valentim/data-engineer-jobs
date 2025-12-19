# Gold Layer - Data Strategy & Volume Analysis

## Overview

This document defines the data strategy for the Gold Layer, considering:
- **Source**: Silver layer only (Parquet in S3 via Redshift Spectrum)
- **Target**: Redshift Serverless (Gold tables)
- **Use Case**: Website queries + Analytics dashboard
- **Refresh**: Every 4 hours

---

## Current Data Volume

> **Analysis Date**: 2025-12-19

### Bronze Layer (Raw Data)

| Dataset | Files | Size | Notes |
|---------|-------|------|-------|
| `linkedin/` (jobs) | 1,273 | 674 MB | JSON partitioned by date |
| `linkedin_companies/` | 9,491 | 395 MB | 1 snapshot per company |
| `ai_enrichment/` | 21,160 | 144 MB | Bedrock enrichment output |
| **Total** | **31,924** | **~1.2 GB** | |

### Silver Layer (Source for Gold)

| Dataset | Records | Size | Partitioning |
|---------|---------|------|--------------|
| `linkedin/` (jobs) | ~53,000 | 328 MB | `year/month/day/hour` |
| `linkedin_companies/` | ~9,500 | ~8 MB | `bucket` (hash) |
| `ai_enrichment/` | ~21,000 | ~30 MB | `year/month/day` |
| **Total** | | **~366 MB** | |

---

## Raw Ingestion Data

### Jobs (Bronze linkedin/)

```
Date            Files    Size (MB)   Notes
------------------------------------------
2025-11-17          2          9.3   Initial test
2025-11-27          5          0.0
2025-11-28          1          0.0
2025-11-29          2          0.0
2025-11-30          1          0.0
2025-12-01          1          0.0
2025-12-02         10          1.3
2025-12-03        114         46.7   ┐
2025-12-04        382        139.8   ├─ BACKFILL (histórico)
2025-12-05        176        286.1   ┘
2025-12-06         46         10.0   ┐
2025-12-07         19          7.4   │
2025-12-08         47         16.9   │
2025-12-09         44         16.8   │
2025-12-10         46         19.8   │
2025-12-11         31         14.9   │
2025-12-12         45         16.3   ├─ STEADY STATE
2025-12-13         47          7.3   │  (~40-50 files/dia)
2025-12-14         45          6.0   │
2025-12-15         46         14.8   │
2025-12-16         48         16.2   │
2025-12-17         44         18.9   │
2025-12-18         47         17.8   │
2025-12-19         24          7.6   ┘  Partial day
------------------------------------------
TOTAL            1273        674.0 MB
```

### Companies (Bronze linkedin_companies/)

```
Date          Companies   Notes
--------------------------------
2025-12-08      2,148     ┐ BACKFILL
2025-12-09      4,861     ┘ (companies from backfilled jobs)
2025-12-10        332     ┐
2025-12-11        211     │
2025-12-12        238     │
2025-12-13         66     │ Weekend
2025-12-14         49     │ Weekend
2025-12-15        230     ├─ STEADY STATE
2025-12-16        302     │  (~200-350/dia weekday)
2025-12-17        361     │
2025-12-18        346     │
2025-12-19        347     ┘
--------------------------------
TOTAL           9,491     Unique companies
```

### AI Enrichment (Bronze ai_enrichment/)

```
Date            Files    Size (MB)
----------------------------------
2025-12-16          6          0.0   <- Pipeline start
2025-12-17       2842         19.0
2025-12-18      18312        124.4   <- Bulk processing
----------------------------------
TOTAL           21160        143.5 MB
```

---

## Ingestion Pattern Summary

### Steady-State (post-backfill, Dec 6+)

| Period | Job Files | Jobs (est.) | Companies |
|--------|-----------|-------------|-----------|
| Weekday (per day) | 40-50 files | ~1,000-1,500 | 200-350 |
| Weekend (per day) | 19-47 files | ~400-800 | 50-100 |
| **Per 4-hour window** | **~8 files** | **~200-300** | **~40-60** |

> **Note**: Each job file contains multiple job postings. Estimate ~25-30 jobs per file based on Silver record counts.

### Growth Projection

| Timeframe | Cumulative Jobs | Cumulative Size |
|-----------|-----------------|-----------------|
| Current | 53K | 366 MB |
| 1 month | 80K | 550 MB |
| 6 months | 200K | 1.4 GB |
| 1 year | 400K | 2.8 GB |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              S3 (Silver)                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │    linkedin/    │  │linkedin_companies│  │  ai_enrichment/ │         │
│  │   (Parquet)     │  │   (Parquet)      │  │   (Parquet)     │         │
│  └────────┬────────┘  └────────┬─────────┘  └────────┬────────┘         │
└───────────┼────────────────────┼─────────────────────┼──────────────────┘
            │                    │                     │
            ▼                    ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Redshift Spectrum (External Schema)                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │  ext_linkedin   │  │  ext_companies  │  │ext_ai_enrichment│         │
│  │   (external)    │  │   (external)    │  │   (external)    │         │
│  └────────┬────────┘  └────────┬─────────┘  └────────┬────────┘         │
└───────────┼────────────────────┼─────────────────────┼──────────────────┘
            │                    │                     │
            ▼                    ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Redshift Serverless (Gold Schema)                   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         DIMENSIONS                               │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │   │
│  │  │dim_company│ │dim_skill │ │dim_date  │ │dim_*     │           │   │
│  │  │(9.5K rows)│ │(dynamic) │ │ (seed)   │ │(seeds)   │           │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      FACT + BRIDGES                              │   │
│  │  ┌────────────────┐  ┌────────────────┐                         │   │
│  │  │fact_job_posting│  │  bridge_*      │                         │   │
│  │  │  (53K+ rows)   │  │ (16 bridges)   │                         │   │
│  │  └────────────────┘  └────────────────┘                         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      AGGREGATIONS                                │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │   │
│  │  │agg_salary│ │agg_demand│ │agg_skills│ │agg_*     │           │   │
│  │  │ (views)  │ │ (views)  │ │ (views)  │ │(8 total) │           │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Website / API                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │   Job Search    │  │  Company Page   │  │ Analytics Dash  │         │
│  │  (fact + dims)  │  │ (dim_company)   │  │ (aggregations)  │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Refresh Strategy

### Schedule: Every 4 Hours

```
00:00 → 04:00 → 08:00 → 12:00 → 16:00 → 20:00
```

### Table Categories

#### 1. SEEDS (One-time load)

Static reference data loaded once at deployment.

| Table | Rows | Strategy | When |
|-------|------|----------|------|
| `dim_date` | 3,650 | Seed | Deploy |
| `dim_time` | 1,440 | Seed | Deploy |
| `dim_seniority_level` | 6 | Seed | Deploy |
| `dim_remote_type` | 4 | Seed | Deploy |
| `dim_employment_type` | 5 | Seed | Deploy |
| `dim_contract_type` | 4 | Seed | Deploy |
| ... (47 more seeds) | | Seed | Deploy |

**Total Seeds**: 51 tables

#### 2. INCREMENTAL (Every 4 hours)

New records appended or merged based on natural key.

| Table | Current Rows | New per 4h | Strategy | Key |
|-------|--------------|------------|----------|-----|
| `fact_job_posting` | 53,000 | ~300-600 | APPEND | `job_id` |
| `bridge_job_skills` | ~150,000 | ~1,000 | APPEND | `job_id, skill_id` |
| `bridge_job_*` (15 more) | varies | ~2,000 total | APPEND | composite |
| `dim_skill` | ~2,000 | ~5-10 new | MERGE | `skill_name` |
| `dim_ai_*` (27 tables) | varies | ~10-20 new | MERGE | natural key |

**Incremental Logic** (dbt):
```sql
-- fact_job_posting (incremental)
{{
  config(
    materialized='incremental',
    unique_key='job_id',
    incremental_strategy='append'
  )
}}

SELECT ...
FROM {{ source('silver', 'linkedin') }}
{% if is_incremental() %}
WHERE ingestion_timestamp > (SELECT MAX(ingestion_timestamp) FROM {{ this }})
{% endif %}
```

#### 3. FULL REFRESH (Every 4 hours)

Small tables where full refresh is simpler and faster than incremental.

| Table | Rows | Refresh Time | Reason |
|-------|------|--------------|--------|
| `dim_company` | 9,500 | ~10 sec | Critical for job queries, frequent updates |
| `dim_location` | ~200 | ~1 sec | Low cardinality, frequent new cities |

**Why Full Refresh for Companies?**
- Companies are **denormalized** in job queries (need latest info)
- Website shows company details alongside jobs
- ~9.5K rows refreshes in seconds
- Avoids complex SCD (Slowly Changing Dimension) logic

#### 4. VIEWS (Real-time from base tables)

Aggregations computed on-demand or as materialized views.

| View | Base Tables | Strategy |
|------|-------------|----------|
| `agg_salary_by_location` | fact, dim_location | VIEW |
| `agg_salary_by_seniority` | fact, dim_seniority | VIEW |
| `agg_demand_by_skill` | bridge_skills, dim_skill | VIEW |
| `agg_demand_by_location` | fact, dim_location | VIEW |
| `agg_skills_trending` | bridge_skills, dim_date | MATERIALIZED VIEW |
| ... (8 total) | | |

**Materialized View** for expensive aggregations:
```sql
CREATE MATERIALIZED VIEW agg_skills_trending AS
SELECT
  s.skill_name,
  d.year_month,
  COUNT(*) as job_count,
  COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY d.year_month) as pct
FROM fact_job_posting f
JOIN bridge_job_skills bs ON f.job_sk = bs.job_sk
JOIN dim_skill s ON bs.skill_sk = s.skill_sk
JOIN dim_date d ON f.posted_date_sk = d.date_sk
GROUP BY s.skill_name, d.year_month;

-- Refresh every 4h with dbt run
```

---

## 4-Hour Pipeline Execution

### Step Functions Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    dbt-gold-pipeline (4h)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1: Seeds Check                                            │
│  └─► dbt run --select tag:seed (if not exists)                  │
│      Time: ~30 sec (first run only)                             │
│                                                                 │
│  Step 2: Full Refresh Dimensions                                │
│  └─► dbt run --select dim_company dim_location --full-refresh   │
│      Time: ~15 sec                                              │
│                                                                 │
│  Step 3: Incremental Dimensions                                 │
│  └─► dbt run --select tag:dim_incremental                       │
│      Time: ~30 sec                                              │
│                                                                 │
│  Step 4: Fact Table                                             │
│  └─► dbt run --select fact_job_posting                          │
│      Time: ~1 min                                               │
│                                                                 │
│  Step 5: Bridge Tables                                          │
│  └─► dbt run --select tag:bridge                                │
│      Time: ~1 min                                               │
│                                                                 │
│  Step 6: Materialized Views                                     │
│  └─► REFRESH MATERIALIZED VIEW agg_*                            │
│      Time: ~2 min                                               │
│                                                                 │
│  Step 7: Tests                                                  │
│  └─► dbt test --select tag:critical                             │
│      Time: ~30 sec                                              │
│                                                                 │
│  Total: ~5-6 minutes                                            │
└─────────────────────────────────────────────────────────────────┘
```

### Execution Timeline

| Step | Duration | Cumulative |
|------|----------|------------|
| Seeds (if needed) | 30 sec | 0:30 |
| dim_company + dim_location | 15 sec | 0:45 |
| Incremental dimensions | 30 sec | 1:15 |
| fact_job_posting | 60 sec | 2:15 |
| 16 bridge tables | 60 sec | 3:15 |
| Materialized views | 120 sec | 5:15 |
| Critical tests | 30 sec | 5:45 |
| **Total** | | **~6 min** |

---

## Website Query Patterns

### Job Search (Primary Use Case)

```sql
-- User searches for "Data Engineer" jobs in "São Paulo"
SELECT
  f.job_id,
  f.job_title,
  f.salary_min_usd,
  f.salary_max_usd,
  c.company_name,
  c.company_logo_url,
  c.industry,
  c.employee_count,
  l.city,
  l.country
FROM fact_job_posting f
JOIN dim_company c ON f.company_sk = c.company_sk
JOIN dim_location l ON f.location_sk = l.location_sk
WHERE f.job_title ILIKE '%data engineer%'
  AND l.city = 'São Paulo'
  AND f.is_active = true
ORDER BY f.posted_at DESC
LIMIT 20;
```

**Performance**:
- `dim_company` is denormalized → no joins to external tables
- `fact_job_posting` has `SORTKEY(posted_at)` for recency queries
- `DISTKEY(company_sk)` for company-centric queries

### Company Page

```sql
-- Show company details + active jobs count
SELECT
  c.*,
  COUNT(f.job_id) as active_jobs
FROM dim_company c
LEFT JOIN fact_job_posting f ON c.company_sk = f.company_sk AND f.is_active = true
WHERE c.company_id = '123456'
GROUP BY c.company_sk;
```

### Analytics Dashboard

```sql
-- Salary trends by seniority (from materialized view)
SELECT * FROM agg_salary_by_seniority
WHERE year_month >= '2024-01';

-- Top skills in demand (from materialized view)
SELECT * FROM agg_skills_trending
WHERE year_month = '2024-12'
ORDER BY job_count DESC
LIMIT 20;
```

---

## Data Freshness SLA

| Component | Max Staleness | Rationale |
|-----------|---------------|-----------|
| Job listings | 4 hours | New jobs appear within 4h |
| Company info | 4 hours | Logo, description updates |
| Skills | 4 hours | New skills from AI extraction |
| Aggregations | 4 hours | Dashboard reflects recent data |
| Salary stats | 4 hours | Market analysis accuracy |

### Freshness Monitoring

```yaml
# dbt source freshness
sources:
  - name: silver
    freshness:
      warn_after: {count: 4, period: hour}
      error_after: {count: 6, period: hour}
    tables:
      - name: linkedin
        loaded_at_field: ingestion_timestamp
      - name: linkedin_companies
        loaded_at_field: snapshot_date
```

---

## Cost Estimate (4-hour refresh)

### Compute

| Component | Usage | Monthly Cost |
|-----------|-------|--------------|
| Redshift Serverless | 6 runs × 6 min × 8 RPU × 30 days | ~$15-25 |
| Lambda (dbt runner) | 180 invocations/month | ~$1 |
| Step Functions | 180 executions/month | ~$0.50 |

### Storage

| Component | Size | Monthly Cost |
|-----------|------|--------------|
| Redshift storage | ~500 MB (growing) | ~$5 |
| S3 (Silver - Spectrum) | ~400 MB | ~$0.01 |

### Networking

| Component | Monthly Cost |
|-----------|--------------|
| VPC Endpoints | ~$7 |
| Data transfer | ~$1 |

### Total

| Category | Monthly |
|----------|---------|
| Compute | ~$17-27 |
| Storage | ~$5 |
| Network | ~$8 |
| **Total** | **~$30-40** |

---

## Redshift Table Design

### Distribution & Sort Keys

```sql
-- fact_job_posting
CREATE TABLE gold.fact_job_posting (
  job_sk BIGINT IDENTITY(1,1),
  job_id VARCHAR(50) NOT NULL,
  ...
  posted_at TIMESTAMP,
  company_sk BIGINT,
  ...
)
DISTSTYLE KEY
DISTKEY (company_sk)  -- Optimize company joins
SORTKEY (posted_at);  -- Optimize recency queries

-- dim_company (replicated for fast joins)
CREATE TABLE gold.dim_company (
  company_sk BIGINT IDENTITY(1,1),
  company_id VARCHAR(50) NOT NULL,
  company_name VARCHAR(255),
  ...
)
DISTSTYLE ALL;  -- Replicate to all nodes for fast joins
```

### Indexing Strategy

Redshift uses zone maps (automatic) + sort keys:

| Table | Sort Key | Reason |
|-------|----------|--------|
| `fact_job_posting` | `posted_at` | Filter by date range |
| `dim_company` | `company_name` | Alphabetical browse |
| `bridge_job_skills` | `job_sk` | Join performance |

---

## Summary

| Aspect | Decision |
|--------|----------|
| **Refresh frequency** | Every 4 hours |
| **dim_company strategy** | Full refresh (critical for website) |
| **fact_job_posting** | Incremental append |
| **Aggregations** | Materialized views, refreshed with dbt |
| **Seeds** | 51 tables, loaded once |
| **Pipeline duration** | ~6 minutes |
| **Monthly cost** | ~$30-40 |
| **Data freshness SLA** | 4 hours max staleness |
