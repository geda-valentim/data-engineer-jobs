# Sprint 1: Dimension Tables

## Goal

Implement all 55 dimension tables: static seeds, dynamic dimensions (SCD2), and skill snowflake.

## Prerequisites

- [ ] Sprint 0 completed (infrastructure up)
- [ ] `dbt debug` passes in Lambda

---

## Task Groups

### 1.1 Static Seed Dimensions (Pre-populated)

These are CSV files loaded as dbt seeds.

| Seed | Rows | Source |
|------|------|--------|
| dim_date | ~3,650 | 2020-2030 |
| dim_time | 24 or 1440 | Hours or minutes |
| dim_seniority | 10 | Static mapping |
| dim_job_family | 12 | Static mapping |
| dim_work_model | 5 | Static mapping |
| dim_employment_type | 6 | Static mapping |
| dim_contract_type | 5 | Static mapping |
| dim_cloud_platform | 7 | Static mapping |

**seeds/dim_date.csv** (example):
```csv
date_key,full_date,year,quarter,month,month_name,week_of_year,day_of_month,day_of_week,day_name,is_weekend
20200101,2020-01-01,2020,1,1,January,1,1,3,Wednesday,false
...
```

**Generate with Python:**
```python
import pandas as pd
from datetime import datetime, timedelta

dates = pd.date_range('2020-01-01', '2030-12-31')
df = pd.DataFrame({
    'date_key': dates.strftime('%Y%m%d').astype(int),
    'full_date': dates,
    'year': dates.year,
    'quarter': dates.quarter,
    'month': dates.month,
    'month_name': dates.strftime('%B'),
    'week_of_year': dates.isocalendar().week,
    'day_of_month': dates.day,
    'day_of_week': dates.dayofweek + 1,
    'day_name': dates.strftime('%A'),
    'is_weekend': dates.dayofweek >= 5
})
df.to_csv('seeds/dim_date.csv', index=False)
```

---

### 1.2 Pass 1 Extraction Dimensions (Static)

| Dimension | Source | Values |
|-----------|--------|--------|
| dim_education | SLV-AI.ext_education_level | High School, Bootcamp, Associates, Bachelors, Masters, PhD, Not Mentioned |
| dim_pay_type | SLV-AI.ext_pay_type | Annual Salary, Hourly Rate, Daily Rate, Project-Based, Mixed, Not Disclosed |
| dim_start_urgency | SLV-AI.ext_start_date | Immediate, Within 2 Weeks, Within Month, Flexible, Specific Date, Not Mentioned |
| dim_geo_restriction | SLV-AI.ext_geo_restriction_type | US Only, EU Only, Specific Countries, LATAM, Global, Not Mentioned |
| dim_pto_policy | SLV-AI.ext_pto_policy | Unlimited, Generous, Standard, Limited, Not Mentioned |
| dim_security_clearance | SLV-AI.ext_security_clearance_stated | Required, Preferred, Not Mentioned |

**seeds/dim_education.csv:**
```csv
education_key,education_level,education_order,typical_years
1,High School,1,0
2,Bootcamp,2,0
3,Associates,3,2
4,Bachelors,4,4
5,Masters,5,6
6,PhD,6,10
7,Not Mentioned,0,
```

---

### 1.3 Pass 2 Inference Dimensions (Static)

| Dimension | Source | Key Values |
|-----------|--------|------------|
| dim_visa_status | SLV-AI.ext_visa_sponsorship_stated | Will Sponsor, H1B Only, Must Be Authorized, US Citizen Only, etc. |
| dim_leadership | SLV-AI.inf_leadership_expectation | Individual Contributor, Tech Lead, Architect, People Manager, etc. |
| dim_orchestrator | SLV-AI.inf_orchestrator_category | Airflow-like, Spark Native, dbt Core, Cloud Native, etc. |
| dim_storage_layer | SLV-AI.inf_storage_layer | Data Warehouse, Data Lake, Lakehouse, Mixed, On-Premises |
| dim_processing_paradigm | SLV-AI.inf_processing_paradigm | Batch Only, Streaming Only, Hybrid, Micro-batch |
| dim_remote_restriction | SLV-AI.inf_remote_restriction | Same Country, Same Timezone, Anywhere, Not Mentioned |
| dim_timezone | SLV-AI.inf_timezone_focus | Americas, Europe, APAC, Global, Not Mentioned |
| dim_growth_clarity | SLV-AI.inf_growth_path_clarity | Explicit, Implied, Vague, Not Mentioned |
| dim_requirement_strictness | SLV-AI.inf_requirement_strictness | Low, Medium, High, Not Mentioned |
| dim_benefits_level | SLV-AI.inf_benefits_level | Comprehensive, Standard, Basic, Not Mentioned |

