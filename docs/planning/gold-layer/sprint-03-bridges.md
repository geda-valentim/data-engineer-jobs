# Sprint 3: Bridge Tables

## Goal

Implement all 16 bridge tables for many-to-many relationships (skills, certifications, benefits, etc.)

## Prerequisites

- [ ] Sprint 2 completed (fact_job_posting available)
- [ ] All supporting dimensions loaded

---

## Bridge Table Categories

| Category | Tables | Count |
|----------|--------|-------|
| Skills | bridge_job_skills | 1 |
| Tech Stack | bridge_job_certifications, bridge_job_cloud_stack, bridge_job_ml_tools | 3 |
| Benefits & Career | bridge_job_benefits, bridge_job_career_tracks | 2 |
| Geographic | bridge_job_geo_restrictions, bridge_job_us_state_restrictions | 2 |
| Culture & Quality | bridge_job_maturity_signals, bridge_job_dev_practices, bridge_job_culture_signals | 3 |
| Recommendations | bridge_job_strengths, bridge_job_concerns, bridge_job_best_fit, bridge_job_probes, bridge_job_leverage | 5 |

---

## Common Bridge Structure

All bridges share this pattern:

```sql
{{ config(
    materialized='incremental',
    unique_key='bridge_key',
    incremental_strategy='delete+insert'
) }}

WITH source AS (
    SELECT
        job_posting_id,
        <array_column>
    FROM {{ source('silver', '<table>') }}
    {% if is_incremental() %}
    WHERE ingestion_timestamp > (SELECT max(dbt_updated_at) FROM {{ this }})
    {% endif %}
),

exploded AS (
    SELECT
        job_posting_id,
        value::string as <entity_name>
    FROM source,
    LATERAL FLATTEN(input => <array_column>)
)

SELECT
    {{ surrogate_key(['e.job_posting_id', 'e.<entity_name>']) }} as bridge_key,
    f.job_posting_key,
    d.<entity>_key,
    -- Additional columns specific to bridge
    CURRENT_TIMESTAMP as dbt_updated_at
FROM exploded e
JOIN {{ ref('fact_job_posting') }} f ON e.job_posting_id = f.job_posting_id
JOIN {{ ref('dim_<entity>') }} d ON e.<entity_name> = d.<entity_name>
```

---

### 3.1 bridge_job_skills (Unified - Snowflake)

**models/bridges/bridge_job_skills.sql:**
```sql
{{ config(
    materialized='incremental',
    unique_key='bridge_key',
    incremental_strategy='delete+insert'
) }}

WITH ai AS (
    SELECT
        job_posting_id,
        ext_must_have_hard_skills,
        ext_nice_to_have_hard_skills,
        ext_must_have_soft_skills,
        ext_nice_to_have_soft_skills
    FROM {{ source('silver', 'ai_enrichment') }}
    {% if is_incremental() %}
    WHERE ingestion_timestamp > (SELECT max(dbt_updated_at) FROM {{ this }})
    {% endif %}
),

-- Explode all skill arrays with metadata
all_skills AS (
    -- Required hard skills
    SELECT
        job_posting_id,
        value::string as skill_name,
        'required' as requirement_type,
        'extracted' as skill_source,
        'HARD' as skill_type_expected
    FROM ai, LATERAL FLATTEN(input => ext_must_have_hard_skills)

    UNION ALL

    -- Nice-to-have hard skills
    SELECT
        job_posting_id,
        value::string as skill_name,
        'nice_to_have' as requirement_type,
        'extracted' as skill_source,
        'HARD' as skill_type_expected
    FROM ai, LATERAL FLATTEN(input => ext_nice_to_have_hard_skills)

    UNION ALL

    -- Required soft skills
    SELECT
        job_posting_id,
        value::string as skill_name,
        'required' as requirement_type,
        'extracted' as skill_source,
        'SOFT' as skill_type_expected
    FROM ai, LATERAL FLATTEN(input => ext_must_have_soft_skills)

    UNION ALL

    -- Nice-to-have soft skills
    SELECT
        job_posting_id,
        value::string as skill_name,
        'nice_to_have' as requirement_type,
        'extracted' as skill_source,
        'SOFT' as skill_type_expected
    FROM ai, LATERAL FLATTEN(input => ext_nice_to_have_soft_skills)
)

SELECT
    {{ surrogate_key(['s.job_posting_id', 's.skill_name', 's.requirement_type']) }} as bridge_key,
    f.job_posting_key,
    COALESCE(d.skill_key, -1) as skill_key,
    s.requirement_type,
    s.skill_source,
    NULL::decimal(3,2) as confidence_score,
    -- Denormalized from snowflake for performance
    COALESCE(d.skill_type, s.skill_type_expected) as skill_type,
    d.skill_category,
    d.skill_family,
    CURRENT_TIMESTAMP as dbt_updated_at
FROM all_skills s
JOIN {{ ref('fact_job_posting') }} f ON s.job_posting_id = f.job_posting_id
LEFT JOIN {{ ref('dim_skill') }} d ON LOWER(s.skill_name) = LOWER(d.skill_canonical_name)
```

