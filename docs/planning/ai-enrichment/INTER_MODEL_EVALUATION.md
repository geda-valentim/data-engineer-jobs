# Inter-Model Evaluation Framework for AI Enrichment

> **Version**: 1.0
> **Created**: 2025-12-06
> **Purpose**: Define metrics and consensus strategies for comparing LLM outputs across 5 models

---

## 1. Overview

### 1.1 Purpose and Scope

This document defines a framework for evaluating and comparing AI enrichment outputs from multiple Large Language Models (LLMs). Since no human-annotated ground truth exists, **model consensus serves as the proxy for correctness**.

**Key Goals**:
- Measure agreement across models for each field
- Identify reliable vs. unreliable fields
- Detect model outliers
- Generate consensus values for downstream use

### 1.2 Models Under Evaluation

| Model ID | Short Name | Parameters | Cost ($/1M tokens) |
|----------|------------|------------|-------------------|
| `openai.gpt-oss-120b-1:0` | gpt-oss | 120B | $0.15 in / $0.60 out |
| `mistral.mistral-large-3-675b-instruct` | mistral | 675B | $2.00 in / $6.00 out |
| `google.gemma-3-27b-it` | gemma | 27B | $0.23 in / $0.38 out |
| `minimax.minimax-m2` | minimax | ~100B | $0.30 in / $1.20 out |
| `qwen.qwen3-vl-235b-a22b` | qwen | 235B | $0.22 in / $0.88 out |

### 1.3 Consensus-as-Ground-Truth Philosophy

Without human labels, we treat **majority agreement as correctness**:
- If 4/5 models agree, the consensus value is likely correct
- If models disagree significantly, the field is ambiguous or poorly defined
- Outlier models may indicate bugs or interpretation differences

**Thresholds**:
- `agreement_rate >= 0.6` (3/5 models) = **valid consensus**
- `agreement_rate < 0.6` = **no consensus** (flag for review)

### 1.4 Output Location and File Format

**Input**: `/data/local/{job_id}/pass{1,2,3}-{model_clean}.json`

**Example**:
```
data/local/4323400548/
├── pass1-openai-gpt-oss-120b-1-0.json
├── pass1-mistral-mistral-large-3-675b-instruct.json
├── pass1-google-gemma-3-27b-it.json
├── pass1-minimax-minimax-m2.json
├── pass1-qwen-qwen3-vl-235b-a22b.json
├── pass2-*.json (5 files)
└── pass3-*.json (5 files)
```

---

## 2. Field Classification Matrix

### 2.1 Pass 1 - Extraction Fields (52 fields, `ext_*` prefix)

#### Boolean Fields (7)
| Field | Description |
|-------|-------------|
| `ext_salary_disclosed` | Whether salary is disclosed |
| `ext_equity_mentioned` | Whether equity/stock mentioned |
| `ext_learning_budget_mentioned` | Learning budget offered |
| `ext_conference_budget_mentioned` | Conference attendance supported |
| `ext_hardware_choice_mentioned` | Hardware choice offered |
| `ext_llm_genai_mentioned` | LLM/GenAI technologies mentioned |
| `ext_feature_store_mentioned` | Feature store mentioned |

#### Enum Fields (16)
| Field | Valid Values |
|-------|--------------|
| `ext_salary_period` | yearly, monthly, hourly, not_mentioned |
| `ext_salary_currency` | USD, EUR, GBP, etc. |
| `ext_visa_sponsorship_stated` | will_sponsor, will_not_sponsor, must_be_authorized, not_mentioned |
| `ext_security_clearance_stated` | required, preferred, not_mentioned |
| `ext_work_model_stated` | remote, hybrid, onsite, not_mentioned |
| `ext_employment_type_stated` | full_time, contract, internship, part_time, not_mentioned |
| `ext_contract_type` | permanent, fixed_term, contract_to_hire, project_based, seasonal, not_mentioned |
| `ext_extension_possible` | yes, likely, no, not_mentioned |
| `ext_conversion_to_fte` | yes_guaranteed, yes_possible, no, not_mentioned |
| `ext_start_date` | immediate, within_2_weeks, within_month, flexible, specific_date, not_mentioned |
| `ext_pay_type` | salary, hourly, daily, weekly, monthly, project_fixed, not_mentioned |
| `ext_rate_negotiable` | yes, doe, fixed, not_mentioned |
| `ext_overtime_paid` | yes, no, exempt, not_mentioned |
| `ext_geo_restriction_type` | us_only, eu_only, uk_only, latam_only, apac_only, specific_countries, global, not_mentioned |
| `ext_residency_requirement` | must_be_resident, willing_to_relocate, no_requirement, not_mentioned |
| `ext_pto_policy` | unlimited, generous, standard, limited, not_mentioned |

#### Numeric Fields (9)
| Field | Type | Range |
|-------|------|-------|
| `ext_salary_min` | float | 0+ |
| `ext_salary_max` | float | 0+ |
| `ext_hourly_rate_min` | float | 0+ |
| `ext_hourly_rate_max` | float | 0+ |
| `ext_daily_rate_min` | float | 0+ |
| `ext_daily_rate_max` | float | 0+ |
| `ext_years_experience_min` | float | 0+ |
| `ext_years_experience_max` | float | 0+ |
| `ext_contract_duration_months` | int | 1+ |

#### String Fields (11)
| Field | Description |
|-------|-------------|
| `ext_salary_text_raw` | Original salary text |
| `ext_hourly_rate_text_raw` | Original hourly rate text |
| `ext_daily_rate_text_raw` | Original daily rate text |
| `ext_work_auth_text` | Work authorization text |
| `ext_citizenship_text` | Citizenship requirement text |
| `ext_location_restriction_text` | Location restriction text |
| `ext_contract_duration_text` | Contract duration text |
| `ext_start_date_text` | Start date text |
| `ext_probation_period_text` | Probation period text |
| `ext_years_experience_text` | Experience requirement text |
| `ext_education_stated` | Education requirement text |

#### Array Fields (9)
| Field | Item Type |
|-------|-----------|
| `ext_must_have_hard_skills` | string[] |
| `ext_nice_to_have_hard_skills` | string[] |
| `ext_must_have_soft_skills` | string[] (canonical 22) |
| `ext_nice_to_have_soft_skills` | string[] (canonical 22) |
| `ext_certifications_mentioned` | string[] |
| `ext_benefits_mentioned` | string[] |
| `ext_allowed_countries` | string[] (ISO codes) |
| `ext_excluded_countries` | string[] (ISO codes) |
| `ext_us_state_restrictions` | string[] (state codes) |

### 2.2 Pass 2 - Inference Fields (25 fields, `inf_*` prefix)

