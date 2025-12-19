# Sprint 4: Aggregations & Data Quality

## Goal

Implement 8 aggregation tables and comprehensive data quality testing.

## Prerequisites

- [ ] Sprint 3 completed (all bridges available)
- [ ] Fact and bridge data validated

---

## Aggregation Tables

| Table | Grain | Purpose |
|-------|-------|---------|
| agg_daily_job_metrics | day × seniority × job_family × country × work_model | Daily KPIs |
| agg_weekly_job_metrics | week × dimensions | Weekly trends |
| agg_monthly_job_metrics | month × dimensions | Monthly summary |
| agg_skills_demand | week × skill × seniority × job_family | Skills trending |
| agg_salary_benchmarks | month × seniority × job_family × country × work_model | Salary percentiles |
| agg_company_hiring | month × company | Company hiring velocity |
| agg_posting_time_analysis | day_of_week × hour × job_family × seniority | Best time to apply |
| agg_hourly_posting_summary | hour × timezone | Hourly distribution |

---

### 4.1 agg_daily_job_metrics

**models/aggregations/agg_daily_job_metrics.sql:**
```sql
{{ config(
    materialized='incremental',
    unique_key=['date_key', 'seniority_key', 'job_family_key', 'country_code', 'work_model_key'],
    incremental_strategy='delete+insert'
) }}

WITH fact AS (
    SELECT
        f.date_key,
        f.seniority_key,
        f.job_family_key,
        l.country_code,
        f.work_model_key,
        f.job_posting_key,
        f.num_applicants,
        f.salary_min_usd,
        f.salary_max_usd,
        f.salary_avg_usd,
        f.has_salary_info,
        f.is_remote,
        f.visa_sponsorship_available,
        f.recommendation_score
    FROM {{ ref('fact_job_posting') }} f
    JOIN {{ ref('dim_location') }} l ON f.location_key = l.location_key
    {% if is_incremental() %}
    WHERE f.dbt_updated_at > (SELECT max(dbt_updated_at) FROM {{ this }})
    {% endif %}
)

SELECT
    date_key,
    seniority_key,
    job_family_key,
    country_code,
    work_model_key,
    COUNT(DISTINCT job_posting_key) as job_count,
    SUM(CASE WHEN has_salary_info THEN 1 ELSE 0 END) as jobs_with_salary,
    SUM(CASE WHEN is_remote THEN 1 ELSE 0 END) as jobs_remote,
    SUM(CASE WHEN visa_sponsorship_available THEN 1 ELSE 0 END) as jobs_visa_sponsor,
    SUM(num_applicants) as total_applicants,
    AVG(salary_avg_usd) as salary_avg,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY salary_avg_usd) as salary_median,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY salary_avg_usd) as salary_p25,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY salary_avg_usd) as salary_p75,
    AVG(recommendation_score) as avg_recommendation_score,
    CURRENT_TIMESTAMP as dbt_updated_at
FROM fact
WHERE salary_avg_usd IS NOT NULL OR has_salary_info = false
GROUP BY 1, 2, 3, 4, 5
```

---

### 4.2 agg_skills_demand

**models/aggregations/agg_skills_demand.sql:**
```sql
{{ config(
    materialized='incremental',
    unique_key=['week_key', 'skill_key', 'seniority_key', 'job_family_key'],
    incremental_strategy='delete+insert'
) }}

WITH base AS (
    SELECT
        CAST(TO_CHAR(d.full_date, 'YYYYIW') AS INT) as week_key,
        b.skill_key,
        f.seniority_key,
        f.job_family_key,
        s.skill_canonical_name as skill_name,
        s.skill_family,
        f.job_posting_key,
        b.requirement_type,
        f.salary_avg_usd
    FROM {{ ref('bridge_job_skills') }} b
    JOIN {{ ref('fact_job_posting') }} f ON b.job_posting_key = f.job_posting_key
    JOIN {{ ref('dim_skill') }} s ON b.skill_key = s.skill_key
    JOIN {{ ref('dim_date') }} d ON f.date_key = d.date_key
    {% if is_incremental() %}
    WHERE b.dbt_updated_at > (SELECT max(dbt_updated_at) FROM {{ this }})
    {% endif %}
)

SELECT
    week_key,
    skill_key,
    seniority_key,
    job_family_key,
    MAX(skill_name) as skill_name,
    MAX(skill_family) as skill_family,
    COUNT(DISTINCT job_posting_key) as job_count,
    SUM(CASE WHEN requirement_type = 'required' THEN 1 ELSE 0 END) as required_count,
    SUM(CASE WHEN requirement_type = 'nice_to_have' THEN 1 ELSE 0 END) as nice_to_have_count,
    AVG(salary_avg_usd) as avg_salary_usd,
    ROW_NUMBER() OVER (
        PARTITION BY week_key, seniority_key, job_family_key
        ORDER BY COUNT(*) DESC
    ) as rank_overall,
    NULL::decimal as growth_rate_4w,  -- Calculated in post-processing
    CURRENT_TIMESTAMP as dbt_updated_at
FROM base
GROUP BY 1, 2, 3, 4
```

