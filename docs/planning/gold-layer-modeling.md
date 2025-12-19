# Gold Layer - Dimensional Modeling

## Executive Summary

O Gold Layer implementa um modelo dimensional (Star Schema) otimizado para analytics, consolidando dados de 3 fontes Silver:

| Source | Records | Fields | Content |
|--------|---------|--------|---------|
| `linkedin/` | ~50K+ jobs | 33 | Job postings (title, salary, location, skills) |
| `linkedin_companies/` | ~10K+ | 41 | Company profiles (size, industry, funding) |
| `ai_enrichment/` | ~50K+ | ~280 | AI analysis (extraction, inference, recommendations) |

**Output**: 1 fact table, 55 dimensions (11 core + 3 snowflake + 27 AI + 14 bridge support), 16 bridge tables, 8 aggregations, 1 confidence table.

**Total: 81 tables** (modelo completo com skills snowflake + time analysis)

---

## Silver Layer Reference

> **Schema completo**: [`silver-layer-schema.md`](./silver-layer-schema.md)

| Code | Source | Columns | Description |
|------|--------|---------|-------------|
| `SLV-LI` | `linkedin/` | 35 | Job postings |
| `SLV-CO` | `linkedin_companies/` | 47 | Company profiles |
| `SLV-AI` | `ai_enrichment/` | 175+ | AI analysis (Pass 1-3) |

---

## Source Data (Silver Layer)

### linkedin/ - Job Postings (33 fields)

```
Identification: job_posting_id, source_system, url, scraped_at
Company:        company_name, company_id, company_url
Job Core:       job_title, job_seniority_level, job_function, job_employment_type, job_industries
Location:       job_location, country_code, job_posted_datetime
Application:    application_availability, apply_link, job_num_applicants
Compensation:   salary_min, salary_max, salary_currency, salary_period
Description:    job_summary, job_description_text
Skills:         skills_canonical[], skills_families[], skills_raw_hits[]
```

### linkedin_companies/ - Company Profiles (41 fields)

```
Identity:       company_id, linkedin_id, name, website_domain
Location:       headquarters, country_code, locations_json
Business:       industries, specialties, organization_type, company_size, founded_year
Metrics:        followers, employees_on_linkedin
Funding:        funding_stage, funding_rounds_count, last_funding_date, funding_amount
```

### ai_enrichment/ - AI Analysis (~280 fields)

```
Pass 1 (ext_*):  57 cols - Factual extraction (salary, skills, requirements, benefits)
Pass 2 (inf_*): 100 cols - Inferences with confidence (seniority, job_family, cloud, visa)
Pass 3 (anl_*): 124 cols - Analysis (maturity scores, red flags, recommendations)
```

---

## Star Schema

```
                        +-------------------+     +-------------------+
                        |    dim_date       |     |    dim_time       |
                        +-------------------+     +-------------------+
                                     \                   /
                                      \                 /
+-------------------+              +-------------------+              +-------------------+
|  dim_company      |--------------|  FACT_JOB_POSTING |--------------|  dim_location     |
|  (SCD2)           |              |                   |              |  (hierarchy)      |
+-------------------+              +-------------------+              +-------------------+
                                             |
═══════════════════════════════════════════════════════════════════════════════════════════
                                   CORE DIMENSIONS (11)
═══════════════════════════════════════════════════════════════════════════════════════════
        |           |           |            |            |           |
+-------------+ +-------------+ +-------------+ +-------------+ +-------------+ +-------------+
|dim_seniority| |dim_job_family| |dim_work_model| |dim_employment| |dim_contract| |dim_cloud    |
+-------------+ +-------------+ +-------------+ +-------------+ +-------------+ +-------------+

═══════════════════════════════════════════════════════════════════════════════════════════
                              AI ENRICHMENT - PASS 1 EXTRACTION (10)
═══════════════════════════════════════════════════════════════════════════════════════════
        |           |           |            |            |           |
+-------------+ +-------------+ +-------------+ +-------------+ +-------------+ +-------------+
|dim_education| |dim_pay_type | |dim_start   | |dim_geo     | |dim_pto      | |dim_security |
|             | |             | |_urgency    | |_restriction| |_policy      | |_clearance   |
+-------------+ +-------------+ +-------------+ +-------------+ +-------------+ +-------------+

═══════════════════════════════════════════════════════════════════════════════════════════
                              AI ENRICHMENT - PASS 2 INFERENCE (10)
═══════════════════════════════════════════════════════════════════════════════════════════
        |           |           |            |            |           |
+-------------+ +-------------+ +-------------+ +-------------+ +-------------+ +-------------+
|dim_visa     | |dim_leadership| |dim_orchestr.| |dim_storage | |dim_processing| |dim_remote  |
|_status      | |              | |             | |_layer      | |_paradigm     | |_restriction|
+-------------+ +-------------+ +-------------+ +-------------+ +-------------+ +-------------+
        |           |           |            |            |           |
+-------------+ +-------------+ +-------------+ +-------------+ +-------------+ +-------------+
|dim_timezone | |dim_growth   | |dim_require | |dim_benefits| |              |              |
|             | |_clarity     | |_strictness | |_level      |              |              |
+-------------+ +-------------+ +-------------+ +-------------+ +-------------+ +-------------+

═══════════════════════════════════════════════════════════════════════════════════════════
                              AI ENRICHMENT - PASS 3 ANALYSIS (10)
═══════════════════════════════════════════════════════════════════════════════════════════
        |           |           |            |            |           |
+-------------+ +-------------+ +-------------+ +-------------+ +-------------+ +-------------+
|dim_maturity | |dim_role     | |dim_manager | |dim_team    | |dim_reporting| |dim_ai       |
|_level       | |_clarity     | |_level      | |_velocity   | |_structure   | |_integration |
+-------------+ +-------------+ +-------------+ +-------------+ +-------------+ +-------------+
        |           |           |            |            |           |
+-------------+ +-------------+ +-------------+ +-------------+ +-------------+ +-------------+
|dim_company  | |dim_team_size| |dim_hiring  | |dim_hiring  | |dim_competit.|              |
|_stage       | |             | |_context    | |_urgency    | |              |              |
+-------------+ +-------------+ +-------------+ +-------------+ +-------------+ +-------------+

═══════════════════════════════════════════════════════════════════════════════════════════
                              BRIDGE TABLES - Many-to-Many (16)
═══════════════════════════════════════════════════════════════════════════════════════════

                    SKILLS SNOWFLAKE (unified hard + soft + hybrid)
                    ┌─────────────────────────────────────────────┐
                    │                                             │
              +------------+     +---------------+     +--------------+
              |dim_skill   |---->|dim_skill_type |     |dim_skill     |
              |_category   |     |(HARD/SOFT/    |<----|_family       |
              |            |     | HYBRID)       |     |              |
              +------------+     +---------------+     +--------------+
                    │                   ▲
                    └───────────────────┘
                              │
+--------+  +--------+  +--------+  +--------+  +--------+  +--------+  +--------+
|skills  |  |certs   |  |benefits|  |cloud   |  |career  |  |geo     |  |us_state|
|(unified)|  |        |  |        |  |_stack  |  |_tracks |  |_restric|  |_restric|
+--------+  +--------+  +--------+  +--------+  +--------+  +--------+  +--------+

+--------+  +--------+  +--------+  +--------+  +--------+  +--------+  +--------+
|ml_tools|  |maturity|  |dev     |  |culture |  |strengths| |concerns|  |best_fit|
|        |  |_signals|  |_practic|  |_signals|  |        |  |        |  |        |
+--------+  +--------+  +--------+  +--------+  +--------+  +--------+  +--------+

+--------+  +--------+
|probes  |  |leverage|
|        |  |        |
+--------+  +--------+
```

---

## Fact Tables

### fact_job_posting