Each field is an **inference object** with structure:
```json
{
  "value": "senior",
  "confidence": 0.95,
  "evidence": "Job title includes 'Senior'...",
  "source": "combined"
}
```

#### Enum+Confidence Fields (17)
| Field | Valid Values |
|-------|--------------|
| `inf_seniority_level` | intern, entry, associate, junior, mid, senior, staff, principal, distinguished, not_mentioned |
| `inf_job_family` | data_engineer, analytics_engineer, ml_engineer, mlops_engineer, data_platform_engineer, data_architect, data_scientist, data_analyst, bi_engineer, research_engineer, not_mentioned |
| `inf_sub_specialty` | streaming_realtime, batch_etl, data_warehouse, data_lakehouse, ml_infra, mlops, data_governance, data_quality, data_modeling, cloud_migration, reverse_etl, api_development, observability, general, not_mentioned |
| `inf_leadership_expectation` | ic, tech_lead_ic, architect, people_manager, tech_and_people_lead, not_mentioned |
| `inf_primary_cloud` | aws, azure, gcp, multi, on_prem, not_mentioned |
| `inf_processing_paradigm` | batch, streaming, hybrid, not_mentioned |
| `inf_orchestrator_category` | airflow_like, spark_native, dbt_core, cloud_native, dagster_prefect, not_mentioned |
| `inf_storage_layer` | warehouse, lake, lakehouse, mixed, not_mentioned |
| `inf_remote_restriction` | same_country, same_timezone, same_region, anywhere, not_mentioned |
| `inf_timezone_focus` | americas, europe, apac, global, specific_country, not_mentioned |
| `inf_citizenship_required` | us_citizen_only, us_or_gc, work_auth_only, any, not_mentioned |
| `inf_w2_vs_1099` | w2, c2c, 1099, any, not_mentioned |
| `inf_benefits_level` | comprehensive, standard, basic, none_mentioned, not_mentioned |
| `inf_growth_path_clarity` | explicit, implied, vague, not_mentioned |
| `inf_mentorship_signals` | explicit_yes, implied, not_mentioned |
| `inf_requirement_strictness` | low, medium, high, not_mentioned |
| `inf_scope_definition` | clear, vague, multi_role, not_mentioned |

#### Boolean+Confidence Fields (6)
| Field | Description |
|-------|-------------|
| `inf_relocation_required` | Whether relocation is required |
| `inf_h1b_friendly` | Whether H1B sponsorship available |
| `inf_opt_cpt_friendly` | Whether OPT/CPT accepted |
| `inf_promotion_path_mentioned` | Whether promotion path mentioned |
| `inf_internal_mobility_mentioned` | Whether internal mobility mentioned |
| `inf_skill_inflation_detected` | Whether unrealistic skills requested |

#### Array+Confidence Fields (2)
| Field | Item Type |
|-------|-----------|
| `inf_secondary_clouds` | string[] (aws, azure, gcp) |
| `inf_career_tracks_available` | string[] (ic_track, management_track, etc.) |

### 2.3 Pass 3 - Analysis Fields (30+ fields, `anl_*` prefix)

#### Score Fields (0.0-1.0) (7)
| Field | Description |
|-------|-------------|
| `anl_scope_creep_score` | Risk of role scope creep (0=clear, 1=severe) |
| `anl_overtime_risk_score` | Risk of overtime/burnout (0=low, 1=high) |
| `anl_overall_red_flag_score` | Overall risk score (0=safe, 1=risky) |
| `anl_work_life_balance_score` | Work-life balance signals (0=poor, 1=excellent) |
| `anl_growth_opportunities_score` | Growth opportunity signals |
| `anl_tech_culture_score` | Tech culture quality |
| `anl_recommendation_score` | Overall recommendation |

#### Score Field (1-5) (1)
| Field | Description |
|-------|-------------|
| `anl_data_maturity_score` | Data maturity level (1=ad-hoc, 5=optimized) |

#### Enum+Confidence Fields (13)
| Field | Valid Values |
|-------|--------------|
| `anl_data_maturity_level` | ad_hoc, developing, defined, managed, optimizing, not_mentioned |
| `anl_role_clarity` | clear, vague, multi_role, not_mentioned |
| `anl_reporting_structure_clarity` | clear, mentioned, vague, not_mentioned |
| `anl_manager_level_inferred` | director_plus, senior_manager, manager, tech_lead, not_mentioned |
| `anl_team_growth_velocity` | rapid_expansion, steady_growth, stable, unknown, not_mentioned |
| `anl_reporting_structure` | reports_to_cto, reports_to_director_data, reports_to_manager, reports_to_tech_lead, matrix_reporting, not_mentioned |
| `anl_ai_integration_level` | none, basic_ml, advanced_ml, mlops, genai_focus, not_mentioned |
| `anl_hiring_urgency` | immediate, asap, normal, pipeline, not_mentioned |
| `anl_competition_level` | low, medium, high, very_high, not_mentioned |
| `anl_company_stage_inferred` | startup_seed, startup_series_a_b, growth_stage, established_tech, enterprise, not_mentioned |
| `anl_hiring_velocity` | aggressive, steady, replacement, first_hire, not_mentioned |
| `anl_team_size_signals` | solo, small_2_5, medium_6_15, large_16_50, very_large_50_plus, not_mentioned |
| `anl_funding_stage_signals` | bootstrapped, seed, series_a, series_b_plus, public, profitable, not_mentioned |
| `anl_role_creation_type` | new_headcount, backfill, team_expansion, new_function, not_mentioned |
| `anl_innovation_signals` | high, medium, low, not_mentioned |

#### Boolean+Confidence Fields (2)
| Field | Description |
|-------|-------------|
| `anl_cross_functional_embedded` | Embedded in cross-functional team |
| `anl_tech_debt_awareness` | Tech debt mentioned as responsibility |

#### Array Fields (8)
| Field | Description |
|-------|-------------|
| `anl_maturity_signals` | Maturity indicators |
| `anl_tech_culture_signals` | Culture indicators |
| `anl_dev_practices_mentioned` | Dev practices |
| `anl_ml_tools_expected` | ML tools |
| `anl_strengths` | Job strengths |
| `anl_concerns` | Job concerns |
| `anl_best_fit_for` | Ideal candidate profiles |
| `anl_red_flags_to_probe` | Interview questions |
| `anl_negotiation_leverage` | Negotiation points |

#### String Field (1)
| Field | Description |
|-------|-------------|
| `anl_overall_assessment` | Free-text summary |

#### Object Field (1)
| Field | Description |
|-------|-------------|
| `anl_team_composition` | {team_size, de_count, seniority_mix} |

### 2.4 Field Type Summary