---

### 1.4 Pass 3 Analysis Dimensions (Static)

| Dimension | Source | Key Values |
|-----------|--------|------------|
| dim_maturity_level | SLV-AI.anl_data_maturity_level | Ad-Hoc, Developing, Defined, Managed, Optimizing |
| dim_role_clarity | SLV-AI.anl_role_clarity | Clear, Vague, Multi-Role, Not Mentioned |
| dim_manager_level | SLV-AI.anl_manager_level_inferred | Director+, Senior Manager, Manager, Tech Lead |
| dim_team_velocity | SLV-AI.anl_team_growth_velocity | Rapid Expansion, Steady Growth, Stable |
| dim_reporting_structure | SLV-AI.anl_reporting_structure | Reports to CTO, Director of Data, Manager, Tech Lead |
| dim_ai_integration | SLV-AI.anl_ai_integration_level | None, Basic ML, Advanced ML, MLOps, GenAI Focus |
| dim_company_stage | SLV-AI.anl_company_stage_inferred | Startup Seed, Series A/B, Growth, Established, Enterprise |
| dim_team_size | SLV-AI.anl_team_size_signals | Solo, Small (2-5), Medium (6-15), Large (16-50), Very Large |
| dim_hiring_context | SLV-AI.anl_role_creation_type | New Headcount, Backfill, Team Expansion, New Function |
| dim_hiring_urgency | SLV-AI.anl_hiring_urgency | Immediate, ASAP, Normal, Pipeline |
| dim_competition | SLV-AI.anl_competition_level | Low, Medium, High, Very High |

---

### 1.5 Skill Snowflake Dimensions (Static)

**Hierarchy:** `dim_skill_type → dim_skill_category → dim_skill_family → dim_skill`

**seeds/dim_skill_type.csv:**
```csv
skill_type_key,skill_type_name,description
1,HARD,Technical teachable measurable skills
2,SOFT,Interpersonal behavioral transferable skills
3,HYBRID,Both technical and interpersonal
```

**seeds/dim_skill_category.csv:**
```csv
skill_category_key,category_name,skill_type,description
1,Programming Languages,HARD,Python Java Scala SQL
2,Cloud Platforms,HARD,AWS Azure GCP services
3,Databases,HARD,PostgreSQL MongoDB Redis
4,Data Processing,HARD,Spark Kafka Flink
5,Orchestration,HARD,Airflow Dagster Prefect
6,DevOps & Infrastructure,HARD,Docker Kubernetes Terraform
7,BI & Visualization,HARD,Tableau Looker Power BI
8,ML & AI,HARD,TensorFlow PyTorch MLflow
9,Data Modeling,HARD,dbt Star Schema Data Vault
10,Communication,SOFT,Verbal written presentation
11,Leadership,SOFT,Team management mentoring
12,Problem Solving,SOFT,Analytical thinking debugging
13,Collaboration,SOFT,Teamwork cross-functional
14,Self-Management,SOFT,Time management organization
15,Business Acumen,SOFT,Stakeholder management domain knowledge
16,Technical Communication,HYBRID,Documentation tech writing
17,Technical Leadership,HYBRID,Architecture decisions code review
```

---

### 1.6 Dynamic Dimension: dim_company (SCD Type 2)