---

### 3.2 bridge_job_certifications

**models/bridges/bridge_job_certifications.sql:**
```sql
{{ config(
    materialized='incremental',
    unique_key='bridge_key',
    incremental_strategy='delete+insert'
) }}

WITH ai AS (
    SELECT
        job_posting_id,
        ext_certifications_mentioned
    FROM {{ source('silver', 'ai_enrichment') }}
    WHERE ext_certifications_mentioned IS NOT NULL
    {% if is_incremental() %}
    AND ingestion_timestamp > (SELECT max(dbt_updated_at) FROM {{ this }})
    {% endif %}
),

exploded AS (
    SELECT
        job_posting_id,
        value::string as cert_name
    FROM ai, LATERAL FLATTEN(input => ext_certifications_mentioned)
)

SELECT
    {{ surrogate_key(['e.job_posting_id', 'e.cert_name']) }} as bridge_key,
    f.job_posting_key,
    COALESCE(d.cert_key, -1) as cert_key,
    NULL::decimal(3,2) as confidence_score,
    CURRENT_TIMESTAMP as dbt_updated_at
FROM exploded e
JOIN {{ ref('fact_job_posting') }} f ON e.job_posting_id = f.job_posting_id
LEFT JOIN {{ ref('dim_certification') }} d ON LOWER(e.cert_name) LIKE '%' || LOWER(d.cert_name) || '%'
```

---

### 3.3 bridge_job_cloud_stack

**models/bridges/bridge_job_cloud_stack.sql:**
```sql
{{ config(
    materialized='incremental',
    unique_key='bridge_key',
    incremental_strategy='delete+insert'
) }}

WITH ai AS (
    SELECT
        job_posting_id,
        inf_primary_cloud,
        inf_secondary_clouds
    FROM {{ source('silver', 'ai_enrichment') }}
    {% if is_incremental() %}
    WHERE ingestion_timestamp > (SELECT max(dbt_updated_at) FROM {{ this }})
    {% endif %}
),

all_clouds AS (
    -- Primary cloud
    SELECT
        job_posting_id,
        inf_primary_cloud as cloud_name,
        true as is_primary
    FROM ai
    WHERE inf_primary_cloud IS NOT NULL

    UNION ALL

    -- Secondary clouds
    SELECT
        job_posting_id,
        value::string as cloud_name,
        false as is_primary
    FROM ai, LATERAL FLATTEN(input => inf_secondary_clouds)
    WHERE inf_secondary_clouds IS NOT NULL
)

SELECT
    {{ surrogate_key(['c.job_posting_id', 'c.cloud_name']) }} as bridge_key,
    f.job_posting_key,
    COALESCE(d.cloud_platform_key, -1) as cloud_platform_key,
    c.is_primary,
    NULL::decimal(3,2) as confidence_score,
    CURRENT_TIMESTAMP as dbt_updated_at
FROM all_clouds c
JOIN {{ ref('fact_job_posting') }} f ON c.job_posting_id = f.job_posting_id
LEFT JOIN {{ ref('dim_cloud_platform') }} d ON c.cloud_name = d.cloud_platform_name
```

---

### 3.4 bridge_job_benefits

**models/bridges/bridge_job_benefits.sql:**
```sql
{{ config(
    materialized='incremental',
    unique_key='bridge_key',
    incremental_strategy='delete+insert'
) }}

WITH ai AS (
    SELECT
        job_posting_id,
        ext_benefits_mentioned
    FROM {{ source('silver', 'ai_enrichment') }}
    WHERE ext_benefits_mentioned IS NOT NULL
    {% if is_incremental() %}
    AND ingestion_timestamp > (SELECT max(dbt_updated_at) FROM {{ this }})
    {% endif %}
),

exploded AS (
    SELECT
        job_posting_id,
        value::string as benefit_name
    FROM ai, LATERAL FLATTEN(input => ext_benefits_mentioned)
)

SELECT
    {{ surrogate_key(['e.job_posting_id', 'e.benefit_name']) }} as bridge_key,
    f.job_posting_key,
    COALESCE(d.benefit_key, -1) as benefit_key,
    NULL::decimal(3,2) as confidence_score,
    CURRENT_TIMESTAMP as dbt_updated_at
FROM exploded e
JOIN {{ ref('fact_job_posting') }} f ON e.job_posting_id = f.job_posting_id
LEFT JOIN {{ ref('dim_benefit') }} d ON LOWER(e.benefit_name) LIKE '%' || LOWER(d.benefit_name) || '%'
```

---

### 3.5 bridge_job_strengths