| Pass | Boolean | Enum | Numeric | String | Array | Inference | Total |
|------|---------|------|---------|--------|-------|-----------|-------|
| Pass 1 | 7 | 16 | 9 | 11 | 9 | - | 52 |
| Pass 2 | - | - | - | - | - | 25 | 25 |
| Pass 3 | - | 14 | 8 | 1 | 9 | - | 32 |
| **Total** | 7 | 30 | 17 | 12 | 18 | 25 | **109** |

---

## 3. Consensus Functions

### 3.1 Categorical Consensus (Enums)

```python
from typing import Dict, Optional, List
from collections import Counter
from dataclasses import dataclass
import math

@dataclass
class CategoricalConsensusResult:
    """Result of categorical field consensus analysis."""
    consensus_value: Optional[str]
    agreement_rate: float  # 0.0-1.0
    entropy: float         # Shannon entropy (0 = perfect agreement)
    value_distribution: Dict[str, int]
    outlier_models: List[str]
    has_consensus: bool    # True if agreement_rate >= threshold


def categorical_consensus(
    values: Dict[str, Optional[str]],
    min_agreement: float = 0.6
) -> CategoricalConsensusResult:
    """
    Compute consensus for categorical (enum) fields.

    Args:
        values: Dict mapping model_id -> extracted value
        min_agreement: Minimum agreement rate for consensus (default 60%)

    Returns:
        CategoricalConsensusResult with consensus analysis

    Example:
        >>> values = {
        ...     "gpt-oss": "hybrid",
        ...     "mistral": "hybrid",
        ...     "gemma": "hybrid",
        ...     "minimax": "hybrid",
        ...     "qwen": "hybrid"
        ... }
        >>> result = categorical_consensus(values)
        >>> result.consensus_value
        'hybrid'
        >>> result.agreement_rate
        1.0
    """
    # Filter out nulls
    non_null = {k: v for k, v in values.items() if v is not None}

    if not non_null:
        return CategoricalConsensusResult(
            consensus_value=None,
            agreement_rate=0.0,
            entropy=0.0,
            value_distribution={},
            outlier_models=list(values.keys()),
            has_consensus=False
        )

    # Count occurrences
    counter = Counter(non_null.values())
    total = len(non_null)

    # Find majority value
    most_common_value, most_common_count = counter.most_common(1)[0]
    agreement_rate = most_common_count / total

    # Calculate Shannon entropy
    entropy = 0.0
    for count in counter.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)

    # Identify outlier models
    outlier_models = [
        model for model, value in values.items()
        if value != most_common_value
    ]

    has_consensus = agreement_rate >= min_agreement

    return CategoricalConsensusResult(
        consensus_value=most_common_value if has_consensus else None,
        agreement_rate=agreement_rate,
        entropy=entropy,
        value_distribution=dict(counter),
        outlier_models=outlier_models,
        has_consensus=has_consensus
    )
```

### 3.2 Numeric Consensus (Salary, Scores)

```python
import numpy as np

@dataclass
class NumericConsensusResult:
    """Result of numeric field consensus analysis."""
    consensus_value: Optional[float]
    mean: Optional[float]
    median: Optional[float]
    std_dev: Optional[float]
    coefficient_of_variation: Optional[float]  # std/mean
    outlier_models: List[str]
    null_count: int
    has_consensus: bool


def numeric_consensus(
    values: Dict[str, Optional[float]],
    max_cv: float = 0.15,  # Maximum coefficient of variation
    outlier_threshold: float = 2.0  # Z-score threshold
) -> NumericConsensusResult:
    """
    Compute consensus for numeric fields.

    Uses median as robust consensus value. Identifies outliers via Z-score.

    Args:
        values: Dict mapping model_id -> numeric value (can be None)
        max_cv: Maximum coefficient of variation for consensus
        outlier_threshold: Z-score threshold for outlier detection

    Example:
        >>> values = {
        ...     "gpt-oss": 111800.0,
        ...     "mistral": 111800.0,
        ...     "gemma": 111800.0,
        ...     "minimax": 111800.0,
        ...     "qwen": 111800.0
        ... }
        >>> result = numeric_consensus(values)
        >>> result.consensus_value
        111800.0
        >>> result.coefficient_of_variation
        0.0
    """
    non_null = {k: v for k, v in values.items() if v is not None}
    null_count = len(values) - len(non_null)

    if not non_null:
        return NumericConsensusResult(
            consensus_value=None,
            mean=None,
            median=None,
            std_dev=None,
            coefficient_of_variation=None,
            outlier_models=list(values.keys()),
            null_count=null_count,
            has_consensus=False
        )

    arr = np.array(list(non_null.values()))

    mean = float(np.mean(arr))
    median = float(np.median(arr))
    std_dev = float(np.std(arr)) if len(arr) > 1 else 0.0
    cv = std_dev / mean if mean != 0 else 0.0

    # Identify outliers using Z-score
    outlier_models = []
    if std_dev > 0:
        z_scores = (arr - mean) / std_dev
        for model, z_score in zip(non_null.keys(), z_scores):
            if abs(z_score) > outlier_threshold:
                outlier_models.append(model)

    # Add null models as outliers
    outlier_models.extend([m for m in values if values[m] is None])

    has_consensus = cv <= max_cv and null_count <= 1

    return NumericConsensusResult(
        consensus_value=median if has_consensus else None,
        mean=mean,
        median=median,
        std_dev=std_dev,
        coefficient_of_variation=cv,
        outlier_models=outlier_models,
        null_count=null_count,
        has_consensus=has_consensus
    )
```

### 3.3 Boolean Consensus

```python
@dataclass
class BooleanConsensusResult:
    """Result of boolean field consensus analysis."""
    consensus_value: Optional[bool]
    agreement_rate: float
    true_count: int
    false_count: int
    null_count: int
    outlier_models: List[str]
    has_consensus: bool


def boolean_consensus(
    values: Dict[str, Optional[bool]],
    min_agreement: float = 0.6
) -> BooleanConsensusResult:
    """
    Compute consensus for boolean fields.

    Example:
        >>> values = {
        ...     "gpt-oss": True,
        ...     "mistral": True,
        ...     "gemma": True,
        ...     "minimax": True,
        ...     "qwen": True
        ... }
        >>> result = boolean_consensus(values)
        >>> result.consensus_value
        True
        >>> result.agreement_rate
        1.0
    """
    non_null = {k: v for k, v in values.items() if v is not None}
    null_count = len(values) - len(non_null)

    if not non_null:
        return BooleanConsensusResult(
            consensus_value=None,
            agreement_rate=0.0,
            true_count=0,
            false_count=0,
            null_count=null_count,
            outlier_models=list(values.keys()),
            has_consensus=False
        )

    true_count = sum(1 for v in non_null.values() if v is True)
    false_count = sum(1 for v in non_null.values() if v is False)
    total = len(non_null)

    if true_count >= false_count:
        consensus_value = True
        agreement_rate = true_count / total
        outlier_models = [m for m, v in values.items() if v is not True]
    else:
        consensus_value = False
        agreement_rate = false_count / total
        outlier_models = [m for m, v in values.items() if v is not False]

    has_consensus = agreement_rate >= min_agreement

    return BooleanConsensusResult(
        consensus_value=consensus_value if has_consensus else None,
        agreement_rate=agreement_rate,
        true_count=true_count,
        false_count=false_count,
        null_count=null_count,
        outlier_models=outlier_models,
        has_consensus=has_consensus
    )
```

