# Sprint 2: Fact Table

## Goal

Implement the central `fact_job_posting` table with all dimension keys, measures, and flags.

## Prerequisites

- [ ] Sprint 1 completed (all dimensions available)
- [ ] All dimension keys validated

---

## Task Overview

| Task | Description |
|------|-------------|
| 2.1 | Create staging models (Spectrum sources) |
| 2.2 | Implement fact_job_posting with incremental logic |
| 2.3 | Map all 37 dimension keys |
| 2.4 | Calculate measures and scores |
| 2.5 | Set boolean flags |
| 2.6 | Add data quality tests |

---

### 2.1 Staging Models (Spectrum Sources)

**models/staging/stg_linkedin.sql:**
```sql
{{ config(materialized='ephemeral') }}

SELECT
    job_posting_id,
    source_system,
    url,
    scraped_at,
    company_name,
    company_id,
    job_title,
    job_seniority_level,
    job_function,
    job_employment_type,
    job_industries,
    job_location,
    country_code,
    job_posted_datetime,
    application_availability,
    apply_link,
    job_num_applicants,
    salary_min,
    salary_max,
    salary_currency,
    salary_period,
    job_summary,
    job_description_text,
    skills_canonical,
    skills_families
FROM {{ source('silver', 'linkedin') }}
{% if is_incremental() %}
WHERE ingestion_timestamp > (SELECT max(dbt_updated_at) FROM {{ this }})
{% endif %}
```

**models/staging/stg_ai_enrichment.sql:**
```sql
{{ config(materialized='ephemeral') }}

SELECT
    job_posting_id,
    -- Pass 1: Extraction
    ext_salary_min,
    ext_salary_max,
    ext_salary_disclosed,
    ext_hourly_rate_min,
    ext_hourly_rate_max,
    ext_daily_rate_min,
    ext_daily_rate_max,
    ext_years_experience_min,
    ext_years_experience_max,
    ext_education_level,
    ext_work_model_stated,
    ext_contract_type,
    ext_pay_type,
    ext_visa_sponsorship_stated,
    ext_security_clearance_stated,
    ext_equity_mentioned,
    ext_learning_budget_mentioned,
    ext_conference_budget_mentioned,
    ext_llm_genai_mentioned,
    ext_feature_store_mentioned,
    ext_pto_policy,
    ext_start_date,
    ext_geo_restriction_type,
    ext_contract_duration_months,
    ext_extension_possible,
    ext_conversion_to_fte,
    ext_must_have_hard_skills,
    ext_nice_to_have_hard_skills,
    ext_must_have_soft_skills,
    ext_nice_to_have_soft_skills,
    ext_certifications_mentioned,
    ext_benefits_mentioned,
    -- Pass 2: Inference
    inf_job_family,
    inf_seniority_level,
    inf_primary_cloud,
    inf_leadership_expectation,
    inf_orchestrator_category,
    inf_storage_layer,
    inf_processing_paradigm,
    inf_remote_restriction,
    inf_timezone_focus,
    inf_growth_path_clarity,
    inf_requirement_strictness,
    inf_benefits_level,
    inf_h1b_friendly,
    inf_opt_cpt_friendly,
    inf_skill_inflation_detected,
    inf_mentorship_signals,
    inf_promotion_path_mentioned,
    -- Pass 3: Analysis
    anl_data_maturity_level,
    anl_data_maturity_score,
    anl_role_clarity,
    anl_manager_level_inferred,
    anl_team_growth_velocity,
    anl_reporting_structure,
    anl_ai_integration_level,
    anl_company_stage_inferred,
    anl_team_size_signals,
    anl_role_creation_type,
    anl_hiring_urgency,
    anl_competition_level,
    anl_scope_creep_score,
    anl_overtime_risk_score,
    anl_work_life_balance_score,
    anl_growth_opportunities_score,
    anl_tech_culture_score,
    anl_innovation_signals,
    anl_recommendation_score,
    anl_overall_red_flag_score,
    anl_tech_culture_signals,
    anl_strengths,
    anl_concerns,
    anl_best_fit_for,
    anl_red_flags_to_probe,
    anl_negotiation_leverage
FROM {{ source('silver', 'ai_enrichment') }}
{% if is_incremental() %}
WHERE ingestion_timestamp > (SELECT max(dbt_updated_at) FROM {{ this }})
{% endif %}
```

---

### 2.2 Fact Table: fact_job_posting

