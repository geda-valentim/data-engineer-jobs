# Pass 3 Summary Vocabulary Specification v3.4

## Overview

This document defines the controlled vocabulary for Pass 3 summary fields, enabling inter-model consensus measurement.

## Problem Statement

Pass 3 summary arrays (strengths, concerns, etc.) had ~0% consensus because each model wrote unique descriptive phrases. For example:
- `summary.strengths`: 164 entries, 163 unique (99.4% uniqueness)
- `summary.concerns`: 139 entries, 136 unique (97.8% uniqueness)

## Solution: Dual-Field Approach

For each summary concept, we now have TWO fields:
1. **`*_categories`**: Array of enum values from controlled vocabulary (for consensus)
2. **`*_details`**: Array of free-text descriptions (for human analysis)

This enables:
- High inter-model consensus on categories (measurable agreement)
- Rich context preserved in detail fields (for future TF-IDF analysis)

## Vocabulary Definitions

### Strength Categories (20 values)

| Category | Description |
|----------|-------------|
| `competitive_compensation` | Above-market salary/total comp |
| `transparent_salary` | Salary range disclosed in posting |
| `equity_offered` | Stock options, RSUs, or equity mentioned |
| `modern_tech_stack` | dbt, Airflow, Snowflake, modern tools |
| `cloud_native` | AWS, GCP, Azure cloud-first architecture |
| `remote_friendly` | Full remote or remote-first policy |
| `hybrid_work` | Flexible hybrid arrangement |
| `flexible_schedule` | Flexible hours, async work culture |
| `career_growth_clear` | Defined career ladder/growth path |
| `learning_opportunities` | Learning budget, conferences, training |
| `clear_requirements` | Well-defined job requirements |
| `well_defined_role` | Focused responsibilities, no scope creep |
| `strong_benefits` | Comprehensive benefits package |
| `work_life_balance` | WLB signals, reasonable hours |
| `collaborative_culture` | Team collaboration emphasized |
| `diverse_team` | Diversity and inclusion signals |
| `data_focused_role` | Pure data engineering focus |
| `established_company` | Stable, mature company |
| `startup_energy` | Fast-paced, high-growth startup |
| `visa_sponsorship` | H1B/visa sponsorship available |

### Concern Categories (20 values)

| Category | Description |
|----------|-------------|
| `vague_requirements` | Generic or unclear requirements |
| `unclear_responsibilities` | Ambiguous role scope |
| `salary_not_disclosed` | No compensation information |
| `below_market_pay` | Compensation below market rate |
| `no_visa_sponsorship` | US work authorization required |
| `citizenship_required` | US citizenship mandatory |
| `on_call_expected` | On-call or 24/7 duties expected |
| `overtime_likely` | Long hours or overtime signals |
| `scope_creep_risk` | Role spans multiple functions |
| `jack_of_all_trades` | Unrealistic breadth of skills |
| `legacy_technology` | Outdated tech stack |
| `tech_debt_heavy` | Maintenance-focused role |
| `high_turnover_signals` | Backfill or urgent hiring |
| `backfill_role` | Replacing departed employee |
| `unclear_reporting` | Manager/reporting unknown |
| `travel_required` | Significant travel expected |
| `relocation_required` | Must relocate for role |
| `limited_growth` | No career advancement signals |
| `startup_risk` | Early-stage company risk |
| `contract_short_term` | Short contract duration |

### Best Fit Categories (15 values)

| Category | Description |
|----------|-------------|
| `senior_data_engineers` | 5+ years DE experience |
| `mid_level_engineers` | 2-5 years experience |
| `junior_engineers` | 0-2 years experience |
| `cloud_specialists` | AWS/GCP/Azure expertise |
| `platform_architects` | Data platform design focus |
| `pipeline_developers` | ETL/ELT pipeline builders |
| `analytics_engineers` | dbt/SQL/modeling focus |
| `ml_engineers` | ML pipeline experience |
| `data_generalists` | Broad data skills |
| `startup_enthusiasts` | Startup culture fit |
| `enterprise_experienced` | Large company experience |
| `remote_workers` | Remote work preference |
| `career_changers` | Transitioning to DE |
| `leadership_track` | Management aspirations |
| `technical_specialists` | Deep technical expertise |