### 3.4 List Consensus (Skills, Benefits)

```python
from typing import Set
from itertools import combinations

@dataclass
class ListConsensusResult:
    """Result of list/array field consensus analysis."""
    consensus_list: List[str]
    item_confidence: Dict[str, float]  # item -> occurrence rate
    avg_jaccard: float
    union_size: int
    intersection_size: int
    outlier_items: Dict[str, List[str]]  # model -> unique items
    has_consensus: bool


def list_consensus(
    lists: Dict[str, Optional[List[str]]],
    min_occurrence: float = 0.5,
    normalize: bool = True
) -> ListConsensusResult:
    """
    Compute consensus for list/array fields (e.g., skills lists).

    Items appearing in >= min_occurrence of models are included in consensus.
    Uses Jaccard similarity for pairwise comparison.

    Args:
        lists: Dict mapping model_id -> list of strings
        min_occurrence: Minimum fraction of models an item must appear in
        normalize: Whether to lowercase and strip items

    Example:
        >>> lists = {
        ...     "gpt-oss": ["AWS", "Python", "SQL"],
        ...     "mistral": ["AWS", "Python", "SQL"],
        ...     "gemma": ["AWS", "Python", "SQL"],
        ...     "minimax": ["AWS", "Python"],
        ...     "qwen": ["AWS", "Python", "SQL"]
        ... }
        >>> result = list_consensus(lists)
        >>> "aws" in result.consensus_list
        True
        >>> result.item_confidence["aws"]
        1.0
    """
    # Normalize and filter empty lists
    normalized: Dict[str, Set[str]] = {}
    for model, items in lists.items():
        if items is None or not items:
            normalized[model] = set()
        else:
            if normalize:
                normalized[model] = {item.lower().strip() for item in items if item}
            else:
                normalized[model] = set(items)

    # Count item occurrences
    all_items: Dict[str, int] = Counter()
    for items in normalized.values():
        for item in items:
            all_items[item] += 1

    total_models = len(lists)

    # Build consensus list
    item_confidence: Dict[str, float] = {}
    consensus_list: List[str] = []

    for item, count in all_items.items():
        confidence = count / total_models
        item_confidence[item] = confidence
        if confidence >= min_occurrence:
            consensus_list.append(item)

    # Calculate union and intersection
    non_empty = [s for s in normalized.values() if s]
    if non_empty:
        union = set.union(*non_empty)
        intersection = set.intersection(*non_empty) if len(non_empty) > 1 else non_empty[0]
    else:
        union = set()
        intersection = set()

    # Calculate average Jaccard similarity
    jaccard_scores = []
    model_list = list(normalized.keys())
    for i in range(len(model_list)):
        for j in range(i + 1, len(model_list)):
            set_a = normalized[model_list[i]]
            set_b = normalized[model_list[j]]
            if set_a or set_b:
                jaccard = len(set_a & set_b) / len(set_a | set_b) if (set_a | set_b) else 0
                jaccard_scores.append(jaccard)

    avg_jaccard = sum(jaccard_scores) / len(jaccard_scores) if jaccard_scores else 0.0

    # Find outlier items (unique to single model)
    outlier_items: Dict[str, List[str]] = {}
    for model, items in normalized.items():
        unique = [item for item in items if all_items[item] == 1]
        if unique:
            outlier_items[model] = unique

    has_consensus = avg_jaccard >= 0.5 and len(consensus_list) > 0

    return ListConsensusResult(
        consensus_list=sorted(consensus_list),
        item_confidence=item_confidence,
        avg_jaccard=avg_jaccard,
        union_size=len(union),
        intersection_size=len(intersection),
        outlier_items=outlier_items,
        has_consensus=has_consensus
    )
```

### 3.5 String Consensus (Free Text)

```python
from difflib import SequenceMatcher
from typing import Tuple

@dataclass
class StringConsensusResult:
    """Result of free-text string field consensus analysis."""
    has_consensus: bool
    unique_values: List[str]
    similarity_matrix: Dict[Tuple[str, str], float]
    avg_similarity: float
    null_count: int


def string_consensus(
    values: Dict[str, Optional[str]],
    similarity_threshold: float = 0.85
) -> StringConsensusResult:
    """
    Compute consensus for free-text string fields.

    Uses fuzzy string matching (SequenceMatcher) for similarity.

    Args:
        values: Dict mapping model_id -> string value
        similarity_threshold: Minimum avg similarity for consensus

    Example:
        >>> values = {
        ...     "gpt-oss": "4+ years of experience",
        ...     "mistral": "4+ years of experience",
        ...     "gemma": "4+ years of experience",
        ...     "minimax": "4+ years of experience",
        ...     "qwen": "4+ years of experience"
        ... }
        >>> result = string_consensus(values)
        >>> result.has_consensus
        True
        >>> result.avg_similarity
        1.0
    """
    non_null = {k: v for k, v in values.items() if v is not None and v.strip()}
    null_count = len(values) - len(non_null)

    if not non_null:
        return StringConsensusResult(
            has_consensus=False,
            unique_values=[],
            similarity_matrix={},
            avg_similarity=0.0,
            null_count=null_count
        )

    unique_values = list(set(non_null.values()))

    # Calculate pairwise similarity
    similarity_matrix: Dict[Tuple[str, str], float] = {}
    model_list = list(non_null.keys())
    similarities = []

    for i in range(len(model_list)):
        for j in range(i + 1, len(model_list)):
            m1, m2 = model_list[i], model_list[j]
            s1, s2 = non_null[m1], non_null[m2]
            ratio = SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
            similarity_matrix[(m1, m2)] = ratio
            similarities.append(ratio)

    avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0

    has_consensus = len(unique_values) == 1 or avg_similarity >= similarity_threshold

    return StringConsensusResult(
        has_consensus=has_consensus,
        unique_values=unique_values,
        similarity_matrix=similarity_matrix,
        avg_similarity=avg_similarity,
        null_count=null_count
    )
```

### 3.6 Confidence Aggregation (Pass 2 & 3 Inference Objects)