**models/facts/fact_job_posting.sql:**
```sql
{{ config(
    materialized='incremental',
    unique_key='job_posting_id',
    incremental_strategy='delete+insert',
    incremental_predicates=[
        "DBT_INTERNAL_DEST.posted_at >= (SELECT MIN(posted_at) FROM DBT_INTERNAL_SOURCE)"
    ],
    sort='posted_at',
    dist='company_key'
) }}

WITH linkedin AS (
    SELECT * FROM {{ ref('stg_linkedin') }}
),

ai AS (
    SELECT * FROM {{ ref('stg_ai_enrichment') }}
),

companies AS (
    SELECT * FROM {{ ref('stg_linkedin_companies') }}
),

-- Dimension lookups
dim_date AS (SELECT * FROM {{ ref('dim_date') }}),
dim_time AS (SELECT * FROM {{ ref('dim_time') }}),
dim_company AS (SELECT * FROM {{ ref('dim_company') }} WHERE is_current = true),
dim_location AS (SELECT * FROM {{ ref('dim_location') }}),
dim_seniority AS (SELECT * FROM {{ ref('dim_seniority') }}),
dim_job_family AS (SELECT * FROM {{ ref('dim_job_family') }}),
dim_work_model AS (SELECT * FROM {{ ref('dim_work_model') }}),
dim_employment_type AS (SELECT * FROM {{ ref('dim_employment_type') }}),
dim_contract_type AS (SELECT * FROM {{ ref('dim_contract_type') }}),
dim_cloud_platform AS (SELECT * FROM {{ ref('dim_cloud_platform') }}),
dim_education AS (SELECT * FROM {{ ref('dim_education') }}),
dim_visa_status AS (SELECT * FROM {{ ref('dim_visa_status') }}),
-- ... more dimension CTEs

joined AS (
    SELECT
        -- Surrogate key
        {{ surrogate_key(['l.job_posting_id', 'l.source_system']) }} as job_posting_key,

        -- Date/Time keys
        CAST(TO_CHAR(l.job_posted_datetime, 'YYYYMMDD') AS INT) as date_key,
        CAST(TO_CHAR(l.job_posted_datetime, 'HH24') AS INT) as time_key,

        -- Dimension keys (with COALESCE for unknown)
        COALESCE(dc.company_key, -1) as company_key,
        COALESCE(dl.location_key, -1) as location_key,
        COALESCE(ds.seniority_key, -1) as seniority_key,
        COALESCE(djf.job_family_key, -1) as job_family_key,
        COALESCE(dwm.work_model_key, -1) as work_model_key,
        COALESCE(det.employment_type_key, -1) as employment_type_key,
        COALESCE(dct.contract_type_key, -1) as contract_type_key,
        COALESCE(dcp.cloud_platform_key, -1) as cloud_platform_key,
        COALESCE(de.education_key, -1) as education_key,
        COALESCE(dvs.visa_status_key, -1) as visa_status_key,
        -- ... more dimension keys

        -- Natural keys
        l.job_posting_id,
        l.source_system,

        -- Measures - Compensation
        COALESCE(l.job_num_applicants, 0) as num_applicants,
        COALESCE(ai.ext_salary_min, l.salary_min) as salary_min_usd,
        COALESCE(ai.ext_salary_max, l.salary_max) as salary_max_usd,
        (COALESCE(ai.ext_salary_min, l.salary_min) + COALESCE(ai.ext_salary_max, l.salary_max)) / 2 as salary_avg_usd,
        ai.ext_hourly_rate_min as hourly_rate_min_usd,
        ai.ext_hourly_rate_max as hourly_rate_max_usd,
        ai.ext_daily_rate_min as daily_rate_min_usd,
        ai.ext_daily_rate_max as daily_rate_max_usd,

        -- Measures - Experience & Skills
        ai.ext_years_experience_min as years_experience_min,
        ai.ext_years_experience_max as years_experience_max,
        ARRAY_SIZE(l.skills_canonical) as skills_count,
        ARRAY_SIZE(ai.ext_must_have_hard_skills) as required_hard_skills_count,
        ARRAY_SIZE(ai.ext_nice_to_have_hard_skills) as nice_to_have_hard_skills_count,
        ARRAY_SIZE(ai.ext_must_have_soft_skills) as required_soft_skills_count,
        ARRAY_SIZE(ai.ext_nice_to_have_soft_skills) as nice_to_have_soft_skills_count,
        ARRAY_SIZE(ai.ext_certifications_mentioned) as certifications_count,

        -- Measures - Contract
        ai.ext_contract_duration_months as contract_duration_months,

        -- Measures - Scores (Pass 3)
        ai.anl_data_maturity_score as data_maturity_score,
        ai.anl_scope_creep_score as scope_creep_score,
        ai.anl_overtime_risk_score as overtime_risk_score,
        ai.anl_work_life_balance_score as work_life_balance_score,
        ai.anl_growth_opportunities_score as growth_opportunities_score,
        ai.anl_tech_culture_score as tech_culture_score,
        ai.anl_innovation_signals as innovation_score,
        ai.anl_recommendation_score as recommendation_score,
        ai.anl_overall_red_flag_score as overall_risk_score,

        -- Flags - Compensation
        COALESCE(ai.ext_salary_disclosed, false) as has_salary_info,
        ai.ext_hourly_rate_min IS NOT NULL as has_hourly_rate,
        ai.ext_daily_rate_min IS NOT NULL as has_daily_rate,
        COALESCE(ai.ext_equity_mentioned, false) as equity_offered,

        -- Flags - Work Authorization
        COALESCE(ai.ext_visa_sponsorship_stated, false) as visa_sponsorship_available,
        COALESCE(ai.inf_h1b_friendly, false) as h1b_friendly,
        COALESCE(ai.inf_opt_cpt_friendly, false) as opt_cpt_friendly,
        LOWER(ai.ext_work_model_stated) = 'remote' as is_remote,

        -- Flags - Contract
        COALESCE(ai.ext_extension_possible, false) as extension_possible,
        COALESCE(ai.ext_conversion_to_fte, false) as conversion_to_fte,

        -- Flags - Tech Stack
        COALESCE(ai.ext_llm_genai_mentioned, false) as genai_mentioned,
        COALESCE(ai.ext_llm_genai_mentioned, false) as llm_genai_mentioned,
        COALESCE(ai.ext_feature_store_mentioned, false) as feature_store_mentioned,

        -- Flags - Culture & Benefits
        COALESCE(ai.ext_learning_budget_mentioned, false) as learning_budget_mentioned,
        COALESCE(ai.ext_conference_budget_mentioned, false) as conference_budget_mentioned,
        COALESCE(ai.inf_mentorship_signals, false) as mentorship_available,
        COALESCE(ai.inf_promotion_path_mentioned, false) as promotion_path_mentioned,
        ARRAY_CONTAINS('open_source'::variant, ai.anl_tech_culture_signals) as open_source_contributor,
        ARRAY_CONTAINS('tech_blog'::variant, ai.anl_tech_culture_signals) as tech_blog_present,
        ARRAY_CONTAINS('hackathons'::variant, ai.anl_tech_culture_signals) as hackathons_mentioned,

        -- Flags - Red Flags
        COALESCE(ai.inf_skill_inflation_detected, false) as skill_inflation_detected,
        ai.anl_scope_creep_score > 0.5 as scope_creep_detected,
        ai.anl_overtime_risk_score > 0.5 as overtime_likely,

        -- Degenerate Dimensions
        l.job_title as job_title_original,
        l.url as job_url,
        l.salary_currency as salary_currency_original,
        l.salary_period as salary_period_original,

        -- Metadata
        l.job_posted_datetime as posted_at,
        CURRENT_TIMESTAMP as dbt_updated_at

    FROM linkedin l
    LEFT JOIN ai ON l.job_posting_id = ai.job_posting_id
    LEFT JOIN dim_company dc ON l.company_id = dc.company_id
    LEFT JOIN dim_location dl ON l.job_location = dl.city || ', ' || dl.state_province
    LEFT JOIN dim_seniority ds ON LOWER(l.job_seniority_level) = LOWER(ds.seniority_level)
    LEFT JOIN dim_job_family djf ON ai.inf_job_family = djf.job_family_name
    LEFT JOIN dim_work_model dwm ON ai.ext_work_model_stated = dwm.work_model_name
    LEFT JOIN dim_employment_type det ON l.job_employment_type = det.employment_type_name
    LEFT JOIN dim_contract_type dct ON ai.ext_contract_type = dct.contract_type_name
    LEFT JOIN dim_cloud_platform dcp ON ai.inf_primary_cloud = dcp.cloud_platform_name
    LEFT JOIN dim_education de ON ai.ext_education_level = de.education_level
    LEFT JOIN dim_visa_status dvs ON (
        ai.ext_visa_sponsorship_stated = dvs.h1b_friendly
        AND ai.inf_h1b_friendly = dvs.h1b_friendly
    )
    -- ... more dimension joins
)

SELECT * FROM joined
```