**models/dimensions/dim_company.sql:**
```sql
{{ config(
    materialized='incremental',
    unique_key='company_key',
    incremental_strategy='merge',
    merge_update_columns=['effective_end_date', 'is_current']
) }}

WITH source AS (
    SELECT
        company_id,
        name as company_name,
        website_domain,
        headquarters,
        country_code as headquarters_country,
        industries[0] as industry_primary,
        organization_type,
        company_size,
        founded_year,
        followers as linkedin_followers,
        employees_on_linkedin as linkedin_employees,
        funding_last_round_type as funding_stage,
        CASE WHEN funding_amount IS NOT NULL THEN true ELSE false END as has_funding_info,
        snapshot_date,
        md5(concat_ws('|',
            name, website_domain, headquarters, industries[0],
            organization_type, company_size, funding_last_round_type
        )) as row_hash
    FROM {{ source('silver', 'linkedin_companies') }}
    {% if is_incremental() %}
    WHERE snapshot_date > (SELECT max(effective_start_date) FROM {{ this }})
    {% endif %}
),

-- SCD2 logic: detect changes
current_records AS (
    SELECT * FROM {{ this }}
    WHERE is_current = true
),

changed AS (
    SELECT s.*
    FROM source s
    LEFT JOIN current_records c ON s.company_id = c.company_id
    WHERE c.company_id IS NULL OR s.row_hash != c.row_hash
)

SELECT
    {{ surrogate_key(['company_id', 'snapshot_date']) }} as company_key,
    company_id,
    company_name,
    website_domain,
    headquarters as headquarters_city,
    headquarters_country,
    industry_primary,
    organization_type,
    -- Parse company_size bucket
    CASE
        WHEN company_size LIKE '%1-10%' THEN 'Startup'
        WHEN company_size LIKE '%11-50%' THEN 'SMB'
        WHEN company_size LIKE '%51-200%' THEN 'SMB'
        WHEN company_size LIKE '%201-500%' THEN 'Mid-Market'
        WHEN company_size LIKE '%501-1000%' THEN 'Mid-Market'
        WHEN company_size LIKE '%1001-5000%' THEN 'Enterprise'
        ELSE 'Enterprise'
    END as company_size_bucket,
    founded_year,
    linkedin_followers,
    linkedin_employees,
    funding_stage,
    has_funding_info,
    snapshot_date as effective_start_date,
    '9999-12-31'::date as effective_end_date,
    true as is_current
FROM changed
```

---

### 1.7 Dynamic Dimension: dim_location

**models/dimensions/dim_location.sql:**
```sql
{{ config(materialized='table') }}

WITH locations AS (
    SELECT DISTINCT
        job_location,
        country_code
    FROM {{ source('silver', 'linkedin') }}
    WHERE job_location IS NOT NULL
)

SELECT
    {{ surrogate_key(['job_location', 'country_code']) }} as location_key,
    -- Parse city from job_location
    SPLIT_PART(job_location, ',', 1) as city,
    CASE
        WHEN country_code = 'US' THEN TRIM(SPLIT_PART(job_location, ',', 2))
        ELSE NULL
    END as state_province,
    country_code,
    CASE country_code
        WHEN 'US' THEN 'United States'
        WHEN 'GB' THEN 'United Kingdom'
        WHEN 'CA' THEN 'Canada'
        WHEN 'DE' THEN 'Germany'
        -- Add more mappings
        ELSE country_code
    END as country_name,
    CASE
        WHEN country_code IN ('US', 'CA', 'MX') THEN 'North America'
        WHEN country_code IN ('GB', 'DE', 'FR', 'NL', 'ES', 'IT') THEN 'Europe'
        WHEN country_code IN ('IN', 'SG', 'AU', 'JP', 'CN') THEN 'APAC'
        WHEN country_code IN ('BR', 'AR', 'CL', 'CO') THEN 'LATAM'
        ELSE 'Other'
    END as region,
    CASE
        WHEN LOWER(job_location) LIKE '%remote%' THEN true
        ELSE false
    END as is_remote_location
FROM locations
```

---

### 1.8 Dynamic Dimension: dim_skill