### Probe Categories (15 values)

| Category | Description |
|----------|-------------|
| `team_size_composition` | Ask about team structure |
| `reporting_structure` | Ask who manager is |
| `tech_stack_details` | Clarify technologies used |
| `on_call_expectations` | Ask about on-call duties |
| `work_hour_expectations` | Ask about typical hours |
| `remote_policy_details` | Clarify remote flexibility |
| `career_growth_path` | Ask about advancement |
| `salary_range_details` | Negotiate compensation |
| `visa_sponsorship_details` | Clarify visa support |
| `role_scope_boundaries` | Understand role limits |
| `tech_debt_situation` | Ask about code quality |
| `team_turnover_history` | Ask about retention |
| `company_financials` | Ask about runway/stability |
| `project_timeline` | Understand deliverables |
| `success_metrics` | Ask how success is measured |

### Leverage Categories (10 values)

| Category | Description |
|----------|-------------|
| `rare_skill_match` | Specialized skills in demand |
| `exact_experience_match` | Perfect background fit |
| `exceeds_requirements` | Overqualified for role |
| `multiple_competing_offers` | Active job search |
| `high_market_demand` | Hot job market for skill |
| `domain_expertise` | Industry domain knowledge |
| `leadership_experience` | Prior leadership roles |
| `quick_availability` | Can start immediately |
| `local_candidate` | No relocation needed |
| `referral_connection` | Internal referral |

## Schema Changes

### New Summary Structure

```json
{
  "summary": {
    "strength_categories": ["transparent_salary", "modern_tech_stack", "well_defined_role"],
    "strength_details": [
      "Transparent compensation ($180-220k + equity)",
      "Strong modern data stack (Snowflake, dbt, Airflow)"
    ],
    "concern_categories": ["overtime_likely", "no_visa_sponsorship"],
    "concern_details": [
      "Immediate start date suggests time pressure",
      "US work authorization required"
    ],
    "best_fit_categories": ["senior_data_engineers", "pipeline_developers"],
    "best_fit_details": [
      "Senior DEs with 5-8 years wanting streaming focus"
    ],
    "probe_categories": ["work_hour_expectations", "on_call_expectations"],
    "probe_details": [
      "Ask about actual work hours and on-call expectations"
    ],
    "leverage_categories": ["rare_skill_match", "domain_expertise"],
    "leverage_details": [
      "Strong streaming expertise (Kafka) is high-value"
    ],
    "overall_assessment": "Strong opportunity...",
    "recommendation_score": 0.82,
    "recommendation_confidence": 0.85
  }
}
```

## Backward Compatibility

Legacy fields are preserved in `field_registry.py`:
- `summary.strengths` → use `summary.strength_details`
- `summary.concerns` → use `summary.concern_details`
- `summary.best_fit_for` → use `summary.best_fit_details`
- `summary.red_flags_to_probe` → use `summary.probe_details`
- `summary.negotiation_leverage` → use `summary.leverage_details`

## Evaluation Impact

With controlled vocabulary:
- **Expected consensus**: 60-90% on category arrays
- **Jaccard Index**: Higher overlap between models
- **Outlier detection**: Models not using valid categories flagged

## Files Modified

1. `src/lambdas/ai_enrichment/enrich_partition/prompts/pass3_complex.py`
   - Updated SYSTEM_PROMPT with vocabulary definitions
   - Updated USER_PROMPT_TEMPLATE with new schema example

2. `src/evaluation/field_registry.py`
   - Added new category and detail fields to `PASS3_SUMMARY_FIELDS`
   - Added `SUMMARY_*_CATEGORIES` constants for validation

3. `data/vocabulary_recommendations.json`
   - TF-IDF analysis results and vocabulary definitions

## Analysis Methodology

Vocabulary derived from TF-IDF analysis of 45 Pass 3 outputs across 10 jobs:
- Identified top keywords by frequency and TF-IDF score
- Clustered similar concepts into categories
- Validated against common job posting patterns
- Refined to ~15-20 categories per field for manageable consensus