```python
from typing import Any

@dataclass
class ConfidenceAggregationResult:
    """Result of inference object consensus (value + confidence)."""
    consensus_value: Optional[Any]
    weighted_confidence: float
    agreement_rate: float
    value_distribution: Dict[str, Tuple[int, float]]  # value -> (count, avg_conf)
    outlier_models: List[str]
    has_consensus: bool


def confidence_aggregation(
    inference_objects: Dict[str, Optional[Dict[str, Any]]],
    min_agreement: float = 0.6
) -> ConfidenceAggregationResult:
    """
    Aggregate inference objects with value + confidence.

    Uses confidence-weighted voting for consensus.

    Args:
        inference_objects: Dict mapping model_id -> {value, confidence, evidence, source}
        min_agreement: Minimum agreement rate for consensus

    Example:
        >>> objs = {
        ...     "gpt-oss": {"value": "senior", "confidence": 0.95},
        ...     "mistral": {"value": "senior", "confidence": 0.92},
        ...     "gemma": {"value": "senior", "confidence": 0.90},
        ...     "minimax": {"value": "senior", "confidence": 0.88},
        ...     "qwen": {"value": "senior", "confidence": 0.91}
        ... }
        >>> result = confidence_aggregation(objs)
        >>> result.consensus_value
        'senior'
        >>> result.agreement_rate
        1.0
    """
    # Extract values and confidences
    valid_entries: Dict[str, Tuple[Any, float]] = {}
    for model, obj in inference_objects.items():
        if obj is not None and isinstance(obj, dict):
            value = obj.get("value")
            conf = obj.get("confidence", 0.5)
            if value is not None:
                valid_entries[model] = (value, conf)

    if not valid_entries:
        return ConfidenceAggregationResult(
            consensus_value=None,
            weighted_confidence=0.0,
            agreement_rate=0.0,
            value_distribution={},
            outlier_models=list(inference_objects.keys()),
            has_consensus=False
        )

    # Group by value
    value_stats: Dict[str, List[Tuple[str, float]]] = {}
    for model, (value, conf) in valid_entries.items():
        key = str(value) if isinstance(value, (list, dict)) else value
        if key not in value_stats:
            value_stats[key] = []
        value_stats[key].append((model, conf))

    # Find value with highest count (then highest avg confidence)
    total_models = len(valid_entries)
    best_value = None
    best_count = 0
    best_avg_conf = 0.0

    value_distribution: Dict[str, Tuple[int, float]] = {}
    for value, entries in value_stats.items():
        count = len(entries)
        avg_conf = sum(conf for _, conf in entries) / count
        value_distribution[value] = (count, avg_conf)

        if count > best_count or (count == best_count and avg_conf > best_avg_conf):
            best_value = value
            best_count = count
            best_avg_conf = avg_conf

    agreement_rate = best_count / total_models if total_models > 0 else 0.0

    # Identify outliers
    outlier_models = [
        model for model, (value, _) in valid_entries.items()
        if str(value) if isinstance(value, (list, dict)) else value != best_value
    ]
    outlier_models.extend([m for m in inference_objects if m not in valid_entries])

    has_consensus = agreement_rate >= min_agreement

    # Get original value (not stringified)
    consensus_value = None
    if has_consensus and best_value is not None:
        for model, (value, _) in valid_entries.items():
            key = str(value) if isinstance(value, (list, dict)) else value
            if key == best_value:
                consensus_value = value
                break

    return ConfidenceAggregationResult(
        consensus_value=consensus_value,
        weighted_confidence=best_avg_conf,
        agreement_rate=agreement_rate,
        value_distribution=value_distribution,
        outlier_models=outlier_models,
        has_consensus=has_consensus
    )
```

---

## 4. Metrics Definitions

### 4.1 Agreement Rate

**Definition**: Proportion of models that agree on the majority value.

```
Agreement Rate = count(majority_value) / total_models
```

**Interpretation**:
- `1.0` = Perfect agreement (5/5 models)
- `0.8` = Strong agreement (4/5 models)
- `0.6` = Minimum consensus (3/5 models)
- `< 0.6` = No consensus

### 4.2 Shannon Entropy

**Definition**: Measure of value distribution uncertainty.

```
H = -Σ p(v) × log₂(p(v))
```

**Interpretation**:
- `0.0` = All models agree (single value)
- `1.0` = Two values equally split
- `2.32` = Maximum for 5 distinct values

### 4.3 Coefficient of Variation (CV)

**Definition**: Normalized measure of numeric value dispersion.

```
CV = σ / μ (standard deviation / mean)
```

**Interpretation**:
- `0.0` = Perfect agreement
- `≤ 0.05` = Excellent (within 5%)
- `≤ 0.15` = Acceptable (within 15%)
- `> 0.15` = High variance (no consensus)

### 4.4 Jaccard Index

**Definition**: Similarity between two sets (arrays).

```
J(A, B) = |A ∩ B| / |A ∪ B|
```

**Interpretation**:
- `1.0` = Identical sets
- `0.5` = 50% overlap
- `0.0` = No overlap

**For multiple models**: Average pairwise Jaccard across all model pairs.

### 4.5 Weighted Confidence

**Definition**: Average confidence score for the consensus value.

```
Weighted Confidence = Σ confidence(model) / count(matching_models)
```

Only includes models that match the consensus value.

### 4.6 Confidence Calibration Score

**Definition**: How well a model's confidence predicts correctness.

```
Calibration = 1 - |avg_conf_when_correct - avg_conf_when_wrong|
```

A well-calibrated model has:
- High confidence when matching consensus
- Low confidence when diverging from consensus

---

## 5. Aggregation Strategies

### 5.1 Simple Majority Voting

**Rule**: The value with the most votes wins.

```python
def simple_majority(values: Dict[str, Any]) -> Tuple[Any, float]:
    counter = Counter(v for v in values.values() if v is not None)
    if not counter:
        return None, 0.0
    most_common, count = counter.most_common(1)[0]
    return most_common, count / len([v for v in values.values() if v is not None])
```

**Use for**: Enum fields, boolean fields

### 5.2 Confidence-Weighted Voting

**Rule**: Weight each vote by its confidence score.

```python
def confidence_weighted(inference_objects: Dict[str, Dict]) -> Tuple[Any, float]:
    scores: Dict[str, float] = {}
    for model, obj in inference_objects.items():
        value = obj.get("value")
        conf = obj.get("confidence", 0.5)
        key = str(value)
        scores[key] = scores.get(key, 0) + conf

    if not scores:
        return None, 0.0

    best_key = max(scores, key=scores.get)
    total_conf = sum(scores.values())
    return best_key, scores[best_key] / total_conf
```

**Use for**: Inference objects (Pass 2 & 3)

### 5.3 Outlier Detection (Z-score)

**Rule**: Identify values more than N standard deviations from mean.