**Grain**: 1 row per unique job posting

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| **Keys - Core** | | | |
| job_posting_key | BIGINT | SK | Surrogate key (PK) |
| date_key | INT | SLV-LI.job_posted_datetime | FK to dim_date (YYYYMMDD) |
| time_key | INT | SLV-LI.job_posted_datetime | FK to dim_time (HHMM or HH) |
| company_key | BIGINT | SLV-LI.company_id | FK to dim_company |
| location_key | BIGINT | SLV-LI.job_location | FK to dim_location |
| seniority_key | INT | SLV-LI.job_seniority_level | FK to dim_seniority |
| job_family_key | INT | SLV-AI.inf_job_family | FK to dim_job_family |
| work_model_key | INT | SLV-AI.ext_work_model_stated | FK to dim_work_model |
| employment_type_key | INT | SLV-LI.job_employment_type | FK to dim_employment_type |
| contract_type_key | INT | SLV-AI.ext_contract_type | FK to dim_contract_type |
| cloud_platform_key | INT | SLV-AI.inf_primary_cloud | FK to dim_cloud_platform |
| **Keys - Pass 1 Extraction** | | | |
| education_key | INT | SLV-AI.ext_education_level | FK to dim_education |
| pay_type_key | INT | SLV-AI.ext_pay_type | FK to dim_pay_type |
| start_urgency_key | INT | SLV-AI.ext_start_date | FK to dim_start_urgency |
| geo_restriction_key | INT | SLV-AI.ext_geo_restriction_type | FK to dim_geo_restriction |
| pto_policy_key | INT | SLV-AI.ext_pto_policy | FK to dim_pto_policy |
| security_clearance_key | INT | SLV-AI.ext_security_clearance_stated | FK to dim_security_clearance |
| **Keys - Pass 2 Inference** | | | |
| visa_status_key | INT | SLV-AI.ext_visa_sponsorship_stated | FK to dim_visa_status |
| leadership_key | INT | SLV-AI.inf_leadership_expectation | FK to dim_leadership |
| orchestrator_key | INT | SLV-AI.inf_orchestrator_category | FK to dim_orchestrator |
| storage_layer_key | INT | SLV-AI.inf_storage_layer | FK to dim_storage_layer |
| processing_paradigm_key | INT | SLV-AI.inf_processing_paradigm | FK to dim_processing_paradigm |
| remote_restriction_key | INT | SLV-AI.inf_remote_restriction | FK to dim_remote_restriction |
| timezone_key | INT | SLV-AI.inf_timezone_focus | FK to dim_timezone |
| growth_clarity_key | INT | SLV-AI.inf_growth_path_clarity | FK to dim_growth_clarity |
| requirement_strictness_key | INT | SLV-AI.inf_requirement_strictness | FK to dim_requirement_strictness |
| benefits_level_key | INT | SLV-AI.inf_benefits_level | FK to dim_benefits_level |
| **Keys - Pass 3 Analysis** | | | |
| maturity_level_key | INT | SLV-AI.anl_data_maturity_level | FK to dim_maturity_level |
| role_clarity_key | INT | SLV-AI.anl_role_clarity | FK to dim_role_clarity |
| manager_level_key | INT | SLV-AI.anl_manager_level_inferred | FK to dim_manager_level |
| team_velocity_key | INT | SLV-AI.anl_team_growth_velocity | FK to dim_team_velocity |
| reporting_structure_key | INT | SLV-AI.anl_reporting_structure | FK to dim_reporting_structure |
| ai_integration_key | INT | SLV-AI.anl_ai_integration_level | FK to dim_ai_integration |
| company_stage_key | INT | SLV-AI.anl_company_stage_inferred | FK to dim_company_stage |
| team_size_key | INT | SLV-AI.anl_team_size_signals | FK to dim_team_size |
| hiring_context_key | INT | SLV-AI.anl_role_creation_type | FK to dim_hiring_context |
| hiring_urgency_key | INT | SLV-AI.anl_hiring_urgency | FK to dim_hiring_urgency |
| competition_key | INT | SLV-AI.anl_competition_level | FK to dim_competition |
| **Natural Keys** | | | |
| job_posting_id | STRING | SLV-LI.job_posting_id | LinkedIn job ID |
| source_system | STRING | SLV-LI.source_system | Source (linkedin) |
| **Measures - Compensation (Additive)** | | | |
| num_applicants | INT | SLV-LI.job_num_applicants | Number of applicants |
| salary_min_usd | DECIMAL(12,2) | SLV-LI.salary_min | Min salary (USD) |
| salary_max_usd | DECIMAL(12,2) | SLV-LI.salary_max | Max salary (USD) |
| salary_avg_usd | DECIMAL(12,2) | DERIVED | Avg salary (USD) |
| hourly_rate_min_usd | DECIMAL(8,2) | SLV-AI.ext_hourly_rate_min | Min hourly rate (USD) |
| hourly_rate_max_usd | DECIMAL(8,2) | SLV-AI.ext_hourly_rate_max | Max hourly rate (USD) |
| daily_rate_min_usd | DECIMAL(10,2) | SLV-AI.ext_daily_rate_min | Min daily rate (USD) |
| daily_rate_max_usd | DECIMAL(10,2) | SLV-AI.ext_daily_rate_max | Max daily rate (USD) |
| **Measures - Experience & Skills** | | | |
| years_experience_min | INT | SLV-AI.ext_years_experience_min | Min experience required |
| years_experience_max | INT | SLV-AI.ext_years_experience_max | Max experience required |
| skills_count | INT | SLV-LI.skills_canonical | Total skills mentioned |
| required_hard_skills_count | INT | SLV-AI.ext_must_have_hard_skills | Must-have hard skills |
| nice_to_have_hard_skills_count | INT | SLV-AI.ext_nice_to_have_hard_skills | Nice-to-have hard skills |
| required_soft_skills_count | INT | SLV-AI.ext_must_have_soft_skills | Must-have soft skills |
| nice_to_have_soft_skills_count | INT | SLV-AI.ext_nice_to_have_soft_skills | Nice-to-have soft skills |
| certifications_count | INT | SLV-AI.ext_certifications_mentioned | Certifications mentioned |
| **Measures - Contract** | | | |
| contract_duration_months | INT | SLV-AI.ext_contract_duration_months | Contract duration (months) |
| **Measures - Scores (Pass 3)** | | | |
| data_maturity_score | DECIMAL(3,2) | SLV-AI.anl_data_maturity_score | Company data maturity (1-5) |
| scope_creep_score | DECIMAL(3,2) | SLV-AI.anl_scope_creep_score | Role scope creep risk (0-1) |
| overtime_risk_score | DECIMAL(3,2) | SLV-AI.anl_overtime_risk_score | Overtime/burnout risk (0-1) |
| work_life_balance_score | DECIMAL(3,2) | SLV-AI.anl_work_life_balance_score | WLB indicator (0-1) |
| growth_opportunities_score | DECIMAL(3,2) | SLV-AI.anl_growth_opportunities_score | Career growth (0-1) |
| tech_culture_score | DECIMAL(3,2) | SLV-AI.anl_tech_culture_score | Tech culture (0-1) |
| innovation_score | DECIMAL(3,2) | SLV-AI.anl_innovation_signals | Innovation signals (0-1) |
| recommendation_score | DECIMAL(3,2) | SLV-AI.anl_recommendation_score | Overall recommendation (0-1) |
| overall_risk_score | DECIMAL(3,2) | SLV-AI.anl_overall_red_flag_score | Combined red flags (0-1) |
| **Measures - Confidence** | | | |
| avg_confidence_pass2 | DECIMAL(3,2) | SLV-AI.inf_*_confidence | Avg confidence Pass 2 |
| avg_confidence_pass3 | DECIMAL(3,2) | SLV-AI.anl_*_confidence | Avg confidence Pass 3 |
| low_confidence_count | INT | DERIVED | Fields with conf < 0.5 |
| **Flags - Compensation** | | | |
| has_salary_info | BOOLEAN | SLV-AI.ext_salary_disclosed | Salary disclosed |
| has_hourly_rate | BOOLEAN | SLV-AI.ext_hourly_rate_min | Hourly rate disclosed |
| has_daily_rate | BOOLEAN | SLV-AI.ext_daily_rate_min | Daily rate disclosed |
| equity_offered | BOOLEAN | SLV-AI.ext_equity_mentioned | Equity/stock mentioned |
| **Flags - Work Authorization** | | | |
| visa_sponsorship_available | BOOLEAN | SLV-AI.ext_visa_sponsorship_stated | Visa sponsorship |
| h1b_friendly | BOOLEAN | SLV-AI.inf_h1b_friendly | H1B friendly |
| opt_cpt_friendly | BOOLEAN | SLV-AI.inf_opt_cpt_friendly | OPT/CPT friendly |
| is_remote | BOOLEAN | SLV-AI.ext_work_model_stated | Remote position |
| **Flags - Contract** | | | |
| extension_possible | BOOLEAN | SLV-AI.ext_extension_possible | Contract extension possible |
| conversion_to_fte | BOOLEAN | SLV-AI.ext_conversion_to_fte | Can convert to full-time |
| **Flags - Tech Stack** | | | |
| genai_mentioned | BOOLEAN | SLV-AI.ext_llm_genai_mentioned | GenAI/LLM required |
| llm_genai_mentioned | BOOLEAN | SLV-AI.ext_llm_genai_mentioned | LLM/GenAI in requirements |
| feature_store_mentioned | BOOLEAN | SLV-AI.ext_feature_store_mentioned | Feature store mentioned |
| **Flags - Culture & Benefits** | | | |
| learning_budget_mentioned | BOOLEAN | SLV-AI.ext_learning_budget_mentioned | Learning budget offered |
| conference_budget_mentioned | BOOLEAN | SLV-AI.ext_conference_budget_mentioned | Conference budget |
| mentorship_available | BOOLEAN | SLV-AI.inf_mentorship_signals | Mentorship signals |
| promotion_path_mentioned | BOOLEAN | SLV-AI.inf_promotion_path_mentioned | Clear promotion path |
| open_source_contributor | BOOLEAN | SLV-AI.anl_tech_culture_signals | OSS contribution culture |
| tech_blog_present | BOOLEAN | SLV-AI.anl_tech_culture_signals | Company tech blog exists |
| hackathons_mentioned | BOOLEAN | SLV-AI.anl_tech_culture_signals | Hackathons culture |
| **Flags - Red Flags** | | | |
| skill_inflation_detected | BOOLEAN | SLV-AI.inf_skill_inflation_detected | Unrealistic requirements |
| scope_creep_detected | BOOLEAN | SLV-AI.anl_scope_creep_score | Multi-role scope |
| overtime_likely | BOOLEAN | SLV-AI.anl_overtime_risk_score | Overtime signals |
| **Degenerate Dimensions** | | | |
| job_title_original | STRING | SLV-LI.job_title | Original job title |
| job_title_normalized | STRING | DERIVED | Normalized title |
| job_url | STRING | SLV-LI.url | Job posting URL |
| salary_currency_original | STRING | SLV-LI.salary_currency | Original salary currency |
| salary_period_original | STRING | SLV-LI.salary_period | Original period (annual/hourly) |