---

### 2.3 Data Quality Tests

**models/facts/schema.yml:**
```yaml
version: 2

models:
  - name: fact_job_posting
    description: Central fact table for job postings
    columns:
      - name: job_posting_key
        description: Surrogate key
        tests:
          - unique
          - not_null

      - name: job_posting_id
        description: Natural key from LinkedIn
        tests:
          - not_null

      - name: date_key
        description: FK to dim_date
        tests:
          - not_null
          - relationships:
              to: ref('dim_date')
              field: date_key

      - name: company_key
        description: FK to dim_company
        tests:
          - not_null

      - name: salary_min_usd
        tests:
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 10000000

      - name: recommendation_score
        tests:
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 1
```

---

## Acceptance Criteria

- [ ] fact_job_posting loads successfully
- [ ] All 37 dimension keys populated (or -1 for unknown)
- [ ] Incremental logic tested with sample data
- [ ] All measures calculate correctly
- [ ] All flags populate correctly
- [ ] Data quality tests pass
- [ ] No duplicate job_posting_id

---

## Row Count Expectations

| Metric | Expected |
|--------|----------|
| Initial load | ~28,000-50,000 rows |
| Per 4-hour increment | ~200-500 rows |
| Dimension key match rate | >95% |
| Null salary_min_usd | ~60% (many jobs don't disclose) |