```python
def detect_outliers(values: Dict[str, float], threshold: float = 2.0) -> List[str]:
    arr = np.array(list(values.values()))
    mean, std = np.mean(arr), np.std(arr)
    if std == 0:
        return []
    z_scores = (arr - mean) / std
    return [model for model, z in zip(values.keys(), z_scores) if abs(z) > threshold]
```

**Use for**: Numeric fields (salary, scores)

### 5.4 Tie-Breaking Rules

When agreement rate = 0.5 (e.g., 2-2-1 split):

1. **Prefer higher confidence** (for inference objects)
2. **Prefer larger model** (by parameter count)
3. **Prefer not_mentioned** over specific values (conservative)
4. **Flag for manual review** if still tied

```python
MODEL_PRIORITY = ["mistral", "qwen", "gpt-oss", "minimax", "gemma"]

def break_tie(values: Dict[str, Any], confidences: Optional[Dict[str, float]] = None) -> Any:
    counter = Counter(v for v in values.values() if v is not None)
    top_values = [v for v, c in counter.most_common() if c == counter.most_common(1)[0][1]]

    if len(top_values) == 1:
        return top_values[0]

    # Prefer higher confidence
    if confidences:
        best_conf = 0
        best_value = None
        for value in top_values:
            models_with_value = [m for m, v in values.items() if v == value]
            avg_conf = sum(confidences.get(m, 0) for m in models_with_value) / len(models_with_value)
            if avg_conf > best_conf:
                best_conf = avg_conf
                best_value = value
        if best_value:
            return best_value

    # Prefer larger model
    for model in MODEL_PRIORITY:
        if model in values and values[model] in top_values:
            return values[model]

    return top_values[0]
```

---

## 6. Edge Case Handling

### 6.1 Null Value Strategy

```python
def handle_nulls(values: Dict[str, Any], field_type: str) -> Dict[str, Any]:
    """
    Rules:
    - Pass 1 null: "not found in text" - valid result
    - Pass 2/3 null: "low confidence" - potential outlier
    - All null: consensus = null (field not extractable)
    - Majority null: consensus = null, non-null are outliers
    """
    non_null = {k: v for k, v in values.items() if v is not None}
    null_count = len(values) - len(non_null)

    if not non_null:
        return {"consensus": None, "reason": "all_null", "valid": True}

    if null_count > len(non_null):
        return {
            "consensus": None,
            "reason": "majority_null",
            "outliers": list(non_null.keys()),
            "valid": True
        }

    return {"values": non_null, "null_models": [k for k in values if values[k] is None]}
```

### 6.2 Type Mismatch Handling

```python
def coerce_type(value: Any, expected_type: str) -> Optional[Any]:
    """
    Attempt type coercion:
    - "true" -> True
    - "5" -> 5
    - "aws, gcp" -> ["aws", "gcp"]
    """
    if value is None:
        return None

    try:
        if expected_type == "boolean":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "yes", "1")
            return bool(value)

        elif expected_type == "numeric":
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                cleaned = value.replace(",", "").replace("$", "").strip()
                return float(cleaned)

        elif expected_type == "array":
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                return [s.strip() for s in value.split(",")]
            return [str(value)]

        return value
    except (ValueError, TypeError):
        return None
```

### 6.3 Semantic Equivalence (Synonyms)

```python
EQUIVALENCES = {
    # Cloud providers
    "amazon web services": "aws",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
    "microsoft azure": "azure",

    # Work models
    "work from home": "remote",
    "wfh": "remote",
    "in-office": "onsite",
    "on-site": "onsite",

    # Employment types
    "full time": "full_time",
    "full-time": "full_time",
    "part time": "part_time",
    "part-time": "part_time",
}

def normalize_value(value: str) -> str:
    if value is None:
        return None
    lower = value.lower().strip()
    return EQUIVALENCES.get(lower, lower)
```

### 6.4 Array Normalization (Skill Synonyms)

```python
SKILL_SYNONYMS = {
    "apache spark": "spark",
    "apache kafka": "kafka",
    "apache airflow": "airflow",
    "amazon s3": "s3",
    "amazon redshift": "redshift",
    "google bigquery": "bigquery",
    "postgresql": "postgres",
    "javascript": "js",
    "typescript": "ts",
    "etl/elt": "etl",
    "infrastructure-as-code": "iac",
    "infrastructure-as-code tools": "iac",
    "datalake technologies": "data lake",
    "data orchestration tools": "orchestration",
}

def normalize_skill(skill: str) -> str:
    lower = skill.lower().strip()
    return SKILL_SYNONYMS.get(lower, lower)

def normalize_skill_list(skills: List[str]) -> List[str]:
    return sorted(set(normalize_skill(s) for s in skills if s))
```

---

## 7. Output Schema

### 7.1 FieldEvaluation

```python
@dataclass
class FieldEvaluation:
    """Evaluation result for a single field."""
    field_name: str
    field_type: str  # boolean, enum, numeric, array, string, inference
    pass_number: int  # 1, 2, or 3

    # Consensus results
    has_consensus: bool
    consensus_value: Optional[Any]
    agreement_rate: float

    # Per-model values
    model_values: Dict[str, Any]

    # Outlier analysis
    outlier_models: List[str]

    # Type-specific metrics
    entropy: Optional[float] = None
    coefficient_of_variation: Optional[float] = None
    jaccard_index: Optional[float] = None
    avg_similarity: Optional[float] = None
    weighted_confidence: Optional[float] = None
```

### 7.2 ModelPerformance

```python
@dataclass
class ModelPerformance:
    """Performance metrics for a single model."""
    model_id: str
    model_name: str

    # Agreement metrics
    total_fields: int
    fields_matching_consensus: int
    agreement_rate: float

    # Per-pass breakdown
    pass1_agreement: float
    pass2_agreement: float
    pass3_agreement: float

    # Outlier frequency
    outlier_count: int
    outlier_rate: float

    # Confidence calibration (Pass 2 & 3)
    avg_confidence_when_correct: float
    avg_confidence_when_wrong: float
```

### 7.3 JobEvaluation

```python
@dataclass
class JobEvaluation:
    """Complete evaluation for a single job posting."""
    job_id: str
    job_title: str
    company_name: str
    evaluated_at: str  # ISO timestamp

    # Models evaluated
    models: List[str]

    # Overall metrics
    overall_consensus_rate: float
    pass1_consensus_rate: float
    pass2_consensus_rate: float
    pass3_consensus_rate: float

    # Field evaluations
    field_evaluations: List[FieldEvaluation]

    # Model performance
    model_performance: Dict[str, ModelPerformance]

    # Consensus output (merged)
    consensus_output: Dict[str, Any]
```

### 7.4 BatchEvaluation