**Partitioning**: `year/month/day` (by job_posted_date)

---

### bridge_job_skills (Unified - Snowflake)

**Grain**: 1 row per job-skill combination (all skill types)

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| bridge_key | BIGINT | SK | Surrogate key (PK) |
| job_posting_key | BIGINT | SK | FK to fact_job_posting |
| skill_key | BIGINT | SK | FK to dim_skill |
| **Skill Classification** | | | |
| requirement_type | STRING | DERIVED | 'required' or 'nice_to_have' |
| skill_source | STRING | DERIVED | 'extracted', 'inferred', 'catalog' |
| confidence_score | DECIMAL(3,2) | SLV-AI.*_confidence | Confidence (0-1) |
| **Denormalized from Snowflake** | | | |
| skill_type | STRING | dim_skill_type | HARD, SOFT, HYBRID |
| skill_category | STRING | dim_skill_category | Programming, Communication, etc. |
| skill_family | STRING | dim_skill_family | Core Programming, Interpersonal, etc. |

**Sources**:
- Hard skills: `SLV-AI.ext_must_have_hard_skills[]`, `SLV-AI.ext_nice_to_have_hard_skills[]`
- Soft skills: `SLV-AI.ext_must_have_soft_skills[]`, `SLV-AI.ext_nice_to_have_soft_skills[]`

**Partitioning**: `year/month` (by job_posted_date)

---

## Dimension Tables

### dim_date (Static)

| Column | Type | Source | Example |
|--------|------|--------|---------|
| date_key | INT | STATIC | 20251218 |
| full_date | DATE | STATIC | 2025-12-18 |
| year | INT | STATIC | 2025 |
| quarter | INT | STATIC | 4 |
| month | INT | STATIC | 12 |
| month_name | STRING | STATIC | December |
| week_of_year | INT | STATIC | 51 |
| day_of_month | INT | STATIC | 18 |
| day_of_week | INT | STATIC | 4 (Thursday) |
| day_name | STRING | STATIC | Thursday |
| is_weekend | BOOLEAN | STATIC | FALSE |

Pre-populated: 2020-2030

---

### dim_time (Static) - NEW

**Purpose**: Analyze job posting times and best hours to apply

| Column | Type | Source | Example |
|--------|------|--------|---------|
| time_key | INT | STATIC | 1430 (14:30) |
| hour_24 | INT | STATIC | 14 |
| hour_12 | INT | STATIC | 2 |
| minute | INT | STATIC | 30 |
| am_pm | STRING | STATIC | PM |
| time_of_day | STRING | STATIC | Afternoon |
| time_bucket_30min | STRING | STATIC | 14:30-15:00 |
| time_bucket_1hr | STRING | STATIC | 14:00-15:00 |
| time_bucket_4hr | STRING | STATIC | 12:00-16:00 |
| is_business_hours | BOOLEAN | STATIC | TRUE |
| is_peak_posting_hour | BOOLEAN | STATIC | TRUE |
| hour_label | STRING | STATIC | 2 PM |

**Time of Day Buckets**:

| time_of_day | Hours | Description |
|-------------|-------|-------------|
| Early Morning | 05:00-08:59 | Before business hours |
| Morning | 09:00-11:59 | Business morning |
| Afternoon | 12:00-16:59 | Business afternoon |
| Evening | 17:00-20:59 | After business hours |
| Night | 21:00-04:59 | Night hours |

**Business Hours**: 09:00-17:59 (local timezone)

Pre-populated: 0000-2359 (1440 rows, one per minute) or 0-23 (24 rows, one per hour)

---

### dim_company (SCD Type 2)

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| company_key | BIGINT | SK | Surrogate key |
| company_id | STRING | SLV-CO.company_id | Natural key (LinkedIn ID) |
| company_name | STRING | SLV-CO.name | Company name |
| website_domain | STRING | SLV-CO.website_domain | Domain |
| headquarters_city | STRING | SLV-CO.headquarters | HQ city |
| headquarters_country | STRING | SLV-CO.country_code | HQ country (ISO) |
| industry_primary | STRING | SLV-CO.industries | Primary industry |
| organization_type | STRING | SLV-CO.organization_type | Public/Private/Nonprofit |
| company_size_bucket | STRING | SLV-CO.company_size | Startup/SMB/Mid-Market/Enterprise |
| company_size_min | INT | SLV-CO.company_size | Min employees |
| company_size_max | INT | SLV-CO.company_size | Max employees |
| founded_year | INT | SLV-CO.founded_year | Year founded |
| linkedin_followers | INT | SLV-CO.followers | Follower count |
| linkedin_employees | INT | SLV-CO.employees_on_linkedin | Employee count |
| funding_stage | STRING | SLV-CO.funding_last_round_type | Seed/Series A/B/C/Public |
| has_funding_info | BOOLEAN | SLV-CO.has_funding_info | Has funding data |
| **SCD2 Fields** | | | |
| effective_start_date | DATE | SLV-CO.snapshot_date | Version start |
| effective_end_date | DATE | DERIVED | Version end |
| is_current | BOOLEAN | DERIVED | Current version |

---

### dim_location (Hierarchy)

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| location_key | BIGINT | SK | Surrogate key |
| city | STRING | SLV-LI.job_location | City name |
| state_province | STRING | SLV-LI.job_location | State/Province |
| state_code | STRING | SLV-LI.job_location | State code (US) |
| country_code | STRING | SLV-LI.country_code | ISO 3166-1 alpha-2 |
| country_name | STRING | DERIVED | Country name |
| region | STRING | DERIVED | North America/Europe/APAC/LATAM |
| timezone_primary | STRING | DERIVED | Primary timezone |
| is_remote_location | BOOLEAN | SLV-AI.ext_work_model_stated | Remote-only marker |

---

### dim_skill (Snowflake - SCD Type 1)

**Snowflake Hierarchy**: `skill_type → skill_category → skill_family → skill`

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| skill_key | BIGINT | SK | Surrogate key |
| skill_canonical_name | STRING | SLV-LI.skills_canonical | Canonical name (Python, AWS, Communication) |
| skill_display_name | STRING | DERIVED | Display name |
| **Snowflake FKs** | | | |
| skill_type_key | INT | STATIC | FK to dim_skill_type (HARD/SOFT) |
| skill_category_key | INT | STATIC | FK to dim_skill_category |
| skill_family_key | INT | STATIC | FK to dim_skill_family |
| **Denormalized (for performance)** | | | |
| skill_type | STRING | STATIC | HARD or SOFT |
| skill_category | STRING | STATIC | Programming, Cloud, Interpersonal, etc. |
| skill_family | STRING | SLV-LI.skills_families | Languages, Databases, Communication, etc. |
| **Attributes** | | | |
| vendor | STRING | STATIC | Apache, AWS, Google, Microsoft, NULL |
| is_emerging | BOOLEAN | STATIC | Emerging technology |
| is_technical | BOOLEAN | STATIC | Requires technical knowledge |
| market_demand_score | DECIMAL(3,2) | DERIVED | Relative demand (0-1) |
| catalog_version | STRING | SLV-LI.skills_catalog_version | Skills catalog version |

---

### dim_skill_type (Static - Snowflake)

**Source**: STATIC (pre-defined)

| skill_type_key | skill_type_name | description |
|----------------|-----------------|-------------|
| 1 | HARD | Technical, teachable, measurable skills |
| 2 | SOFT | Interpersonal, behavioral, transferable skills |
| 3 | HYBRID | Both technical and interpersonal (e.g., Technical Writing) |

---

### dim_skill_category (Static - Snowflake)

**Source**: STATIC (pre-defined)