**models/bridges/bridge_job_strengths.sql:**
```sql
{{ config(
    materialized='incremental',
    unique_key='bridge_key',
    incremental_strategy='delete+insert'
) }}

WITH ai AS (
    SELECT
        job_posting_id,
        anl_strengths
    FROM {{ source('silver', 'ai_enrichment') }}
    WHERE anl_strengths IS NOT NULL
    {% if is_incremental() %}
    AND ingestion_timestamp > (SELECT max(dbt_updated_at) FROM {{ this }})
    {% endif %}
),

exploded AS (
    SELECT
        job_posting_id,
        value::string as strength_name
    FROM ai, LATERAL FLATTEN(input => anl_strengths)
)

SELECT
    {{ surrogate_key(['e.job_posting_id', 'e.strength_name']) }} as bridge_key,
    f.job_posting_key,
    COALESCE(d.strength_key, -1) as strength_key,
    NULL::decimal(3,2) as confidence_score,
    CURRENT_TIMESTAMP as dbt_updated_at
FROM exploded e
JOIN {{ ref('fact_job_posting') }} f ON e.job_posting_id = f.job_posting_id
LEFT JOIN {{ ref('dim_strength_category') }} d ON LOWER(e.strength_name) = LOWER(d.category_name)
```

---

### 3.6 bridge_job_concerns

**models/bridges/bridge_job_concerns.sql:**
```sql
{{ config(
    materialized='incremental',
    unique_key='bridge_key',
    incremental_strategy='delete+insert'
) }}

WITH ai AS (
    SELECT
        job_posting_id,
        anl_concerns
    FROM {{ source('silver', 'ai_enrichment') }}
    WHERE anl_concerns IS NOT NULL
    {% if is_incremental() %}
    AND ingestion_timestamp > (SELECT max(dbt_updated_at) FROM {{ this }})
    {% endif %}
),

exploded AS (
    SELECT
        job_posting_id,
        value::string as concern_name
    FROM ai, LATERAL FLATTEN(input => anl_concerns)
)

SELECT
    {{ surrogate_key(['e.job_posting_id', 'e.concern_name']) }} as bridge_key,
    f.job_posting_key,
    COALESCE(d.concern_key, -1) as concern_key,
    NULL::decimal(3,2) as confidence_score,
    CURRENT_TIMESTAMP as dbt_updated_at
FROM exploded e
JOIN {{ ref('fact_job_posting') }} f ON e.job_posting_id = f.job_posting_id
LEFT JOIN {{ ref('dim_concern_category') }} d ON LOWER(e.concern_name) = LOWER(d.category_name)
```

---

### 3.7-3.16 Remaining Bridge Tables

Similar pattern for:
- `bridge_job_ml_tools` - from `anl_ml_tools_expected[]`
- `bridge_job_career_tracks` - from `inf_career_tracks_available[]`
- `bridge_job_geo_restrictions` - from `ext_allowed_countries[]`, `ext_excluded_countries[]`
- `bridge_job_us_state_restrictions` - from `ext_us_state_restrictions[]`
- `bridge_job_maturity_signals` - from `anl_maturity_signals[]`
- `bridge_job_dev_practices` - from `anl_dev_practices_mentioned[]`
- `bridge_job_culture_signals` - from `anl_tech_culture_signals[]`
- `bridge_job_best_fit` - from `anl_best_fit_for[]`
- `bridge_job_probes` - from `anl_red_flags_to_probe[]`
- `bridge_job_leverage` - from `anl_negotiation_leverage[]`

---

## Acceptance Criteria

- [ ] All 16 bridge tables load successfully
- [ ] bridge_job_skills unifies hard + soft with correct skill_type
- [ ] Skill snowflake denormalization works (skill_type, category, family)
- [ ] Incremental logic tested
- [ ] No orphan foreign keys
- [ ] Data quality tests pass

---

## Expected Row Counts

| Bridge | Avg per Job | Total (~50K jobs) |
|--------|-------------|-------------------|
| bridge_job_skills | 8-15 | ~400-750K |
| bridge_job_certifications | 0-3 | ~50-150K |
| bridge_job_benefits | 3-8 | ~150-400K |
| bridge_job_strengths | 2-5 | ~100-250K |
| bridge_job_concerns | 1-4 | ~50-200K |

---

## Query Examples

**Top skills by job family:**
```sql
SELECT
    jf.job_family_name,
    s.skill_canonical_name,
    s.skill_type,
    COUNT(*) as job_count
FROM gold.bridge_job_skills b
JOIN gold.fact_job_posting f ON b.job_posting_key = f.job_posting_key
JOIN gold.dim_job_family jf ON f.job_family_key = jf.job_family_key
JOIN gold.dim_skill s ON b.skill_key = s.skill_key
WHERE b.requirement_type = 'required'
GROUP BY 1, 2, 3
ORDER BY 1, 4 DESC;
```

**Jobs with specific certifications:**
```sql
SELECT
    f.job_title_original,
    c.company_name,
    cert.cert_name
FROM gold.bridge_job_certifications b
JOIN gold.fact_job_posting f ON b.job_posting_key = f.job_posting_key
JOIN gold.dim_company c ON f.company_key = c.company_key
JOIN gold.dim_certification cert ON b.cert_key = cert.cert_key
WHERE cert.cert_name = 'AWS Solutions Architect';
```
