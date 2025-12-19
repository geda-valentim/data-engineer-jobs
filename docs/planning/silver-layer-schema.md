# Silver Layer - Schema Documentation

## Executive Summary

O Silver Layer contém dados limpos e padronizados, prontos para transformação em Gold.

| Source | Columns | Format | Partitioning |
|--------|---------|--------|--------------|
| `linkedin/` | 35 | Parquet | year/month/day/hour |
| `linkedin_companies/` | 47 | Parquet | bucket (0-49) |
| `ai_enrichment/` | 175+ | DeltaLake | - |
| **Total** | **257+** | | |

## Data Flow

```
Bronze (Raw JSON)
    │
    ├─► [Glue Job] ─────────────────► linkedin/
    │                                  (skills detection)
    │
    ├─► [Lambda ETL] ───────────────► linkedin_companies/
    │                                  (flatten + dedupe)
    │
    └─► [AI Enrichment Pipeline] ───► ai_enrichment/
         ├─ Pass 1: Extraction         (ext_*)
         ├─ Pass 2: Inference          (inf_*)
         └─ Pass 3: Analysis           (anl_*)
```

---

## 1. linkedin/ - Job Postings (35 columns)

**Location**: `s3://silver/linkedin/year={year}/month={month}/day={day}/hour={hour}/`
**Format**: Parquet (SNAPPY)
**Source**: Bronze via AWS Glue Job

### Identification

| Column | Type | Description |
|--------|------|-------------|
| job_posting_id | STRING | Unique LinkedIn job ID |
| source_system | STRING | Always "linkedin" |
| url | STRING | Job posting URL |
| scraped_at | TIMESTAMP | When job was scraped |

### Company

| Column | Type | Description |
|--------|------|-------------|
| company_name | STRING | Company name |
| company_id | STRING | Company identifier |
| company_url | STRING | Company profile URL |

### Job Details

| Column | Type | Description |
|--------|------|-------------|
| job_title | STRING | Job title |
| job_seniority_level | STRING | Seniority (Senior, Entry-level, etc.) |
| job_function | STRING | Job function category |
| job_employment_type | STRING | Employment type (full-time, contract) |
| job_industries | STRING | Industry category |

### Location & Timing

| Column | Type | Description |
|--------|------|-------------|
| job_location | STRING | Job location text |
| country_code | STRING | ISO 3166 country code |
| job_posted_datetime | TIMESTAMP | Posted date and time |
| job_posted_date_only | DATE | Posted date only |

### Application

| Column | Type | Description |
|--------|------|-------------|
| application_availability | BOOLEAN | Whether applications are open |
| apply_link | STRING | Application link |
| job_num_applicants | INT | Number of applicants |

### Compensation

| Column | Type | Description |
|--------|------|-------------|
| salary_min | DOUBLE | Minimum salary |
| salary_max | DOUBLE | Maximum salary |
| salary_currency | STRING | Currency (USD, EUR, etc.) |
| salary_period | STRING | Period (yearly, monthly, hourly) |

### Recruiter

| Column | Type | Description |
|--------|------|-------------|
| job_poster_name | STRING | Recruiter name |
| job_poster_title | STRING | Recruiter title |
| job_poster_url | STRING | Recruiter profile URL |

### Description

| Column | Type | Description |
|--------|------|-------------|
| job_summary | STRING | Job summary text |
| job_description_html | STRING | Description in HTML |
| job_description_text | STRING | Description as plain text |

### Skills (Detected at Silver)

| Column | Type | Description |
|--------|------|-------------|
| skills_canonical | ARRAY&lt;STRING&gt; | Canonical skill names |
| skills_families | ARRAY&lt;STRING&gt; | Skill family categories |
| skills_raw_hits | ARRAY&lt;STRING&gt; | Raw text matches |
| skills_catalog_version | STRING | Skills catalog version |

### Partitions