| skill_category_key | category_name | skill_type | description |
|--------------------|---------------|------------|-------------|
| **HARD SKILL CATEGORIES** | | | |
| 1 | Programming Languages | HARD | Python, Java, Scala, SQL |
| 2 | Cloud Platforms | HARD | AWS, Azure, GCP services |
| 3 | Databases | HARD | PostgreSQL, MongoDB, Redis |
| 4 | Data Processing | HARD | Spark, Kafka, Flink |
| 5 | Orchestration | HARD | Airflow, Dagster, Prefect |
| 6 | DevOps & Infrastructure | HARD | Docker, Kubernetes, Terraform |
| 7 | BI & Visualization | HARD | Tableau, Looker, Power BI |
| 8 | ML & AI | HARD | TensorFlow, PyTorch, MLflow |
| 9 | Data Modeling | HARD | dbt, Star Schema, Data Vault |
| **SOFT SKILL CATEGORIES** | | | |
| 10 | Communication | SOFT | Verbal, written, presentation |
| 11 | Leadership | SOFT | Team management, mentoring |
| 12 | Problem Solving | SOFT | Analytical thinking, debugging |
| 13 | Collaboration | SOFT | Teamwork, cross-functional |
| 14 | Self-Management | SOFT | Time management, organization |
| 15 | Business Acumen | SOFT | Stakeholder management, domain knowledge |
| **HYBRID CATEGORIES** | | | |
| 16 | Technical Communication | HYBRID | Documentation, tech writing |
| 17 | Technical Leadership | HYBRID | Architecture decisions, code review |

---

### dim_skill_family (Static - Snowflake)

**Source**: STATIC (pre-defined)

| skill_family_key | family_name | skill_type | categories_included |
|------------------|-------------|------------|---------------------|
| **HARD SKILL FAMILIES** | | | |
| 1 | Core Programming | HARD | Programming Languages |
| 2 | Cloud & Infrastructure | HARD | Cloud Platforms, DevOps |
| 3 | Data Storage | HARD | Databases |
| 4 | Data Processing | HARD | Data Processing, Orchestration |
| 5 | Analytics & ML | HARD | BI & Visualization, ML & AI |
| 6 | Data Architecture | HARD | Data Modeling |
| **SOFT SKILL FAMILIES** | | | |
| 7 | Interpersonal | SOFT | Communication, Collaboration |
| 8 | Management | SOFT | Leadership, Self-Management |
| 9 | Analytical | SOFT | Problem Solving |
| 10 | Business | SOFT | Business Acumen |
| **HYBRID FAMILIES** | | | |
| 11 | Technical Soft Skills | HYBRID | Technical Communication, Technical Leadership |

---

### dim_seniority (Static)

**Source**: STATIC (mapped from SLV-LI.job_seniority_level, SLV-AI.inf_seniority_level)

| seniority_key | seniority_level | order | years_min | years_max | is_ic |
|---------------|-----------------|-------|-----------|-----------|-------|
| 1 | Intern | 1 | 0 | 0 | TRUE |
| 2 | Entry | 2 | 0 | 1 | TRUE |
| 3 | Junior | 3 | 1 | 3 | TRUE |
| 4 | Mid | 4 | 3 | 5 | TRUE |
| 5 | Senior | 5 | 5 | 8 | TRUE |
| 6 | Staff | 6 | 8 | 12 | TRUE |
| 7 | Principal | 7 | 12 | 20 | TRUE |
| 8 | Lead | 8 | 5 | 15 | FALSE |
| 9 | Manager | 9 | 5 | 15 | FALSE |
| 10 | Director | 10 | 10 | 20 | FALSE |

---

### dim_job_family (Static)

**Source**: STATIC (mapped from SLV-AI.inf_job_family, SLV-AI.inf_sub_specialty)

| job_family_key | job_family_name | sub_specialty |
|----------------|-----------------|---------------|
| 1 | Data Engineer | Batch ETL |
| 2 | Data Engineer | Streaming/Real-time |
| 3 | Data Engineer | Data Warehouse |
| 4 | Data Engineer | Data Lakehouse |
| 5 | Analytics Engineer | dbt/Modeling |
| 6 | ML Engineer | MLOps |
| 7 | ML Engineer | Feature Engineering |
| 8 | Data Scientist | Research |
| 9 | Data Scientist | Applied |
| 10 | Data Analyst | BI/Reporting |
| 11 | Platform Engineer | Data Platform |
| 12 | Data Architect | Enterprise |

---

### dim_work_model (Static)

**Source**: STATIC (mapped from SLV-AI.ext_work_model_stated)

| work_model_key | work_model_name | remote_pct_min | remote_pct_max |
|----------------|-----------------|----------------|----------------|
| 1 | Fully Remote | 100 | 100 |
| 2 | Remote with Restrictions | 80 | 100 |
| 3 | Hybrid | 20 | 80 |
| 4 | On-Site | 0 | 20 |
| 5 | Flexible | 0 | 100 |

---

### dim_employment_type (Static)

**Source**: STATIC (mapped from SLV-LI.job_employment_type, SLV-AI.ext_employment_type_stated)

| employment_type_key | employment_type_name | is_permanent |
|---------------------|----------------------|--------------|
| 1 | Full-Time | TRUE |
| 2 | Contract | FALSE |
| 3 | Contract-to-Hire | FALSE |
| 4 | Part-Time | TRUE |
| 5 | Internship | FALSE |
| 6 | Freelance | FALSE |

---

### dim_contract_type (Static)

**Source**: STATIC (mapped from SLV-AI.ext_contract_type, SLV-AI.inf_w2_vs_1099)

| contract_type_key | contract_type_name | has_benefits |
|-------------------|--------------------|--------------|
| 1 | W-2 | TRUE |
| 2 | C2C | FALSE |
| 3 | 1099 | FALSE |
| 4 | Any | NULL |
| 5 | Unknown | NULL |

---

### dim_cloud_platform (Static)

**Source**: STATIC (mapped from SLV-AI.inf_primary_cloud)

| cloud_platform_key | cloud_platform_name | vendor |
|--------------------|---------------------|--------|
| 1 | AWS | Amazon |
| 2 | Azure | Microsoft |
| 3 | GCP | Google |
| 4 | Multi-Cloud | Multiple |
| 5 | On-Premises | N/A |
| 6 | Hybrid | Multiple |
| 7 | Unknown | N/A |

---

## AI Enrichment Dimensions (New)

### dim_education (Static)

**Source**: STATIC (mapped from SLV-AI.ext_education_level)

| education_key | education_level | education_order | typical_years |
|---------------|-----------------|-----------------|---------------|
| 1 | High School | 1 | 0 |
| 2 | Bootcamp | 2 | 0 |
| 3 | Associates | 3 | 2 |
| 4 | Bachelors | 4 | 4 |
| 5 | Masters | 5 | 6 |
| 6 | PhD | 6 | 10 |
| 7 | Not Mentioned | 0 | NULL |

---

### dim_visa_status (Static)

**Source**: STATIC (mapped from SLV-AI.ext_visa_sponsorship_stated, SLV-AI.inf_h1b_friendly, SLV-AI.inf_citizenship_required)

| visa_status_key | visa_category | h1b_friendly | opt_cpt_friendly | citizenship_required |
|-----------------|---------------|--------------|------------------|----------------------|
| 1 | Will Sponsor | TRUE | TRUE | FALSE |
| 2 | H1B Only | TRUE | FALSE | FALSE |
| 3 | Must Be Authorized | FALSE | FALSE | FALSE |
| 4 | US Citizen Only | FALSE | FALSE | TRUE |
| 5 | US/GC Only | FALSE | FALSE | TRUE |
| 6 | Any Work Auth | TRUE | TRUE | FALSE |
| 7 | Not Mentioned | NULL | NULL | NULL |

---

### dim_leadership (Static)

**Source**: STATIC (mapped from SLV-AI.inf_leadership_expectation)

| leadership_key | leadership_level | is_ic | manages_people | manages_tech |
|----------------|------------------|-------|----------------|--------------|
| 1 | Individual Contributor | TRUE | FALSE | FALSE |
| 2 | Tech Lead (IC) | TRUE | FALSE | TRUE |
| 3 | Architect | TRUE | FALSE | TRUE |
| 4 | People Manager | FALSE | TRUE | FALSE |
| 5 | Tech + People Lead | FALSE | TRUE | TRUE |
| 6 | Not Mentioned | NULL | NULL | NULL |

---

### dim_orchestrator (Static)

**Source**: STATIC (mapped from SLV-AI.inf_orchestrator_category)

| orchestrator_key | orchestrator_category | examples |
|------------------|----------------------|----------|
| 1 | Airflow-like | Airflow, MWAA, Astronomer |
| 2 | Spark Native | Databricks Workflows, EMR |
| 3 | dbt Core | dbt Cloud, dbt Core |
| 4 | Cloud Native | AWS Step Functions, GCP Workflows |
| 5 | Dagster/Prefect | Dagster, Prefect, Mage |
| 6 | Luigi/Argo | Luigi, Argo Workflows |
| 7 | Not Mentioned | N/A |