```python
@dataclass
class BatchEvaluation:
    """Evaluation across multiple job postings."""
    batch_id: str
    evaluated_at: str
    job_count: int

    # Aggregate metrics
    avg_consensus_rate: float

    # Field reliability rankings
    most_reliable_fields: List[Tuple[str, float]]  # (field, avg_agreement)
    least_reliable_fields: List[Tuple[str, float]]

    # Model rankings
    model_rankings: List[Tuple[str, float]]  # (model, avg_agreement)
```

---

## 8. Implementation Guide

### 8.1 Data Loading

```python
import json
from pathlib import Path
from typing import Dict, Any

def load_model_outputs(job_id: str, pass_num: int, base_path: str = "data/local") -> Dict[str, Dict]:
    """
    Load outputs from all 5 models for a specific pass.

    Returns:
        Dict mapping model_short_name -> parsed JSON
    """
    job_dir = Path(base_path) / job_id
    outputs = {}

    model_files = {
        "gpt-oss": f"pass{pass_num}-openai-gpt-oss-120b-1-0.json",
        "mistral": f"pass{pass_num}-mistral-mistral-large-3-675b-instruct.json",
        "gemma": f"pass{pass_num}-google-gemma-3-27b-it.json",
        "minimax": f"pass{pass_num}-minimax-minimax-m2.json",
        "qwen": f"pass{pass_num}-qwen-qwen3-vl-235b-a22b.json",
    }

    for model_name, filename in model_files.items():
        filepath = job_dir / filename
        if filepath.exists():
            with open(filepath) as f:
                outputs[model_name] = json.load(f)

    return outputs
```

### 8.2 Field-by-Field Evaluation Loop

```python
def evaluate_pass1_field(field_name: str, outputs: Dict[str, Dict]) -> FieldEvaluation:
    """Evaluate a single Pass 1 field across all models."""

    # Extract field values from each model
    values = {}
    for model, data in outputs.items():
        result = data.get("result", {})
        values[model] = result.get(field_name)

    # Determine field type and apply appropriate consensus function
    field_type = get_field_type(field_name)  # From classification matrix

    if field_type == "boolean":
        result = boolean_consensus(values)
    elif field_type == "enum":
        result = categorical_consensus(values)
    elif field_type == "numeric":
        result = numeric_consensus(values)
    elif field_type == "array":
        result = list_consensus(values)
    elif field_type == "string":
        result = string_consensus(values)
    else:
        raise ValueError(f"Unknown field type: {field_type}")

    return FieldEvaluation(
        field_name=field_name,
        field_type=field_type,
        pass_number=1,
        has_consensus=result.has_consensus,
        consensus_value=getattr(result, 'consensus_value', None) or getattr(result, 'consensus_list', None),
        agreement_rate=result.agreement_rate if hasattr(result, 'agreement_rate') else result.avg_jaccard,
        model_values=values,
        outlier_models=result.outlier_models if hasattr(result, 'outlier_models') else [],
        entropy=getattr(result, 'entropy', None),
        coefficient_of_variation=getattr(result, 'coefficient_of_variation', None),
        jaccard_index=getattr(result, 'avg_jaccard', None),
        avg_similarity=getattr(result, 'avg_similarity', None),
    )


def evaluate_pass2_field(field_path: str, outputs: Dict[str, Dict]) -> FieldEvaluation:
    """Evaluate a single Pass 2 inference field."""

    # Extract inference objects
    inference_objects = {}
    for model, data in outputs.items():
        result = data.get("result", {})
        inference = result.get("inference", {})

        # Navigate nested path (e.g., "seniority_and_role.seniority_level")
        parts = field_path.split(".")
        obj = inference
        for part in parts:
            obj = obj.get(part, {}) if isinstance(obj, dict) else {}

        if obj and isinstance(obj, dict) and "value" in obj:
            inference_objects[model] = obj
        else:
            inference_objects[model] = None

    result = confidence_aggregation(inference_objects)

    return FieldEvaluation(
        field_name=field_path,
        field_type="inference",
        pass_number=2,
        has_consensus=result.has_consensus,
        consensus_value=result.consensus_value,
        agreement_rate=result.agreement_rate,
        model_values={m: o.get("value") if o else None for m, o in inference_objects.items()},
        outlier_models=result.outlier_models,
        weighted_confidence=result.weighted_confidence,
    )
```

### 8.3 Report Generation

```python
def generate_evaluation_report(job_id: str) -> JobEvaluation:
    """Generate complete evaluation report for a job."""

    # Load all outputs
    pass1_outputs = load_model_outputs(job_id, 1)
    pass2_outputs = load_model_outputs(job_id, 2)
    pass3_outputs = load_model_outputs(job_id, 3)

    # Get job metadata from first available output
    first_output = list(pass1_outputs.values())[0]
    metadata = first_output.get("metadata", {})

    evaluations = []

    # Evaluate Pass 1 fields
    pass1_fields = [
        "ext_salary_disclosed", "ext_salary_min", "ext_salary_max",
        "ext_work_model_stated", "ext_employment_type_stated",
        "ext_must_have_hard_skills", "ext_nice_to_have_hard_skills",
        # ... all 52 fields
    ]
    for field in pass1_fields:
        evaluations.append(evaluate_pass1_field(field, pass1_outputs))

    # Evaluate Pass 2 fields
    pass2_fields = [
        "seniority_and_role.seniority_level",
        "seniority_and_role.job_family",
        "stack_and_cloud.primary_cloud",
        # ... all 25 inference paths
    ]
    for field in pass2_fields:
        evaluations.append(evaluate_pass2_field(field, pass2_outputs))

    # Calculate overall metrics
    pass1_evals = [e for e in evaluations if e.pass_number == 1]
    pass2_evals = [e for e in evaluations if e.pass_number == 2]
    pass3_evals = [e for e in evaluations if e.pass_number == 3]

    pass1_rate = sum(1 for e in pass1_evals if e.has_consensus) / len(pass1_evals) if pass1_evals else 0
    pass2_rate = sum(1 for e in pass2_evals if e.has_consensus) / len(pass2_evals) if pass2_evals else 0
    pass3_rate = sum(1 for e in pass3_evals if e.has_consensus) / len(pass3_evals) if pass3_evals else 0
    overall_rate = sum(1 for e in evaluations if e.has_consensus) / len(evaluations) if evaluations else 0

    return JobEvaluation(
        job_id=job_id,
        job_title=metadata.get("job_title", ""),
        company_name=metadata.get("company_name", ""),
        evaluated_at=datetime.now().isoformat(),
        models=list(pass1_outputs.keys()),
        overall_consensus_rate=overall_rate,
        pass1_consensus_rate=pass1_rate,
        pass2_consensus_rate=pass2_rate,
        pass3_consensus_rate=pass3_rate,
        field_evaluations=evaluations,
        model_performance={},  # Calculate separately
        consensus_output={e.field_name: e.consensus_value for e in evaluations if e.has_consensus}
    )
```