| Column | Type | Description |
|--------|------|-------------|
| year | STRING | Year (2024-2030) |
| month | STRING | Month (01-12) |
| day | STRING | Day (01-31) |
| hour | STRING | Hour (00-23) |

---

## 2. linkedin_companies/ - Company Profiles (47 columns)

**Location**: `s3://silver/linkedin_companies/bucket={bucket}/`
**Format**: Parquet
**Partitioning**: Hash bucket (0-49, MD5-based)
**Source**: Lambda ETL from Bronze

### Core Identifiers

| Column | Type | Description |
|--------|------|-------------|
| company_id | STRING | Unique company ID (NOT NULL) |
| linkedin_id | STRING | LinkedIn profile ID |
| name | STRING | Company name |
| slogan | STRING | Company tagline |
| headquarters | STRING | HQ location |
| country_code | STRING | ISO 3166 country code |
| website | STRING | Company website URL |
| website_domain | STRING | Simplified domain |
| linkedin_url | STRING | LinkedIn company URL |

### Business Info

| Column | Type | Description |
|--------|------|-------------|
| about | STRING | Company description |
| industries | STRING | Industry classification |
| specialties | STRING | Company specialties |
| organization_type | STRING | Type (public, private, non-profit) |
| company_size | STRING | Size range |
| founded_year | INT32 | Year founded |

### Metrics

| Column | Type | Description |
|--------|------|-------------|
| followers | INT64 | LinkedIn followers |
| employees_on_linkedin | INT32 | Employees on LinkedIn |

### Locations (JSON)

| Column | Type | Description |
|--------|------|-------------|
| locations_json | STRING | Office locations (JSON array) |
| formatted_locations_json | STRING | Formatted locations (JSON array) |
| country_codes_json | STRING | Country codes (JSON array) |

### Media

| Column | Type | Description |
|--------|------|-------------|
| logo_url | STRING | Company logo URL |
| cover_image_url | STRING | Cover image URL |

### Funding

| Column | Type | Description |
|--------|------|-------------|
| funding_last_round_date | DATE32 | Last funding round date |
| funding_last_round_type | STRING | Funding type (Series A, B, etc.) |
| funding_rounds_count | INT32 | Total funding rounds |
| funding_last_round_amount | STRING | Last round amount |
| has_funding_info | BOOLEAN | Whether funding info exists |

### External Links

| Column | Type | Description |
|--------|------|-------------|
| crunchbase_url | STRING | Crunchbase profile URL |

### Nested Data (JSON)

| Column | Type | Description |
|--------|------|-------------|
| employees_json | STRING | Featured employees (JSON array) |
| similar_companies_json | STRING | Similar companies (JSON array) |
| affiliated_pages_json | STRING | Affiliated pages (JSON array) |
| updates_json | STRING | Company updates (JSON array) |

### Derived Counts

| Column | Type | Description |
|--------|------|-------------|
| employees_featured_count | INT32 | Featured employees count |
| similar_companies_count | INT32 | Similar companies count |
| affiliated_pages_count | INT32 | Affiliated pages count |
| updates_count | INT32 | Updates count |

### Metadata

| Column | Type | Description |
|--------|------|-------------|
| latest_update_date | TIMESTAMP | Most recent update |
| snapshot_date | DATE32 | Data snapshot date (NOT NULL) |
| scraped_at | TIMESTAMP | When scraped |
| source_url | STRING | Source URL |
| processed_at | TIMESTAMP | When processed (NOT NULL) |

### Partition

| Column | Type | Description |
|--------|------|-------------|
| bucket | INT32 | Hash bucket (0-49) |

---

## 3. ai_enrichment/ - AI-Enriched Data (175+ columns)

**Location**: `s3://silver/ai_enrichment/`
**Format**: DeltaLake (fallback Parquet)
**Source**: Lambda + Amazon Bedrock (3-pass pipeline)

### Pass Structure