---

### dim_storage_layer (Static)

**Source**: STATIC (mapped from SLV-AI.inf_storage_layer)

| storage_layer_key | storage_type | is_cloud_native |
|-------------------|--------------|-----------------|
| 1 | Data Warehouse | TRUE |
| 2 | Data Lake | TRUE |
| 3 | Lakehouse | TRUE |
| 4 | Mixed | TRUE |
| 5 | On-Premises | FALSE |
| 6 | Not Mentioned | NULL |

---

### dim_processing_paradigm (Static)

**Source**: STATIC (mapped from SLV-AI.inf_processing_paradigm)

| processing_key | paradigm_name | real_time |
|----------------|---------------|-----------|
| 1 | Batch Only | FALSE |
| 2 | Streaming Only | TRUE |
| 3 | Hybrid (Batch + Stream) | TRUE |
| 4 | Micro-batch | FALSE |
| 5 | Not Mentioned | NULL |

---

### dim_company_stage (Static)

**Source**: STATIC (mapped from SLV-AI.anl_company_stage_inferred)

| company_stage_key | stage_name | typical_size | has_funding |
|-------------------|------------|--------------|-------------|
| 1 | Startup Seed | 1-20 | TRUE |
| 2 | Startup Series A/B | 20-100 | TRUE |
| 3 | Growth Stage | 100-500 | TRUE |
| 4 | Established Tech | 500-5000 | TRUE |
| 5 | Enterprise | 5000+ | FALSE |
| 6 | Not Mentioned | NULL | NULL |

---

### dim_team_size (Static)

**Source**: STATIC (mapped from SLV-AI.anl_team_size_signals)

| team_size_key | team_size_bucket | min_size | max_size |
|---------------|------------------|----------|----------|
| 1 | Solo | 1 | 1 |
| 2 | Small (2-5) | 2 | 5 |
| 3 | Medium (6-15) | 6 | 15 |
| 4 | Large (16-50) | 16 | 50 |
| 5 | Very Large (50+) | 51 | 500 |
| 6 | Not Mentioned | NULL | NULL |

---

### dim_hiring_context (Static)

**Source**: STATIC (mapped from SLV-AI.anl_role_creation_type)

| hiring_context_key | context_type | is_growth | is_urgent |
|--------------------|--------------|-----------|-----------|
| 1 | New Headcount | TRUE | FALSE |
| 2 | Backfill | FALSE | TRUE |
| 3 | Team Expansion | TRUE | FALSE |
| 4 | New Function | TRUE | FALSE |
| 5 | Contractor Conversion | FALSE | FALSE |
| 6 | Not Mentioned | NULL | NULL |

---

### dim_security_clearance (Static)

**Source**: STATIC (mapped from SLV-AI.ext_security_clearance_stated)

| security_key | clearance_level | required |
|--------------|-----------------|----------|
| 1 | Required | TRUE |
| 2 | Preferred | FALSE |
| 3 | Not Mentioned | NULL |

---

### dim_pay_type (Static) - NEW

**Source**: STATIC (mapped from SLV-AI.ext_pay_type)

| pay_type_key | pay_type_name | is_salary | is_hourly |
|--------------|---------------|-----------|-----------|
| 1 | Annual Salary | TRUE | FALSE |
| 2 | Hourly Rate | FALSE | TRUE |
| 3 | Daily Rate | FALSE | FALSE |
| 4 | Project-Based | FALSE | FALSE |
| 5 | Mixed | TRUE | TRUE |
| 6 | Not Disclosed | NULL | NULL |

---

### dim_start_urgency (Static) - NEW

**Source**: STATIC (mapped from SLV-AI.ext_start_date)

| start_urgency_key | start_type | order | days_range |
|-------------------|------------|-------|------------|
| 1 | Immediate | 1 | 0-7 |
| 2 | Within 2 Weeks | 2 | 7-14 |
| 3 | Within Month | 3 | 14-30 |
| 4 | Flexible | 4 | 30-90 |
| 5 | Specific Date | 5 | NULL |
| 6 | Not Mentioned | 0 | NULL |

---

### dim_geo_restriction (Static) - NEW

**Source**: STATIC (mapped from SLV-AI.ext_geo_restriction_type)

| geo_restriction_key | restriction_type | scope |
|---------------------|------------------|-------|
| 1 | US Only | country |
| 2 | EU Only | region |
| 3 | Specific Countries | country |
| 4 | LATAM | region |
| 5 | Global | worldwide |
| 6 | Not Mentioned | NULL |

---

### dim_pto_policy (Static) - NEW

**Source**: STATIC (mapped from SLV-AI.ext_pto_policy)

| pto_policy_key | policy_type | days_estimate |
|----------------|-------------|---------------|
| 1 | Unlimited | NULL |
| 2 | Generous | 25-30 |
| 3 | Standard | 15-20 |
| 4 | Limited | 10-15 |
| 5 | Not Mentioned | NULL |

---

## Pass 2 Inference Dimensions (NEW)

### dim_remote_restriction (Static)

**Source**: STATIC (mapped from SLV-AI.inf_remote_restriction)

| remote_restriction_key | restriction_type | description |
|------------------------|------------------|-------------|
| 1 | Same Country | Must work in same country |
| 2 | Same Timezone | +/- 3 hours timezone |
| 3 | Anywhere | Fully global remote |
| 4 | Not Mentioned | NULL |

---

### dim_timezone (Static)

**Source**: STATIC (mapped from SLV-AI.inf_timezone_focus)

| timezone_key | timezone_name | utc_range |
|--------------|---------------|-----------|
| 1 | Americas | UTC-10 to UTC-3 |
| 2 | Europe | UTC-1 to UTC+4 |
| 3 | APAC | UTC+5 to UTC+12 |
| 4 | Global | All |
| 5 | Not Mentioned | NULL |

---

### dim_growth_clarity (Static)

**Source**: STATIC (mapped from SLV-AI.inf_growth_path_clarity)

| growth_clarity_key | clarity_level | description |
|--------------------|---------------|-------------|
| 1 | Explicit | Clear progression path stated |
| 2 | Implied | Growth hints but not explicit |
| 3 | Vague | No clear growth path |
| 4 | Not Mentioned | NULL |

---

### dim_requirement_strictness (Static)

**Source**: STATIC (mapped from SLV-AI.inf_requirement_strictness)

| strictness_key | strictness_level | flexibility |
|----------------|------------------|-------------|
| 1 | Low | Flexible, will train |
| 2 | Medium | Some requirements firm |
| 3 | High | All requirements mandatory |
| 4 | Not Mentioned | NULL |

---

### dim_benefits_level (Static)

**Source**: STATIC (mapped from SLV-AI.inf_benefits_level)

| benefits_level_key | level_name | score_range |
|--------------------|------------|-------------|
| 1 | Comprehensive | 8-10 |
| 2 | Standard | 5-7 |
| 3 | Basic | 2-4 |
| 4 | Not Mentioned | NULL |

---

## Pass 3 Analysis Dimensions (NEW)

### dim_maturity_level (Static)

**Source**: STATIC (mapped from SLV-AI.anl_data_maturity_level)

| maturity_level_key | maturity_name | score | description |
|--------------------|---------------|-------|-------------|
| 1 | Ad-Hoc | 1 | No formal processes |
| 2 | Developing | 2 | Some processes emerging |
| 3 | Defined | 3 | Standard processes |
| 4 | Managed | 4 | Measured & controlled |
| 5 | Optimizing | 5 | Continuous improvement |
| 6 | Not Mentioned | 0 | NULL |

---

### dim_role_clarity (Static)

**Source**: STATIC (mapped from SLV-AI.anl_role_clarity)

| role_clarity_key | clarity_level | red_flag_level |
|------------------|---------------|----------------|
| 1 | Clear | LOW |
| 2 | Vague | MEDIUM |
| 3 | Multi-Role | HIGH |
| 4 | Not Mentioned | NULL |

---

### dim_manager_level (Static)

**Source**: STATIC (mapped from SLV-AI.anl_manager_level_inferred)

| manager_level_key | manager_type | seniority_order |
|-------------------|--------------|-----------------|
| 1 | Director+ | 4 |
| 2 | Senior Manager | 3 |
| 3 | Manager | 2 |
| 4 | Tech Lead | 1 |
| 5 | Not Mentioned | 0 |

---

### dim_team_velocity (Static)

**Source**: STATIC (mapped from SLV-AI.anl_team_growth_velocity)

| team_velocity_key | velocity_type | growth_rate |
|-------------------|---------------|-------------|
| 1 | Rapid Expansion | > 50% YoY |
| 2 | Steady Growth | 10-50% YoY |
| 3 | Stable | < 10% YoY |
| 4 | Not Mentioned | NULL |

---

### dim_reporting_structure (Static)