---

## 9. Example: Job 4323400548 Analysis

### 9.1 ext_salary_min (Numeric)

**Model Values**:
| Model | Value |
|-------|-------|
| gpt-oss | 111800.0 |
| mistral | 111800.0 |
| gemma | 111800.0 |
| minimax | 111800.0 |
| qwen | 111800.0 |

**Result**:
```python
NumericConsensusResult(
    consensus_value=111800.0,
    mean=111800.0,
    median=111800.0,
    std_dev=0.0,
    coefficient_of_variation=0.0,
    outlier_models=[],
    null_count=0,
    has_consensus=True
)
```

**Interpretation**: Perfect agreement (CV=0.0). All 5 models extracted the same salary.

### 9.2 ext_work_model_stated (Enum)

**Model Values**:
| Model | Value |
|-------|-------|
| gpt-oss | hybrid |
| mistral | hybrid |
| gemma | hybrid |
| minimax | hybrid |
| qwen | hybrid |

**Result**:
```python
CategoricalConsensusResult(
    consensus_value="hybrid",
    agreement_rate=1.0,
    entropy=0.0,
    value_distribution={"hybrid": 5},
    outlier_models=[],
    has_consensus=True
)
```

### 9.3 ext_must_have_hard_skills (Array)

**Model Values**:
| Model | Skills (normalized) |
|-------|---------------------|
| gpt-oss | aws, azure, gcp, sql, athena, python, etl, schema design, data lake, dagster, airflow, prefect, ci/cd, docker, kubernetes, terraform, cloudformation |
| mistral | aws, sql, python, etl, schema design, datalake, orchestration, dagster, airflow, prefect, ci/cd, docker, kubernetes, iac, terraform, cloudformation |
| gemma | aws, sql, python, data warehousing, etl, schema design, datalake, dagster, airflow, prefect, ci/cd, docker, kubernetes, iac, terraform, cloudformation, json, avro, parquet, iceberg |
| minimax | aws, sql, python, etl, schema design, datalake, orchestration, ci/cd, docker, kubernetes, iac |
| qwen | aws, azure, gcp, sql, athena, python, etl, schema design, datalake, dagster, airflow, prefect, ci/cd, docker, kubernetes, terraform, cloudformation, json, avro, parquet, iceberg |

**Consensus List** (appearing in 3+ models):
```
aws, sql, python, etl, schema design, datalake/data lake,
dagster, airflow, prefect, ci/cd, docker, kubernetes,
terraform, cloudformation
```

**Item Confidence**:
| Skill | Confidence |
|-------|------------|
| aws | 1.0 |
| python | 1.0 |
| sql | 1.0 |
| docker | 1.0 |
| kubernetes | 1.0 |
| ci/cd | 1.0 |
| terraform | 0.8 |
| airflow | 0.8 |
| dagster | 0.8 |
| prefect | 0.8 |
| azure | 0.4 |
| gcp | 0.4 |

### 9.4 inf_seniority_level (Inference Object)

**Model Values**:
| Model | Value | Confidence |
|-------|-------|------------|
| gpt-oss | senior | 0.95 |
| mistral | senior | 0.92 |
| gemma | senior | 0.90 |
| minimax | senior | 0.88 |
| qwen | senior | 0.91 |

**Result**:
```python
ConfidenceAggregationResult(
    consensus_value="senior",
    weighted_confidence=0.912,  # average
    agreement_rate=1.0,
    value_distribution={"senior": (5, 0.912)},
    outlier_models=[],
    has_consensus=True
)
```

### 9.5 ext_employment_type_stated (Enum - Divergent)

**Model Values**:
| Model | Value |
|-------|-------|
| gpt-oss | not_mentioned |
| mistral | full_time |
| gemma | full_time |
| minimax | full_time |
| qwen | full_time |

**Result**:
```python
CategoricalConsensusResult(
    consensus_value="full_time",
    agreement_rate=0.8,  # 4/5
    entropy=0.72,
    value_distribution={"full_time": 4, "not_mentioned": 1},
    outlier_models=["gpt-oss"],
    has_consensus=True
)
```

**Interpretation**: GPT-OSS is the outlier - it was too conservative and marked "not_mentioned" when other models correctly inferred "full_time".

---

## 10. Appendix

### 10.1 Complete Field Enumeration

See Section 2 (Field Classification Matrix) for the complete list of 109 fields.

### 10.2 Model Configuration Reference

```python
MODELS = {
    "gpt-oss": {
        "id": "openai.gpt-oss-120b-1:0",
        "name": "OpenAI GPT-OSS 120B",
        "params": "120B",
        "input_cost_per_1m": 0.15,
        "output_cost_per_1m": 0.60,
    },
    "mistral": {
        "id": "mistral.mistral-large-3-675b-instruct",
        "name": "Mistral Large 675B",
        "params": "675B",
        "input_cost_per_1m": 2.00,
        "output_cost_per_1m": 6.00,
    },
    "gemma": {
        "id": "google.gemma-3-27b-it",
        "name": "Google Gemma 3 27B",
        "params": "27B",
        "input_cost_per_1m": 0.23,
        "output_cost_per_1m": 0.38,
    },
    "minimax": {
        "id": "minimax.minimax-m2",
        "name": "MiniMax M2",
        "params": "~100B",
        "input_cost_per_1m": 0.30,
        "output_cost_per_1m": 1.20,
    },
    "qwen": {
        "id": "qwen.qwen3-vl-235b-a22b",
        "name": "Qwen3 235B",
        "params": "235B",
        "input_cost_per_1m": 0.22,
        "output_cost_per_1m": 0.88,
    },
}
```

### 10.3 Quality Thresholds

| Metric | Threshold | Interpretation |
|--------|-----------|----------------|
| Agreement Rate | ≥ 0.6 | Minimum for consensus (3/5) |
| Agreement Rate | ≥ 0.8 | Strong consensus (4/5) |
| Agreement Rate | = 1.0 | Perfect consensus (5/5) |
| CV (numeric) | ≤ 0.05 | Excellent agreement |
| CV (numeric) | ≤ 0.15 | Acceptable agreement |
| Jaccard (arrays) | ≥ 0.5 | Minimum overlap |
| Jaccard (arrays) | ≥ 0.7 | Good overlap |
| Shannon Entropy | ≤ 0.5 | Low uncertainty |
| Shannon Entropy | ≤ 1.0 | Moderate uncertainty |
| String Similarity | ≥ 0.85 | Near-identical text |
| Weighted Confidence | ≥ 0.8 | High confidence consensus |

---

## Changelog

- **v1.0** (2025-12-06): Initial version with complete framework