| Pass | Prefix | Columns | Purpose |
|------|--------|---------|---------|
| Pass 1 | ext_* | 62 | **Extraction** - Only explicitly stated facts |
| Pass 2 | inf_* | 47 | **Inference** - Derived insights + confidence |
| Pass 3 | anl_* | 66+ | **Analysis** - Scores, signals, recommendations |

---

### Pass 1: Extraction (ext_*) - 62 columns

**Extracts ONLY explicitly stated information from job postings.**

#### Compensation (10 cols)

| Column | Type | Values/Description |
|--------|------|-------------------|
| ext_salary_disclosed | BOOLEAN | Salary is disclosed |
| ext_salary_min | DOUBLE | Minimum salary |
| ext_salary_max | DOUBLE | Maximum salary |
| ext_salary_currency | STRING | USD, EUR, GBP, etc. |
| ext_salary_period | STRING | yearly, monthly, hourly |
| ext_salary_text_raw | STRING | Original salary text |
| ext_hourly_rate_min | DOUBLE | Min hourly rate |
| ext_hourly_rate_max | DOUBLE | Max hourly rate |
| ext_hourly_rate_currency | STRING | Currency for hourly |
| ext_hourly_rate_text_raw | STRING | Original hourly text |

#### Work Authorization (4 cols)

| Column | Type | Values |
|--------|------|--------|
| ext_visa_sponsorship_stated | STRING | will_sponsor, will_not_sponsor, must_be_authorized, not_mentioned |
| ext_work_auth_text | STRING | Original text |
| ext_citizenship_text | STRING | Citizenship requirements text |
| ext_security_clearance_stated | STRING | required, preferred, not_mentioned |

#### Work Model (3 cols)

| Column | Type | Values |
|--------|------|--------|
| ext_work_model_stated | STRING | remote, hybrid, onsite, not_mentioned |
| ext_location_restriction_text | STRING | Location restriction text |
| ext_employment_type_stated | STRING | full_time, contract, internship, part_time, not_mentioned |

#### Contract Details (8 cols)

| Column | Type | Values |
|--------|------|--------|
| ext_contract_type | STRING | permanent, fixed_term, contract_to_hire, project_based, seasonal, not_mentioned |
| ext_contract_duration_months | DOUBLE | Duration in months |
| ext_contract_duration_text | STRING | Original duration text |
| ext_extension_possible | STRING | yes, likely, no, not_mentioned |
| ext_conversion_to_fte | STRING | yes_guaranteed, yes_possible, no, not_mentioned |
| ext_start_date | STRING | immediate, within_2_weeks, within_month, flexible, specific_date, not_mentioned |
| ext_start_date_text | STRING | Original start date text |
| ext_probation_period_text | STRING | Probation period text |

#### Contractor Rates (7 cols)

| Column | Type | Values |
|--------|------|--------|
| ext_pay_type | STRING | salary, hourly, daily, weekly, monthly, project_fixed, not_mentioned |
| ext_daily_rate_min | DOUBLE | Min daily rate |
| ext_daily_rate_max | DOUBLE | Max daily rate |
| ext_daily_rate_currency | STRING | Currency |
| ext_daily_rate_text_raw | STRING | Original text |
| ext_rate_negotiable | STRING | yes, doe, fixed, not_mentioned |
| ext_overtime_paid | STRING | yes, no, exempt, not_mentioned |

#### Skills (12 cols)

| Column | Type | Description |
|--------|------|-------------|
| ext_must_have_hard_skills | ARRAY&lt;STRING&gt; | Required technical skills |
| ext_nice_to_have_hard_skills | ARRAY&lt;STRING&gt; | Preferred technical skills |
| ext_must_have_soft_skills | ARRAY&lt;STRING&gt; | Required soft skills |
| ext_nice_to_have_soft_skills | ARRAY&lt;STRING&gt; | Preferred soft skills |
| ext_certifications_mentioned | ARRAY&lt;STRING&gt; | Certifications mentioned |
| ext_years_experience_min | DOUBLE | Min years experience |
| ext_years_experience_max | DOUBLE | Max years experience |
| ext_years_experience_text | STRING | Original experience text |
| ext_education_level | STRING | PHD, MASTERS, BACHELORS, ASSOCIATES, HIGH_SCHOOL, BOOTCAMP, null |
| ext_education_area | STRING | Field of study |
| ext_education_requirement | STRING | required, preferred, or_equivalent, not_mentioned |
| ext_education_text_raw | STRING | Original education text |