**Source**: STATIC (mapped from SLV-AI.anl_reporting_structure)

| reporting_key | reports_to | level_proximity |
|---------------|------------|-----------------|
| 1 | Reports to CTO | Executive |
| 2 | Reports to Director of Data | Director |
| 3 | Reports to Manager | Manager |
| 4 | Reports to Tech Lead | Peer |
| 5 | Not Mentioned | NULL |

---

### dim_ai_integration (Static)

**Source**: STATIC (mapped from SLV-AI.anl_ai_integration_level)

| ai_integration_key | integration_level | order |
|--------------------|-------------------|-------|
| 1 | None | 0 |
| 2 | Basic ML | 1 |
| 3 | Advanced ML | 2 |
| 4 | MLOps | 3 |
| 5 | GenAI Focus | 4 |
| 6 | Not Mentioned | NULL |

---

### dim_hiring_urgency (Static)

**Source**: STATIC (mapped from SLV-AI.anl_hiring_urgency)

| hiring_urgency_key | urgency_type | priority |
|--------------------|--------------|----------|
| 1 | Immediate | 4 |
| 2 | ASAP | 3 |
| 3 | Normal | 2 |
| 4 | Pipeline | 1 |
| 5 | Not Mentioned | 0 |

---

### dim_competition (Static)

**Source**: STATIC (mapped from SLV-AI.anl_competition_level)

| competition_key | competition_level | order |
|-----------------|-------------------|-------|
| 1 | Low | 1 |
| 2 | Medium | 2 |
| 3 | High | 3 |
| 4 | Very High | 4 |
| 5 | Not Mentioned | 0 |

---

## Bridge Tables (Many-to-Many)

All bridge tables share this common structure:

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| bridge_key | BIGINT | SK | Surrogate key (PK) |
| job_posting_key | BIGINT | SK | FK to fact_job_posting |
| {entity}_key | BIGINT | SK | FK to related dimension |
| confidence_score | DECIMAL(3,2) | SLV-AI.*_confidence | Confidence (0-1) |

### Skills Bridge (Snowflake)

#### bridge_job_skills
- **Entity**: dim_skill (snowflake with dim_skill_type, dim_skill_category, dim_skill_family)
- **Extra columns**: requirement_type, skill_source, skill_type (denormalized), skill_category (denormalized)
- **Source**: `SLV-AI.ext_must_have_hard_skills[]`, `SLV-AI.ext_nice_to_have_hard_skills[]`, `SLV-AI.ext_must_have_soft_skills[]`, `SLV-AI.ext_nice_to_have_soft_skills[]`
- **Note**: Single unified bridge - filter by `skill_type` for HARD/SOFT/HYBRID

#### bridge_job_certifications
- **Entity**: dim_certification (AWS, GCP, Azure, Kubernetes, etc.)
- **Source**: `SLV-AI.ext_certifications_mentioned[]`

### Tech Stack Bridges

#### bridge_job_cloud_stack
- **Entity**: dim_cloud_platform
- **Extra columns**: is_primary (boolean)
- **Source**: `SLV-AI.inf_primary_cloud`, `SLV-AI.inf_secondary_clouds[]`

#### bridge_job_ml_tools
- **Entity**: dim_ml_tool (SageMaker, MLflow, Feast, Vertex AI, etc.)
- **Source**: `SLV-AI.anl_ml_tools_expected[]`

### Benefits & Career Bridges

#### bridge_job_benefits
- **Entity**: dim_benefit (health, dental, 401k, equity, unlimited_pto, etc.)
- **Source**: `SLV-AI.ext_benefits_mentioned[]`

#### bridge_job_career_tracks
- **Entity**: dim_career_track (ic_track, management_track, specialist_track, architect_track)
- **Source**: `SLV-AI.inf_career_tracks_available[]`

### Geographic Bridges

#### bridge_job_geo_restrictions
- **Entity**: dim_country
- **Extra columns**: restriction_type (allowed/excluded)
- **Source**: `SLV-AI.ext_allowed_countries[]`, `SLV-AI.ext_excluded_countries[]`

#### bridge_job_us_state_restrictions
- **Entity**: dim_us_state
- **Extra columns**: restriction_type (allowed/excluded)
- **Source**: `SLV-AI.ext_us_state_restrictions[]`

### Culture & Quality Bridges

#### bridge_job_maturity_signals
- **Entity**: dim_maturity_signal (modern_data_stack, cicd_practices, data_quality_testing, etc.)
- **Source**: `SLV-AI.anl_maturity_signals[]`

#### bridge_job_dev_practices
- **Entity**: dim_dev_practice (code_review, pair_programming, tdd, ci_cd, monitoring)
- **Source**: `SLV-AI.anl_dev_practices_mentioned[]`

#### bridge_job_culture_signals
- **Entity**: dim_culture_signal (open_source, tech_blogs, conference_speaking, hackathons)
- **Source**: `SLV-AI.anl_tech_culture_signals[]`

### Summary & Recommendation Bridges

#### bridge_job_strengths
- **Entity**: dim_strength_category (competitive_compensation, modern_tech_stack, remote_friendly, etc.)
- **Source**: `SLV-AI.anl_strengths[]`

#### bridge_job_concerns
- **Entity**: dim_concern_category (vague_requirements, overtime_likely, scope_creep_risk, etc.)
- **Source**: `SLV-AI.anl_concerns[]`

#### bridge_job_best_fit
- **Entity**: dim_best_fit_category (senior_data_engineers, ml_engineers, startup_enthusiasts, etc.)
- **Source**: `SLV-AI.anl_best_fit_for[]`

#### bridge_job_probes
- **Entity**: dim_probe_category (work_hour_expectations, career_growth_path, team_structure, etc.)
- **Source**: `SLV-AI.anl_red_flags_to_probe[]` (questions to ask in interview)

#### bridge_job_leverage
- **Entity**: dim_leverage_category (rare_skill_match, domain_expertise, competing_offers, etc.)
- **Source**: `SLV-AI.anl_negotiation_leverage[]` (negotiation points)

---

## Supporting Dimensions for Bridges

### dim_certification

**Source**: STATIC (populated from `SLV-AI.ext_certifications_mentioned[]`)

| cert_key | cert_name | vendor | category |
|----------|-----------|--------|----------|
| 1 | AWS Solutions Architect | AWS | Cloud |
| 2 | AWS Data Engineer | AWS | Data |
| 3 | GCP Professional Data Engineer | GCP | Data |
| 4 | Azure Data Engineer | Azure | Data |
| 5 | Databricks Certified | Databricks | Data |
| 6 | Snowflake SnowPro | Snowflake | Data |
| 7 | Kubernetes CKA/CKAD | CNCF | DevOps |
| 8 | dbt Analytics Engineer | dbt Labs | Analytics |

### dim_ml_tool (NEW)

**Source**: STATIC (populated from `SLV-AI.anl_ml_tools_expected[]`)

| ml_tool_key | tool_name | vendor | category |
|-------------|-----------|--------|----------|
| 1 | SageMaker | AWS | MLOps |
| 2 | MLflow | Databricks | Experiment Tracking |
| 3 | Feast | Community | Feature Store |
| 4 | Vertex AI | GCP | MLOps |
| 5 | Azure ML | Microsoft | MLOps |
| 6 | Kubeflow | Google | Orchestration |
| 7 | Weights & Biases | W&B | Experiment Tracking |
| 8 | Tecton | Tecton | Feature Store |
| 9 | Metaflow | Netflix | Orchestration |
| 10 | Ray | Anyscale | Compute |

### dim_us_state (NEW)

**Source**: STATIC (populated from `SLV-AI.ext_us_state_restrictions[]`)

| state_key | state_code | state_name | region |
|-----------|------------|------------|--------|
| 1 | CA | California | West |
| 2 | NY | New York | Northeast |
| 3 | TX | Texas | South |
| 4 | WA | Washington | West |
| 5 | ... | ... (all 50 states) | ... |

### dim_benefit

**Source**: STATIC (populated from `SLV-AI.ext_benefits_mentioned[]`)

| benefit_key | benefit_name | category |
|-------------|--------------|----------|
| 1 | Health Insurance | Health |
| 2 | Dental/Vision | Health |
| 3 | 401k Match | Retirement |
| 4 | Stock/Equity | Compensation |
| 5 | Unlimited PTO | Time Off |
| 6 | Learning Budget | Development |
| 7 | Conference Budget | Development |
| 8 | Remote Stipend | Remote |
| 9 | Hardware Choice | Equipment |

### dim_strength_category

**Source**: STATIC (populated from `SLV-AI.anl_strengths[]`)

| strength_key | category_name | description |
|--------------|---------------|-------------|
| 1 | competitive_compensation | Above market salary |
| 2 | transparent_salary | Salary clearly disclosed |
| 3 | modern_tech_stack | Modern tools and technologies |
| 4 | learning_opportunities | Growth and learning culture |
| 5 | work_life_balance | Good WLB indicators |
| 6 | career_growth | Clear advancement path |
| 7 | remote_friendly | Remote/hybrid options |
| 8 | strong_benefits | Comprehensive benefits |
| 9 | visa_friendly | Visa sponsorship available |
| 10 | equity_upside | Meaningful equity package |