**models/dimensions/dim_skill.sql:**
```sql
{{ config(materialized='table') }}

WITH all_skills AS (
    -- Hard skills from canonical
    SELECT DISTINCT
        skill as skill_canonical_name,
        'HARD' as skill_type
    FROM {{ source('silver', 'linkedin') }},
    LATERAL FLATTEN(input => skills_canonical) s(skill)

    UNION

    -- Soft skills from AI extraction
    SELECT DISTINCT
        skill as skill_canonical_name,
        'SOFT' as skill_type
    FROM {{ source('silver', 'ai_enrichment') }},
    LATERAL FLATTEN(input => ext_must_have_soft_skills) s(skill)
),

categorized AS (
    SELECT
        skill_canonical_name,
        skill_type,
        -- Map to category based on known patterns
        CASE
            WHEN skill_canonical_name IN ('Python', 'Java', 'Scala', 'SQL', 'Go', 'Rust') THEN 1
            WHEN skill_canonical_name IN ('AWS', 'Azure', 'GCP', 'S3', 'Redshift') THEN 2
            WHEN skill_canonical_name IN ('PostgreSQL', 'MySQL', 'MongoDB', 'Redis') THEN 3
            WHEN skill_canonical_name IN ('Spark', 'Kafka', 'Flink', 'Kinesis') THEN 4
            WHEN skill_canonical_name IN ('Airflow', 'Dagster', 'Prefect', 'Luigi') THEN 5
            WHEN skill_canonical_name IN ('Docker', 'Kubernetes', 'Terraform') THEN 6
            WHEN skill_canonical_name IN ('Tableau', 'Looker', 'Power BI', 'Metabase') THEN 7
            WHEN skill_canonical_name IN ('TensorFlow', 'PyTorch', 'MLflow', 'SageMaker') THEN 8
            WHEN skill_canonical_name IN ('dbt', 'Data Modeling', 'Star Schema') THEN 9
            -- Soft skills
            WHEN skill_type = 'SOFT' AND skill_canonical_name ILIKE '%communicat%' THEN 10
            WHEN skill_type = 'SOFT' AND skill_canonical_name ILIKE '%leader%' THEN 11
            ELSE NULL
        END as skill_category_key
    FROM all_skills
)

SELECT
    {{ surrogate_key(['skill_canonical_name']) }} as skill_key,
    skill_canonical_name,
    INITCAP(skill_canonical_name) as skill_display_name,
    CASE skill_type
        WHEN 'HARD' THEN 1
        WHEN 'SOFT' THEN 2
        WHEN 'HYBRID' THEN 3
    END as skill_type_key,
    skill_category_key,
    skill_type,
    false as is_emerging,
    skill_type = 'HARD' as is_technical
FROM categorized
```

---

### 1.9 Bridge Support Dimensions (Static Seeds)

| Seed | Description |
|------|-------------|
| dim_certification | AWS, GCP, Azure, Databricks certs |
| dim_ml_tool | SageMaker, MLflow, Feast, etc. |
| dim_benefit | Health, 401k, equity, PTO, etc. |
| dim_us_state | All 50 US states |
| dim_strength_category | Job strengths (modern stack, remote, etc.) |
| dim_concern_category | Job concerns (overtime, vague, etc.) |
| dim_best_fit_category | Best fit profiles |
| dim_probe_category | Interview questions to ask |
| dim_leverage_category | Negotiation leverage points |

---

## Acceptance Criteria

- [ ] All 31 static seed CSVs created and loaded
- [ ] `dbt seed` completes successfully
- [ ] dim_company SCD2 logic tested with sample updates
- [ ] dim_location parses all unique locations
- [ ] dim_skill categorizes skills correctly
- [ ] All dimension tables queryable in Redshift

---

## Deliverables

```
dbt_gold/
├── seeds/
│   ├── dim_date.csv
│   ├── dim_time.csv
│   ├── dim_seniority.csv
│   ├── dim_job_family.csv
│   ├── ... (31 seed files)
└── models/dimensions/
    ├── dim_company.sql
    ├── dim_location.sql
    └── dim_skill.sql
```