#### Technology Mentions (2 cols)

| Column | Type | Description |
|--------|------|-------------|
| ext_llm_genai_mentioned | BOOLEAN | LLMs/GenAI explicitly mentioned |
| ext_feature_store_mentioned | BOOLEAN | Feature store platforms mentioned |

#### Geographic Restrictions (5 cols)

| Column | Type | Values |
|--------|------|--------|
| ext_geo_restriction_type | STRING | us_only, eu_only, uk_only, latam_only, apac_only, specific_countries, global, not_mentioned |
| ext_allowed_countries | ARRAY&lt;STRING&gt; | Allowed countries list |
| ext_excluded_countries | ARRAY&lt;STRING&gt; | Excluded countries list |
| ext_us_state_restrictions | ARRAY&lt;STRING&gt; | US state restrictions |
| ext_residency_requirement | STRING | must_be_resident, willing_to_relocate, no_requirement, not_mentioned |

#### Benefits (6 cols)

| Column | Type | Description |
|--------|------|-------------|
| ext_benefits_mentioned | ARRAY&lt;STRING&gt; | Benefits list |
| ext_equity_mentioned | BOOLEAN | Equity/stock mentioned |
| ext_learning_budget_mentioned | BOOLEAN | Learning budget offered |
| ext_conference_budget_mentioned | BOOLEAN | Conference budget offered |
| ext_hardware_choice_mentioned | BOOLEAN | Hardware choice offered |
| ext_pto_policy | STRING | unlimited, generous, standard, limited, not_mentioned |

#### Context (2 cols)

| Column | Type | Description |
|--------|------|-------------|
| ext_team_info_text | STRING | Team information text |
| ext_company_description_text | STRING | Company description text |

---

### Pass 2: Inference (inf_*) - 47 columns

**Each field has 4 sub-columns:**
- `inf_{field}` - The inferred value
- `inf_{field}_confidence` - Confidence score (0.0-1.0)
- `inf_{field}_evidence` - Reasoning text
- `inf_{field}_source` - pass1_derived | inferred | combined

#### Seniority and Role (4 primary fields = 16 cols)

| Column | Type | Values |
|--------|------|--------|
| inf_seniority_level | STRING | intern, entry, associate, junior, mid, senior, staff, principal, distinguished, not_mentioned |
| inf_job_family | STRING | data_engineer, analytics_engineer, ml_engineer, mlops_engineer, data_platform_engineer, data_architect, data_scientist, data_analyst, bi_engineer, research_engineer, not_mentioned |
| inf_sub_specialty | STRING | streaming_realtime, batch_etl, data_warehouse, data_lakehouse, ml_infra, mlops, data_governance, data_quality, data_modeling, cloud_migration, reverse_etl, api_development, observability, general, not_mentioned |
| inf_leadership_expectation | STRING | ic, tech_lead_ic, architect, people_manager, tech_and_people_lead, not_mentioned |

#### Stack and Cloud (5 primary fields = 20 cols)

| Column | Type | Values |
|--------|------|--------|
| inf_primary_cloud | STRING | aws, azure, gcp, multi, on_prem, not_mentioned |
| inf_secondary_clouds | ARRAY&lt;STRING&gt; | Secondary cloud platforms |
| inf_processing_paradigm | STRING | streaming, batch, hybrid, not_mentioned |
| inf_orchestrator_category | STRING | airflow_like, spark_native, dbt_core, cloud_native, dagster_prefect, not_mentioned |
| inf_storage_layer | STRING | warehouse, lake, lakehouse, mixed, not_mentioned |