### dim_concern_category

**Source**: STATIC (populated from `SLV-AI.anl_concerns[]`)

| concern_key | category_name | risk_level |
|-------------|---------------|------------|
| 1 | overtime_likely | HIGH |
| 2 | no_visa_sponsorship | MEDIUM |
| 3 | vague_requirements | MEDIUM |
| 4 | scope_creep_risk | HIGH |
| 5 | low_salary | MEDIUM |
| 6 | legacy_tech_stack | LOW |
| 7 | unclear_growth_path | MEDIUM |
| 8 | high_turnover_signals | HIGH |
| 9 | skill_inflation | MEDIUM |
| 10 | startup_risk | MEDIUM |

### dim_best_fit_category (NEW)

**Source**: STATIC (populated from `SLV-AI.anl_best_fit_for[]`)

| best_fit_key | category_name | target_audience |
|--------------|---------------|-----------------|
| 1 | senior_data_engineers | 5+ years DE experience |
| 2 | ml_engineers | ML/MLOps background |
| 3 | startup_enthusiasts | High risk tolerance |
| 4 | career_changers | Non-traditional path |
| 5 | remote_workers | Location flexibility needed |
| 6 | visa_seekers | Needs sponsorship |
| 7 | tech_leads | Leadership aspirations |
| 8 | specialists | Deep domain expertise |

### dim_probe_category (NEW)

**Source**: STATIC (populated from `SLV-AI.anl_red_flags_to_probe[]`)

| probe_key | category_name | question_topic |
|-----------|---------------|----------------|
| 1 | work_hour_expectations | On-call, overtime expectations |
| 2 | career_growth_path | Promotion timeline and criteria |
| 3 | team_structure | Team composition and dynamics |
| 4 | tech_debt_reality | Actual state of codebase |
| 5 | budget_autonomy | Decision-making authority |
| 6 | hiring_reason | Why position is open |
| 7 | success_metrics | How performance is measured |
| 8 | remote_policy_details | WFH flexibility specifics |

### dim_leverage_category (NEW)

**Source**: STATIC (populated from `SLV-AI.anl_negotiation_leverage[]`)

| leverage_key | category_name | negotiation_power |
|--------------|---------------|-------------------|
| 1 | rare_skill_match | Unique skill combination |
| 2 | domain_expertise | Industry-specific knowledge |
| 3 | competing_offers | Multiple offers in hand |
| 4 | immediate_availability | Can start quickly |
| 5 | referral_connection | Internal referral |
| 6 | location_flexibility | Willing to relocate |
| 7 | salary_data | Market rate knowledge |
| 8 | certifications | Relevant certifications |

---

## Aggregation Tables

### agg_daily_job_metrics

**Grain**: day × seniority × job_family × country × work_model

| Column | Type | Description |
|--------|------|-------------|
| date_key | INT | YYYYMMDD |
| seniority_key | INT | FK |
| job_family_key | INT | FK |
| country_code | STRING | ISO country |
| work_model_key | INT | FK |
| job_count | INT | Count of jobs |
| jobs_with_salary | INT | Jobs with salary info |
| jobs_remote | INT | Remote jobs |
| jobs_visa_sponsor | INT | Visa sponsor jobs |
| total_applicants | BIGINT | Sum of applicants |
| salary_avg | DECIMAL | Average salary (USD) |
| salary_median | DECIMAL | Median salary (USD) |
| salary_p25 | DECIMAL | 25th percentile |
| salary_p75 | DECIMAL | 75th percentile |
| avg_recommendation_score | DECIMAL | Avg rec score |

**Partitioning**: `year/month`

---

### agg_weekly_job_metrics

Same schema as daily, grain: week × dimensions

---

### agg_monthly_job_metrics

Same schema as daily, grain: month × dimensions

---

### agg_skills_demand

**Grain**: week × skill × seniority × job_family

| Column | Type | Description |
|--------|------|-------------|
| week_key | INT | YYYYWW |
| skill_key | BIGINT | FK |
| seniority_key | INT | FK |
| job_family_key | INT | FK |
| skill_name | STRING | Denormalized |
| skill_family | STRING | Denormalized |
| job_count | INT | Jobs requiring skill |
| required_count | INT | As must-have |
| nice_to_have_count | INT | As nice-to-have |
| avg_salary_usd | DECIMAL | Avg salary |
| rank_overall | INT | Overall rank |
| growth_rate_4w | DECIMAL | 4-week growth % |

---

### agg_salary_benchmarks

**Grain**: month × seniority × job_family × country × work_model

| Column | Type | Description |
|--------|------|-------------|
| month_key | INT | YYYYMM |
| seniority_key | INT | FK |
| job_family_key | INT | FK |
| country_code | STRING | ISO country |
| work_model_key | INT | FK |
| sample_size | INT | Number of jobs |
| salary_p10 | DECIMAL | 10th percentile |
| salary_p25 | DECIMAL | 25th percentile |
| salary_p50 | DECIMAL | Median |
| salary_p75 | DECIMAL | 75th percentile |
| salary_p90 | DECIMAL | 90th percentile |
| salary_avg | DECIMAL | Average |
| mom_change_pct | DECIMAL | Month-over-month % |
| yoy_change_pct | DECIMAL | Year-over-year % |

---

### agg_company_hiring

**Grain**: month × company

| Column | Type | Description |
|--------|------|-------------|
| month_key | INT | YYYYMM |
| company_key | BIGINT | FK |
| company_name | STRING | Denormalized |
| company_size_bucket | STRING | Denormalized |
| industry_primary | STRING | Denormalized |
| new_job_postings | INT | Jobs posted |
| active_job_postings | INT | Currently active |
| unique_job_titles | INT | Distinct titles |
| unique_locations | INT | Distinct locations |
| pct_remote | DECIMAL | % remote jobs |
| avg_salary_usd | DECIMAL | Avg salary offered |
| hiring_velocity_rank | INT | Rank among companies |

---

### agg_posting_time_analysis (NEW)

**Grain**: day_of_week × hour × job_family × seniority

**Purpose**: Analyze when jobs are posted and best hours to apply

| Column | Type | Description |
|--------|------|-------------|
| day_of_week | INT | 1-7 (Monday-Sunday) |
| day_name | STRING | Monday, Tuesday, etc. |
| hour_24 | INT | 0-23 |
| time_of_day | STRING | Morning/Afternoon/Evening |
| job_family_key | INT | FK |
| seniority_key | INT | FK |
| job_count | INT | Jobs posted at this time |
| pct_of_total | DECIMAL | % of all jobs |
| avg_applicants | DECIMAL | Avg applicants for jobs posted at this time |
| avg_time_to_100_applicants_hrs | DECIMAL | Avg hours to reach 100 applicants |
| competition_score | DECIMAL | Relative competition (0-1) |
| is_peak_posting_time | BOOLEAN | Top 20% posting times |
| is_low_competition_time | BOOLEAN | Bottom 20% competition |
| recommendation_score | DECIMAL | Best time to apply score (0-1) |

**Key Insights This Table Provides**:
- When do companies post jobs? (day of week + hour)
- Which posting times have lower competition?
- Best time to apply for maximum visibility
- Peak posting hours by job family

---

### agg_hourly_posting_summary (NEW)

**Grain**: hour × timezone

**Purpose**: Simple hourly distribution by timezone

| Column | Type | Description |
|--------|------|-------------|
| hour_24 | INT | 0-23 |
| hour_label | STRING | 9 AM, 2 PM, etc. |
| time_of_day | STRING | Morning/Afternoon/Evening |
| timezone | STRING | Americas/Europe/APAC |
| job_count | INT | Total jobs posted |
| pct_of_total | DECIMAL | % of all jobs |
| avg_applicants_24h | DECIMAL | Avg applicants in first 24h |
| rank_by_volume | INT | Rank by posting volume |
| rank_by_low_competition | INT | Rank by low competition |

---

## Confidence Details Table

### job_confidence_details

**Grain**: job × field (from Pass 2 and Pass 3)

| Column | Type | Description |
|--------|------|-------------|
| job_posting_key | BIGINT | FK to fact_job_posting |
| field_name | STRING | Field name (e.g., inf_seniority_level) |
| field_value | STRING | Inferred/analyzed value |
| confidence_score | DECIMAL(3,2) | Confidence (0-1) |
| evidence | STRING | Supporting evidence text |
| source | STRING | pass1_derived, inferred, combined |
| pass_number | INT | 2 or 3 |

**Partitioning**: `year/month`

---

## Partitioning Strategy