---

### 4.3 agg_salary_benchmarks

**models/aggregations/agg_salary_benchmarks.sql:**
```sql
{{ config(materialized='table') }}

WITH fact AS (
    SELECT
        CAST(TO_CHAR(d.full_date, 'YYYYMM') AS INT) as month_key,
        f.seniority_key,
        f.job_family_key,
        l.country_code,
        f.work_model_key,
        f.salary_avg_usd
    FROM {{ ref('fact_job_posting') }} f
    JOIN {{ ref('dim_date') }} d ON f.date_key = d.date_key
    JOIN {{ ref('dim_location') }} l ON f.location_key = l.location_key
    WHERE f.has_salary_info = true
      AND f.salary_avg_usd > 0
),

current_month AS (
    SELECT
        month_key,
        seniority_key,
        job_family_key,
        country_code,
        work_model_key,
        COUNT(*) as sample_size,
        PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY salary_avg_usd) as salary_p10,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY salary_avg_usd) as salary_p25,
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY salary_avg_usd) as salary_p50,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY salary_avg_usd) as salary_p75,
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY salary_avg_usd) as salary_p90,
        AVG(salary_avg_usd) as salary_avg
    FROM fact
    GROUP BY 1, 2, 3, 4, 5
    HAVING COUNT(*) >= 5  -- Minimum sample size
)

SELECT
    c.month_key,
    c.seniority_key,
    c.job_family_key,
    c.country_code,
    c.work_model_key,
    c.sample_size,
    c.salary_p10,
    c.salary_p25,
    c.salary_p50,
    c.salary_p75,
    c.salary_p90,
    c.salary_avg,
    -- Month-over-month change
    CASE
        WHEN pm.salary_p50 > 0 THEN (c.salary_p50 - pm.salary_p50) / pm.salary_p50 * 100
        ELSE NULL
    END as mom_change_pct,
    -- Year-over-year change
    CASE
        WHEN py.salary_p50 > 0 THEN (c.salary_p50 - py.salary_p50) / py.salary_p50 * 100
        ELSE NULL
    END as yoy_change_pct,
    CURRENT_TIMESTAMP as dbt_updated_at
FROM current_month c
LEFT JOIN current_month pm ON (
    c.seniority_key = pm.seniority_key
    AND c.job_family_key = pm.job_family_key
    AND c.country_code = pm.country_code
    AND c.work_model_key = pm.work_model_key
    AND pm.month_key = c.month_key - 1  -- Previous month
)
LEFT JOIN current_month py ON (
    c.seniority_key = py.seniority_key
    AND c.job_family_key = py.job_family_key
    AND c.country_code = py.country_code
    AND c.work_model_key = py.work_model_key
    AND py.month_key = c.month_key - 100  -- Previous year (YYYYMM)
)
```

---

### 4.4 agg_posting_time_analysis