#### Geo and Work Model (3 primary fields = 12 cols)

| Column | Type | Values |
|--------|------|--------|
| inf_remote_restriction | STRING | same_country, same_timezone, same_region, anywhere, not_mentioned |
| inf_timezone_focus | STRING | americas, europe, apac, global, specific_country, not_mentioned |
| inf_relocation_required | BOOLEAN | Relocation required |

#### Visa and Authorization (3 primary fields = 12 cols)

| Column | Type | Values |
|--------|------|--------|
| inf_h1b_friendly | BOOLEAN | H1B visa friendly |
| inf_opt_cpt_friendly | BOOLEAN | OPT/CPT friendly |
| inf_citizenship_required | STRING | work_auth_only, us_citizen_only, us_or_gc, any, not_mentioned |

#### Contract and Compensation (2 primary fields = 8 cols)

| Column | Type | Values |
|--------|------|--------|
| inf_w2_vs_1099 | STRING | w2, c2c, 1099, any, not_mentioned |
| inf_benefits_level | STRING | comprehensive, standard, basic, none_mentioned, not_mentioned |

#### Career Development (5 primary fields = 20 cols)

| Column | Type | Values |
|--------|------|--------|
| inf_growth_path_clarity | STRING | explicit, implied, vague, not_mentioned |
| inf_mentorship_signals | STRING | explicit_yes, implied, not_mentioned |
| inf_promotion_path_mentioned | BOOLEAN | Promotion path mentioned |
| inf_internal_mobility_mentioned | BOOLEAN | Internal mobility mentioned |
| inf_career_tracks_available | ARRAY&lt;STRING&gt; | ic_track, management_track, specialist_track, architect_track |

#### Requirements Classification (3 primary fields = 12 cols)

| Column | Type | Values |
|--------|------|--------|
| inf_requirement_strictness | STRING | low, medium, high, not_mentioned |
| inf_scope_definition | STRING | clear, vague, multi_role, not_mentioned |
| inf_skill_inflation_detected | BOOLEAN | Unrealistic requirements detected |

---

### Pass 3: Analysis (anl_*) - 66+ columns

**Each field has 4 sub-columns (value, confidence, evidence, source).**

#### Company Maturity (3 primary fields = 12 cols)

| Column | Type | Values/Description |
|--------|------|-------------------|
| anl_data_maturity_score | INT | 1-5 scale |
| anl_data_maturity_level | STRING | ad_hoc, developing, defined, managed, optimizing |
| anl_maturity_signals | ARRAY&lt;STRING&gt; | Signals list |

#### Red Flags and Role Quality (4 primary fields = 16 cols)

| Column | Type | Values/Description |
|--------|------|-------------------|
| anl_scope_creep_score | FLOAT | 0.0-1.0 risk score |
| anl_overtime_risk_score | FLOAT | 0.0-1.0 risk score |
| anl_role_clarity | STRING | clear, vague, multi_role, not_mentioned |
| anl_overall_red_flag_score | FLOAT | 0.0-1.0 combined risk |

#### Stakeholders and Leadership (6 primary fields = 24 cols)

| Column | Type | Values |
|--------|------|--------|
| anl_reporting_structure_clarity | STRING | clear, mentioned, vague, not_mentioned |
| anl_manager_level_inferred | STRING | director_plus, senior_manager, manager, tech_lead, not_mentioned |
| anl_team_growth_velocity | STRING | rapid_expansion, steady_growth, stable, unknown, not_mentioned |
| anl_team_composition | OBJECT | team_size, de_count, seniority_mix |
| anl_reporting_structure | STRING | reports_to_cto, reports_to_director_data, reports_to_manager, reports_to_tech_lead, matrix_reporting, not_mentioned |
| anl_cross_functional_embedded | BOOLEAN | Cross-functional team |