| Table | Partition Keys | Projection |
|-------|----------------|------------|
| fact_job_posting | year/month/day | 2024-2030 |
| bridge_job_skills | year/month | 2024-2030 |
| agg_daily_job_metrics | year/month | 2024-2030 |
| agg_weekly_job_metrics | year | 2024-2030 |
| agg_monthly_job_metrics | year | 2024-2030 |
| agg_skills_demand | year/month | 2024-2030 |
| agg_salary_benchmarks | year | 2024-2030 |
| agg_company_hiring | year | 2024-2030 |
| job_confidence_details | year/month | 2024-2030 |
| dim_* | none | Static/small |

**Storage**: S3 Parquet (Snappy compression)
**Catalog**: AWS Glue with Partition Projection

---

## Implementation Phases

### Phase 1: Foundation (Static Dimensions)
- [ ] Create Gold S3 bucket structure (`s3://gold-bucket/facts/`, `/dims/`, `/bridges/`, `/aggs/`)
- [ ] Create Core Static Dimensions:
  - dim_date (pre-populate 2020-2030)
  - dim_time (pre-populate 0-23 hours with time_of_day buckets)
  - dim_seniority, dim_job_family, dim_work_model
  - dim_employment_type, dim_contract_type, dim_cloud_platform
- [ ] Create Pass 1 Static Dimensions:
  - dim_education, dim_pay_type, dim_start_urgency
  - dim_geo_restriction, dim_pto_policy, dim_security_clearance
- [ ] Create Pass 2 Static Dimensions:
  - dim_visa_status, dim_leadership, dim_orchestrator
  - dim_storage_layer, dim_processing_paradigm
  - dim_remote_restriction, dim_timezone, dim_growth_clarity
  - dim_requirement_strictness, dim_benefits_level
- [ ] Create Pass 3 Static Dimensions:
  - dim_maturity_level, dim_role_clarity, dim_manager_level
  - dim_team_velocity, dim_reporting_structure, dim_ai_integration
  - dim_company_stage, dim_team_size, dim_hiring_context
  - dim_hiring_urgency, dim_competition
- [ ] Deploy Glue catalog tables for all dimensions

### Phase 2: Dynamic Dimensions
- [ ] Implement dim_skill_type, dim_skill_family, dim_skill_category (snowflake static tables)
- [ ] Implement dim_skill ETL (unified hard + soft skills with snowflake FKs)
  - Map ext_must_have_hard_skills → skill_type = HARD
  - Map ext_must_have_soft_skills → skill_type = SOFT
  - Classify hybrid skills (Technical Writing, etc.)
- [ ] Implement dim_company ETL (SCD2 from linkedin_companies)
- [ ] Implement dim_location ETL (from job locations)
- [ ] Implement dim_certification (from ext_certifications_mentioned)
- [ ] Implement dim_ml_tool (from anl_ml_tools_expected)
- [ ] Implement dim_benefit (from ext_benefits_mentioned)
- [ ] Implement dim_us_state (all 50 US states)
- [ ] Implement recommendation dimensions:
  - dim_strength_category, dim_concern_category
  - dim_best_fit_category, dim_probe_category, dim_leverage_category
- [ ] Implement signal dimensions:
  - dim_maturity_signal, dim_dev_practice, dim_culture_signal, dim_career_track

### Phase 3: Fact Table
- [ ] Implement fact_job_posting ETL (join all sources)
- [ ] Implement currency conversion (to USD) for salary, hourly, daily rates
- [ ] Implement deduplication logic (job_posting_id + source_system)
- [ ] Map all 37 dimension keys
- [ ] Calculate all score measures from Pass 3
- [ ] Set all boolean flags from Pass 1/2/3

### Phase 4: Bridge Tables (Skills & Tech Stack)
- [ ] Implement bridge_job_skills (unified - explode all skill arrays)
  - Hard: ext_must_have_hard_skills[], ext_nice_to_have_hard_skills[]
  - Soft: ext_must_have_soft_skills[], ext_nice_to_have_soft_skills[]
  - Denormalize skill_type, skill_category, skill_family for performance
- [ ] Implement bridge_job_certifications
- [ ] Implement bridge_job_cloud_stack
- [ ] Implement bridge_job_ml_tools
- [ ] Implement bridge_job_benefits
- [ ] Implement bridge_job_career_tracks

### Phase 5: Bridge Tables (Geography & Culture)
- [ ] Implement bridge_job_geo_restrictions
- [ ] Implement bridge_job_us_state_restrictions
- [ ] Implement bridge_job_maturity_signals
- [ ] Implement bridge_job_dev_practices
- [ ] Implement bridge_job_culture_signals

### Phase 6: Bridge Tables (Recommendations)
- [ ] Implement bridge_job_strengths
- [ ] Implement bridge_job_concerns
- [ ] Implement bridge_job_best_fit
- [ ] Implement bridge_job_probes
- [ ] Implement bridge_job_leverage

### Phase 7: Aggregations
- [ ] Implement agg_daily_job_metrics
- [ ] Implement agg_weekly_job_metrics
- [ ] Implement agg_monthly_job_metrics
- [ ] Implement agg_skills_demand (hard + soft skills)
- [ ] Implement agg_salary_benchmarks
- [ ] Implement agg_company_hiring
- [ ] Implement agg_posting_time_analysis (best time to apply)
- [ ] Implement agg_hourly_posting_summary (hourly distribution by timezone)

### Phase 8: Confidence & Quality
- [ ] Implement job_confidence_details ETL
- [ ] Add data quality checks (Great Expectations or dbt tests)
- [ ] Create monitoring dashboards
- [ ] Document ETL dependencies and lineage

---

## Summary

| Category | Count | Examples |
|----------|-------|----------|
| **Fact Tables** | 1 | fact_job_posting |
| **Core Dimensions** | 11 | date, time, company, location, skill, seniority, job_family, work_model, employment, contract, cloud |
| **Skill Snowflake Dims** | 3 | **dim_skill_type** (HARD/SOFT/HYBRID), **dim_skill_category**, **dim_skill_family** |
| **Pass 1 Dimensions** | 6 | education, pay_type, start_urgency, geo_restriction, pto_policy, security_clearance |
| **Pass 2 Dimensions** | 10 | visa_status, leadership, orchestrator, storage_layer, processing_paradigm, remote_restriction, timezone, growth_clarity, requirement_strictness, benefits_level |
| **Pass 3 Dimensions** | 11 | maturity_level, role_clarity, manager_level, team_velocity, reporting_structure, ai_integration, company_stage, team_size, hiring_context, hiring_urgency, competition |
| **Bridge Supporting Dims** | 13 | certification, ml_tool, us_state, benefit, career_track, strength_category, concern_category, best_fit_category, probe_category, leverage_category, maturity_signal, dev_practice, culture_signal |
| **Bridge Tables** | 16 | **skills** (unified), certifications, cloud_stack, ml_tools, benefits, career_tracks, geo_restrictions, us_state_restrictions, maturity_signals, dev_practices, culture_signals, strengths, concerns, best_fit, probes, leverage |
| **Aggregation Tables** | 8 | daily/weekly/monthly metrics, skills demand, salary benchmarks, company hiring, posting_time_analysis, hourly_posting_summary |
| **Confidence Table** | 1 | job_confidence_details |
| **Total Tables** | **81** | Complete dimensional model with skills snowflake + time analysis |

### Field Coverage Summary

| AI Pass | Source Fields | Dimensions | Bridges | Flags | Measures |
|---------|---------------|------------|---------|-------|----------|
| Pass 1 (Extraction) | ~57 | 6 | 5 | 8 | 8 |
| Pass 2 (Inference) | ~100 | 10 | 2 | 2 | 0 |
| Pass 3 (Analysis) | ~124 | 11 | 10 | 5 | 9 |
| **Total** | **~280** | **27** | **17** | **15** | **17** |

### Skills Snowflake Features

| Hierarchy Level | Table | Description |
|-----------------|-------|-------------|
| **Type** | dim_skill_type | HARD / SOFT / HYBRID classification |
| **Family** | dim_skill_family | Core Programming, Interpersonal, Analytics & ML, etc. |
| **Category** | dim_skill_category | Programming Languages, Communication, Leadership, etc. |
| **Skill** | dim_skill | Individual skills (Python, AWS, Communication, etc.) |

**Benefits**:
- Single unified `bridge_job_skills` for all skill types
- Filter by `skill_type = 'SOFT'` for soft skills analysis
- Hierarchical drill-down: Type → Family → Category → Skill
- HYBRID type for skills like "Technical Writing" that span both

---

### Time Analysis Features

| Feature | Description |
|---------|-------------|
| **dim_time** | Hour/minute breakdown with time_of_day buckets |
| **time_key in fact** | Links each job posting to posting hour |
| **agg_posting_time_analysis** | Best time to apply by day_of_week × hour |
| **agg_hourly_posting_summary** | Hourly distribution by timezone |
| **Metrics** | competition_score, recommendation_score, avg_time_to_100_applicants |