**models/aggregations/agg_posting_time_analysis.sql:**
```sql
{{ config(materialized='table') }}

WITH fact AS (
    SELECT
        d.day_of_week,
        d.day_name,
        t.hour_24,
        t.time_of_day,
        f.job_family_key,
        f.seniority_key,
        f.job_posting_key,
        f.num_applicants
    FROM {{ ref('fact_job_posting') }} f
    JOIN {{ ref('dim_date') }} d ON f.date_key = d.date_key
    JOIN {{ ref('dim_time') }} t ON f.time_key = t.time_key
),

aggregated AS (
    SELECT
        day_of_week,
        day_name,
        hour_24,
        time_of_day,
        job_family_key,
        seniority_key,
        COUNT(DISTINCT job_posting_key) as job_count,
        AVG(num_applicants) as avg_applicants
    FROM fact
    GROUP BY 1, 2, 3, 4, 5, 6
),

totals AS (
    SELECT SUM(job_count) as total_jobs FROM aggregated
),

with_metrics AS (
    SELECT
        a.*,
        a.job_count::decimal / t.total_jobs * 100 as pct_of_total,
        -- Competition score: inverse of applicants (lower = less competition)
        1 - (a.avg_applicants / NULLIF(MAX(a.avg_applicants) OVER (), 0)) as competition_score
    FROM aggregated a
    CROSS JOIN totals t
)

SELECT
    day_of_week,
    day_name,
    hour_24,
    time_of_day,
    job_family_key,
    seniority_key,
    job_count,
    pct_of_total,
    avg_applicants,
    NULL::decimal as avg_time_to_100_applicants_hrs,  -- Would need time-series data
    competition_score,
    pct_of_total >= PERCENTILE_CONT(0.8) WITHIN GROUP (ORDER BY pct_of_total) OVER () as is_peak_posting_time,
    competition_score >= PERCENTILE_CONT(0.8) WITHIN GROUP (ORDER BY competition_score) OVER () as is_low_competition_time,
    -- Recommendation: high posting volume + low competition
    (pct_of_total + competition_score) / 2 as recommendation_score,
    CURRENT_TIMESTAMP as dbt_updated_at
FROM with_metrics
```

---

### 4.5 agg_company_hiring

**models/aggregations/agg_company_hiring.sql:**
```sql
{{ config(materialized='table') }}

WITH fact AS (
    SELECT
        CAST(TO_CHAR(d.full_date, 'YYYYMM') AS INT) as month_key,
        f.company_key,
        c.company_name,
        c.company_size_bucket,
        c.industry_primary,
        f.job_posting_key,
        f.job_title_original,
        l.city,
        f.is_remote,
        f.salary_avg_usd
    FROM {{ ref('fact_job_posting') }} f
    JOIN {{ ref('dim_date') }} d ON f.date_key = d.date_key
    JOIN {{ ref('dim_company') }} c ON f.company_key = c.company_key
    JOIN {{ ref('dim_location') }} l ON f.location_key = l.location_key
)

SELECT
    month_key,
    company_key,
    MAX(company_name) as company_name,
    MAX(company_size_bucket) as company_size_bucket,
    MAX(industry_primary) as industry_primary,
    COUNT(DISTINCT job_posting_key) as new_job_postings,
    COUNT(DISTINCT job_posting_key) as active_job_postings,  -- Simplified
    COUNT(DISTINCT job_title_original) as unique_job_titles,
    COUNT(DISTINCT city) as unique_locations,
    SUM(CASE WHEN is_remote THEN 1 ELSE 0 END)::decimal / COUNT(*) * 100 as pct_remote,
    AVG(salary_avg_usd) as avg_salary_usd,
    ROW_NUMBER() OVER (PARTITION BY month_key ORDER BY COUNT(*) DESC) as hiring_velocity_rank,
    CURRENT_TIMESTAMP as dbt_updated_at
FROM fact
GROUP BY 1, 2
```

---

## Data Quality Framework

### 4.6 Reconciliation Tests