#### Tech Culture (7 primary fields = 28 cols)

| Column | Type | Values/Description |
|--------|------|-------------------|
| anl_work_life_balance_score | FLOAT | 0.0-1.0 score |
| anl_growth_opportunities_score | FLOAT | 0.0-1.0 score |
| anl_tech_culture_score | FLOAT | 0.0-1.0 score |
| anl_tech_culture_signals | ARRAY&lt;STRING&gt; | Culture signals |
| anl_dev_practices_mentioned | ARRAY&lt;STRING&gt; | Dev practices |
| anl_innovation_signals | STRING | high, medium, low, not_mentioned |
| anl_tech_debt_awareness | BOOLEAN | Tech debt mentioned |

#### AI/ML Integration (2 primary fields = 8 cols)

| Column | Type | Values |
|--------|------|--------|
| anl_ai_integration_level | STRING | none, basic_ml, advanced_ml, mlops, genai_focus, not_mentioned |
| anl_ml_tools_expected | ARRAY&lt;STRING&gt; | ML tools list |

#### Competition and Timing (2 primary fields = 8 cols)

| Column | Type | Values |
|--------|------|--------|
| anl_hiring_urgency | STRING | immediate, asap, normal, pipeline, not_mentioned |
| anl_competition_level | STRING | low, medium, high, very_high, not_mentioned |

#### Company Context (5 primary fields = 20 cols)

| Column | Type | Values |
|--------|------|--------|
| anl_company_stage_inferred | STRING | startup_seed, startup_series_a_b, growth_stage, established_tech, enterprise, not_mentioned |
| anl_hiring_velocity | STRING | aggressive, steady, replacement, first_hire, not_mentioned |
| anl_team_size_signals | STRING | solo, small_2_5, medium_6_15, large_16_50, very_large_50_plus, not_mentioned |
| anl_funding_stage_signals | STRING | bootstrapped, seed, series_a, series_b_plus, public, profitable, not_mentioned |
| anl_role_creation_type | STRING | new_headcount, backfill, team_expansion, new_function, not_mentioned |

#### Summary (8 columns - plain values)

| Column | Type | Description |
|--------|------|-------------|
| anl_strengths | ARRAY&lt;STRING&gt; | Job strengths list |
| anl_concerns | ARRAY&lt;STRING&gt; | Job concerns list |
| anl_best_fit_for | ARRAY&lt;STRING&gt; | Best fit candidates |
| anl_red_flags_to_probe | ARRAY&lt;STRING&gt; | Questions to ask |
| anl_negotiation_leverage | ARRAY&lt;STRING&gt; | Negotiation points |
| anl_overall_assessment | STRING | Overall assessment text |
| anl_recommendation_score | FLOAT | 0.0-1.0 recommendation |
| anl_recommendation_confidence | FLOAT | 0.0-1.0 confidence |

---

## Storage & Partitioning Summary

| Source | Format | Compression | Partitioning | Projection |
|--------|--------|-------------|--------------|------------|
| linkedin/ | Parquet | SNAPPY | year/month/day/hour | 2024-2030 |
| linkedin_companies/ | Parquet | SNAPPY | bucket (0-49) | - |
| ai_enrichment/ | DeltaLake | SNAPPY | - | - |

## Column Count Summary

| Source | Count | Breakdown |
|--------|-------|-----------|
| linkedin/ | 35 | 4 ID + 3 company + 5 job + 4 location + 3 application + 4 compensation + 3 recruiter + 3 description + 4 skills + 4 partitions |
| linkedin_companies/ | 47 | 9 core + 5 business + 2 metrics + 3 locations + 2 media + 5 funding + 1 external + 4 nested + 4 derived + 5 metadata + 1 partition |
| ai_enrichment/ | 175+ | 62 ext_* + 47 inf_* (×4 sub-cols) + 66+ anl_* (×4 sub-cols) |
| **Total** | **257+** | |