**models/data_quality/reconciliation_silver_gold.sql:**
```sql
{{ config(materialized='table') }}

WITH silver_counts AS (
    SELECT
        'linkedin' as source,
        COUNT(DISTINCT job_posting_id) as record_count,
        MAX(ingestion_timestamp) as latest_timestamp
    FROM {{ source('silver', 'linkedin') }}

    UNION ALL

    SELECT
        'ai_enrichment' as source,
        COUNT(DISTINCT job_posting_id) as record_count,
        MAX(ingestion_timestamp) as latest_timestamp
    FROM {{ source('silver', 'ai_enrichment') }}

    UNION ALL

    SELECT
        'linkedin_companies' as source,
        COUNT(DISTINCT company_id) as record_count,
        MAX(snapshot_date) as latest_timestamp
    FROM {{ source('silver', 'linkedin_companies') }}
),

gold_counts AS (
    SELECT
        'fact_job_posting' as table_name,
        COUNT(DISTINCT job_posting_id) as record_count
    FROM {{ ref('fact_job_posting') }}

    UNION ALL

    SELECT
        'dim_company' as table_name,
        COUNT(DISTINCT company_id) as record_count
    FROM {{ ref('dim_company') }}
    WHERE is_current = true
)

SELECT
    s.source,
    s.record_count as silver_count,
    g.record_count as gold_count,
    s.record_count - g.record_count as variance,
    CASE
        WHEN ABS(s.record_count - g.record_count) <= 10 THEN 'OK'
        WHEN ABS(s.record_count - g.record_count) <= 100 THEN 'WARNING'
        ELSE 'ALERT'
    END as status,
    s.latest_timestamp,
    CURRENT_TIMESTAMP as checked_at
FROM silver_counts s
LEFT JOIN gold_counts g ON (
    (s.source = 'linkedin' AND g.table_name = 'fact_job_posting')
    OR (s.source = 'linkedin_companies' AND g.table_name = 'dim_company')
)
```

---

### 4.7 Schema Tests

**models/aggregations/schema.yml:**
```yaml
version: 2

models:
  - name: agg_daily_job_metrics
    description: Daily aggregated metrics by key dimensions
    tests:
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns:
            - date_key
            - seniority_key
            - job_family_key
            - country_code
            - work_model_key
    columns:
      - name: job_count
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0

      - name: salary_avg
        tests:
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 10000000

  - name: agg_skills_demand
    description: Weekly skills demand trends
    columns:
      - name: job_count
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 1

      - name: rank_overall
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 1

  - name: agg_salary_benchmarks
    description: Monthly salary percentiles
    columns:
      - name: sample_size
        tests:
          - dbt_utils.accepted_range:
              min_value: 5  # Minimum for statistical significance

      - name: salary_p50
        tests:
          - dbt_utils.expression_is_true:
              expression: "salary_p25 <= salary_p50 AND salary_p50 <= salary_p75"
```

---

### 4.8 Alert Thresholds

**models/data_quality/alert_thresholds.sql:**
```sql
{{ config(materialized='ephemeral') }}

SELECT
    -- Reconciliation alerts
    CASE
        WHEN (SELECT MAX(status) FROM {{ ref('reconciliation_silver_gold') }}) = 'ALERT'
        THEN 'FAIL: Silver-Gold reconciliation variance exceeds threshold'
        ELSE 'PASS'
    END as reconciliation_check,

    -- Freshness alerts
    CASE
        WHEN (SELECT MAX(checked_at) FROM {{ ref('reconciliation_silver_gold') }})
             < DATEADD(hour, -6, CURRENT_TIMESTAMP)
        THEN 'FAIL: Data freshness exceeds 6 hours'
        ELSE 'PASS'
    END as freshness_check,

    -- Null rate alerts
    CASE
        WHEN (SELECT AVG(CASE WHEN company_key = -1 THEN 1 ELSE 0 END) FROM {{ ref('fact_job_posting') }}) > 0.1
        THEN 'WARN: >10% jobs missing company mapping'
        ELSE 'PASS'
    END as company_mapping_check
```

---

## Acceptance Criteria

- [ ] All 8 aggregation tables load successfully
- [ ] Salary percentiles calculate correctly (p25 < p50 < p75)
- [ ] Reconciliation passes with <1% variance
- [ ] All schema tests pass
- [ ] Aggregations refresh in <5 minutes

---

## Deliverables

```
dbt_gold/
└── models/
    ├── aggregations/
    │   ├── agg_daily_job_metrics.sql
    │   ├── agg_weekly_job_metrics.sql
    │   ├── agg_monthly_job_metrics.sql
    │   ├── agg_skills_demand.sql
    │   ├── agg_salary_benchmarks.sql
    │   ├── agg_company_hiring.sql
    │   ├── agg_posting_time_analysis.sql
    │   ├── agg_hourly_posting_summary.sql
    │   └── schema.yml
    └── data_quality/
        ├── reconciliation_silver_gold.sql
        └── alert_thresholds.sql
```
