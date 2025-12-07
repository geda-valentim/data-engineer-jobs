# AI Enrichment Technical Guide

> **Version**: 3.4
> **Last Updated**: 2025-12-07
> **Status**: Production Ready

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [The 3-Pass Pipeline](#3-the-3-pass-pipeline)
4. [Schema Evolution](#4-schema-evolution)
5. [Multi-Model Evaluation](#5-multi-model-evaluation)
6. [Key Decisions & Trade-offs](#6-key-decisions--trade-offs)
7. [Implementation Details](#7-implementation-details)
8. [Validation & Quality](#8-validation--quality)
9. [Improvements Made](#9-improvements-made)
10. [Current Results](#10-current-results)
11. [Usage Guide](#11-usage-guide)

---

## 1. Overview

### What is AI Enrichment?

The AI Enrichment pipeline uses Large Language Models (LLMs) to extract structured metadata from unstructured job posting text. It transforms free-text job descriptions into ~280 flattened columns of structured data.

### Primary Goals

1. **Extract Facts** - Salary, location, work model, skills, benefits
2. **Infer Context** - Seniority level, cloud focus, job family, visa friendliness
3. **Analyze Quality** - Red flags, company maturity, role clarity, recommendations

### Key Metrics

| Metric | Current Value | Target |
|--------|---------------|--------|
| Overall Consensus (5 LLMs) | **79.8%** | > 75% |
| Pass 1 Consensus | **88.1%** | > 85% |
| Pass 2 Consensus | **93.2%** | > 90% |
| Pass 3 Consensus | **62.8%** | > 60% |
| Cost per Job | **~$0.0012** | < $0.002 |

---

## 2. Architecture

### Pipeline Flow

```
LinkedIn Jobs (Silver Parquet)
         ↓
    ┌────────────────────────────────────────────┐
    │           AI ENRICHMENT PIPELINE           │
    │                                            │
    │   Pass 1: Extraction (factual data)        │
    │      ↓                                     │
    │   Pass 2: Inference (with confidence)      │
    │      ↓                                     │
    │   Pass 3: Analysis (complex signals)       │
    │                                            │
    └────────────────────────────────────────────┘
         ↓
  Enriched Jobs (Silver-AI Parquet)
```

### Components

```
src/lambdas/ai_enrichment/
├── discover_partitions/     # Find unprocessed partitions
│   └── handler.py
├── enrich_partition/        # Main processing
│   ├── handler.py           # Lambda entry point
│   ├── bedrock_client.py    # LLM invocation wrapper
│   ├── prompts/             # Pass 1, 2, 3 templates
│   │   ├── pass1_extraction.py
│   │   ├── pass2_inference.py
│   │   └── pass3_complex.py
│   ├── parsers/             # JSON parsing, validation
│   │   ├── json_parser.py
│   │   └── validators.py
│   └── flatteners/          # Nested → flat columns
│       ├── extraction.py
│       ├── inference.py
│       └── analysis.py
└── shared/
    └── s3_utils.py

src/evaluation/              # Inter-model evaluation
├── __init__.py
├── evaluator.py             # Main evaluation logic
├── consensus.py             # Consensus functions
├── models.py                # Dataclasses
├── field_registry.py        # Field definitions
└── report.py                # Report generation

scripts/ai-enrichment/       # Testing & evaluation
├── test_enrichment_local.py
├── test_enrichment_passes.py
└── test_enrichment_helpers.py
```

### Models Used

| Model | ID | Parameters | Cost/1M Tokens | Use |
|-------|-----|------------|----------------|-----|
| GPT-OSS | `openai.gpt-oss-120b-1:0` | 120B | $0.15 in / $0.60 out | Primary |
| Mistral | `mistral.mistral-large-3-675b-instruct` | 675B | $2.00 in / $6.00 out | Evaluation |
| Qwen | `qwen.qwen3-vl-235b-a22b` | 235B | $0.22 in / $0.88 out | Evaluation |
| MiniMax | `minimax.minimax-m2` | ~100B | $0.30 in / $1.20 out | Evaluation |
| Gemma | `google.gemma-3-27b-it` | 27B | $0.23 in / $0.38 out | Evaluation |

---

## 3. The 3-Pass Pipeline

### Pass 1: Extraction (Factual)

**Purpose**: Extract facts directly stated in the job posting.

**Fields**: 57 columns (`ext_*` prefix)

| Category | Fields | Examples |
|----------|--------|----------|
| Salary | 9 | `ext_salary_min`, `ext_salary_max`, `ext_salary_currency` |
| Skills | 4 | `ext_must_have_hard_skills[]`, `ext_nice_to_have_hard_skills[]` |
| Work Model | 3 | `ext_work_model_stated`, `ext_employment_type_stated` |
| Visa | 3 | `ext_visa_sponsorship_stated`, `ext_citizenship_text` |
| Benefits | 2 | `ext_benefits_mentioned[]`, `ext_pto_policy` |
| Contract | 4 | `ext_contract_type`, `ext_contract_duration_months` |
| AI/ML | 2 | `ext_llm_genai_mentioned`, `ext_feature_store_mentioned` |

**Key Rules**:
- Extract ONLY what is explicitly stated
- Use `null` when information is not found
- Use controlled vocabularies for enums

### Pass 2: Inference (Normalization)

**Purpose**: Infer information with confidence scores.

**Fields**: 25 inference objects → 100 columns (`inf_*` prefix)

Each field returns:
```json
{
  "value": "senior",
  "confidence": 0.95,
  "evidence": "Title says 'Senior Data Engineer', requires 5+ years",
  "source": "combined"
}
```

| Category | Fields | Examples |
|----------|--------|----------|
| Seniority & Role | 4 | `seniority_level`, `job_family`, `sub_specialty` |
| Stack & Cloud | 5 | `primary_cloud`, `processing_paradigm`, `orchestrator_category` |
| Geo & Work | 3 | `remote_restriction`, `timezone_focus` |
| Visa & Auth | 3 | `h1b_friendly`, `opt_cpt_friendly`, `citizenship_required` |
| Career Dev | 5 | `growth_path_clarity`, `mentorship_signals`, `career_tracks_available` |

**Confidence Guidelines**:
- `0.9-1.0`: Directly from Pass 1 or explicit in text
- `0.7-0.9`: Strong inference with multiple signals
- `0.5-0.7`: Moderate inference with 1-2 signals
- `<0.5`: Use `not_mentioned`

### Pass 3: Analysis (Complex)

**Purpose**: Subjective analysis for career advisors.

**Fields**: 46 fields → 124 columns (`anl_*` prefix)

| Category | Fields | Examples |
|----------|--------|----------|
| Company Maturity | 3 | `data_maturity_score`, `data_maturity_level`, `maturity_signals` |
| Red Flags | 4 | `scope_creep_score`, `overtime_risk_score`, `role_clarity` |
| Stakeholders | 6 | `reporting_structure`, `team_composition`, `cross_functional_embedded` |
| Tech Culture | 7 | `tech_culture_score`, `innovation_signals`, `dev_practices_mentioned` |
| Company Context | 5 | `company_stage_inferred`, `hiring_velocity`, `role_creation_type` |
| Summary | 12 | `strength_categories[]`, `concern_categories[]`, `recommendation_score` |

---

## 4. Schema Evolution

### Version History

| Version | Date | Changes |
|---------|------|---------|
| v3.0 | 2025-12-05 | Initial 3-pass pipeline |
| v3.1 | 2025-12-05 | Added Pass 2 career_development |
| v3.2 | 2025-12-06 | Complete Pass 2/3 implementation |
| v3.3 | 2025-12-06 | Added 19 new fields (AI/ML, culture, company context) |
| v3.4 | 2025-12-07 | Controlled vocabulary for Pass 3 summary |

### v3.4 Vocabulary Spec (Key Innovation)

**Problem**: Pass 3 summary arrays had ~0% consensus because each model wrote unique descriptive phrases:
- `summary.strengths`: 164 entries, 163 unique (99.4% uniqueness)
- `summary.concerns`: 139 entries, 136 unique (97.8% uniqueness)

**Solution**: Dual-field approach with controlled vocabulary:

```json
{
  "summary": {
    "strength_categories": ["transparent_salary", "modern_tech_stack", "equity_offered"],
    "strength_details": [
      "Transparent compensation ($180-220k + equity)",
      "Strong modern data stack (Snowflake, dbt, Airflow)"
    ],
    "concern_categories": ["overtime_likely", "no_visa_sponsorship"],
    "concern_details": [
      "Immediate start date suggests time pressure",
      "US work authorization required"
    ]
  }
}
```

**Vocabulary Categories**:

| Field | Enum Count | Example Values |
|-------|------------|----------------|
| `strength_categories` | 20 | `transparent_salary`, `modern_tech_stack`, `remote_friendly` |
| `concern_categories` | 20 | `vague_requirements`, `overtime_likely`, `startup_risk` |
| `best_fit_categories` | 15 | `senior_data_engineers`, `pipeline_developers`, `leadership_track` |
| `probe_categories` | 15 | `team_size_composition`, `on_call_expectations`, `career_growth_path` |
| `leverage_categories` | 10 | `rare_skill_match`, `domain_expertise`, `exceeds_requirements` |

**Impact**: Pass 3 consensus improved from ~60% to ~65% after vocabulary implementation.

---

## 5. Multi-Model Evaluation

### Philosophy: Consensus as Ground Truth

Without human-annotated labels, we use **model consensus** as the proxy for correctness:
- If 4/5 models agree → value is likely correct
- If models disagree significantly → field is ambiguous or poorly defined
- Outlier models → may indicate bugs or interpretation differences

### Consensus Thresholds

| Metric | Threshold | Interpretation |
|--------|-----------|----------------|
| Agreement Rate | ≥ 0.6 | Minimum consensus (3/5 models) |
| Agreement Rate | ≥ 0.8 | Strong consensus (4/5 models) |
| CV (numeric) | ≤ 0.15 | Acceptable variance |
| Jaccard (arrays) | ≥ 0.5 | Minimum overlap |

### Consensus Functions

| Function | Use Case | Key Metric |
|----------|----------|------------|
| `categorical_consensus()` | Enum fields | Agreement rate, Shannon entropy |
| `numeric_consensus()` | Salary, scores | Coefficient of variation, Z-score |
| `boolean_consensus()` | True/False fields | Agreement rate |
| `list_consensus()` | Skills, benefits | Jaccard index, item confidence |
| `confidence_aggregation()` | Inference objects | Weighted confidence |

### Evaluation Output

```python
@dataclass
class JobEvaluation:
    job_id: str
    job_title: str
    company_name: str
    models: List[str]
    overall_consensus_rate: float
    pass1_consensus_rate: float
    pass2_consensus_rate: float
    pass3_consensus_rate: float
    field_evaluations: List[FieldEvaluation]
    model_performance: Dict[str, ModelPerformance]
    high_disagreement_fields: List[str]
```

---

## 6. Key Decisions & Trade-offs

### Decision 1: Per-Record Fault Tolerance

**Context**: No budget for reprocessing failed partitions.

**Decision**: Failures are tracked per-record, not per-partition.

**Implementation**:
- Each job has `pass1_success`, `pass2_success`, `pass3_success` flags
- Failed jobs are marked but don't block other jobs
- `enrichment_errors` column stores error details

**Trade-off**: Slightly more complex logic, but guarantees partition always written.

### Decision 2: Cascading Context Architecture

**Context**: Each pass builds on previous results.

**Decision**: Pass 2 receives Pass 1 output; Pass 3 receives Pass 1 + Pass 2.

**Benefits**:
- More accurate inference with prior context
- Reduces duplicate extraction
- Enables confidence calibration

**Trade-off**: Higher token usage per job, but better accuracy.

### Decision 3: Controlled Vocabulary for Subjective Fields

**Context**: Free-text summary arrays had 0% consensus.

**Decision**: Split into `*_categories` (enum) and `*_details` (text).

**Benefits**:
- Measurable inter-model consensus
- Structured data for downstream queries
- Rich context preserved in details

**Trade-off**: Larger prompt, ~80 enum values to maintain.

### Decision 4: Primary Model vs Multi-Model Evaluation

**Context**: Need to balance cost and validation.

**Decision**:
- **Production**: Use GPT-OSS (cheapest) for all passes
- **Evaluation**: Run 5 models for validation & consensus

**Costs**:
- GPT-OSS only: ~$0.0012/job
- 5-model evaluation: ~$0.015/job (12x more)

**Trade-off**: Higher dev cost, but validated quality before production.

### Decision 5: "Thinking Model" Suppression

**Context**: Some models output `<reasoning>` tags before JSON.

**Problem**: Reasoning content was consuming output tokens, causing truncation.

**Solution**: Added `include_reasoning: false` for thinking models (GPT-OSS, DeepSeek R1).

```python
def _is_thinking_model(self, model_id: str) -> bool:
    thinking_patterns = (
        "openai.gpt-oss",    # GPT-OSS outputs <reasoning> tags
        "kimi-k2-thinking",
        "deepseek.r1",
    )
    return any(pattern in model_id for pattern in thinking_patterns)
```

### Decision 6: Pass-Specific max_tokens

**Context**: Pass 3 output is larger (~500 lines JSON).

**Problem**: Default 4096 tokens was truncating Pass 3 output.

**Solution**: Different limits per pass:

```python
DEFAULT_MAX_TOKENS = {
    "pass1": 4096,
    "pass2": 4096,
    "pass3": 32768,  # Large JSON schema
}
```

---

## 7. Implementation Details

### BedrockClient Configuration

```python
class BedrockClient:
    def __init__(
        self,
        model_ids: Optional[Dict[str, str]] = None,
        region: str = "us-east-1",
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        self.model_ids = model_ids or {
            "pass1": "openai.gpt-oss-120b-1:0",
            "pass2": "openai.gpt-oss-120b-1:0",
            "pass3": "openai.gpt-oss-120b-1:0",
        }
```

**Features**:
- Exponential backoff on throttling
- Automatic retry on transient errors
- Cost tracking per invocation
- Multi-model format support (OpenAI, Claude, generic)

### Prompt Engineering Patterns

**1. Critical Rules at Top**:
```markdown
## ⚠️ CRITICAL WARNING - READ FIRST

NEVER classify based on section title alone.
ALWAYS look at the qualifier word for EACH skill.
```

**2. Exact Examples with Correct/Wrong**:
```markdown
CORRECT:
✅ must_have_hard_skills: ["SQL", "Python", "dbt"]

WRONG (DO NOT DO THIS):
❌ nice_to_have_hard_skills: ["SQL", "Python", "dbt"]
```

**3. Explicit Enum Definitions**:
```markdown
### work_model_stated
Values: "remote" | "hybrid" | "onsite" | "not_mentioned"
```

### Flattening Strategy

Nested inference objects are flattened to 4 columns each:

```python
# Input: {"seniority_level": {"value": "senior", "confidence": 0.95, ...}}
# Output:
#   inf_seniority_level = "senior"
#   inf_seniority_level_confidence = 0.95
#   inf_seniority_level_evidence = "Title says Senior..."
#   inf_seniority_level_source = "combined"
```

---

## 8. Validation & Quality

### Field Registry

All 114 fields are registered with types:

```python
PASS1_FIELDS = {
    "ext_salary_disclosed": BOOLEAN,
    "ext_salary_min": NUMERIC,
    "ext_work_model_stated": ENUM,
    "ext_must_have_hard_skills": ARRAY,
    # ...
}
```

### Validation Checks

1. **JSON Structure** - Valid JSON returned
2. **Required Sections** - All sections present
3. **Required Fields** - All fields present
4. **Enum Values** - Values in allowed set
5. **Confidence Range** - 0.0 ≤ confidence ≤ 1.0
6. **Evidence Present** - Non-empty reasoning

### Quality Thresholds

| Field Category | Acceptable Consensus |
|----------------|----------------------|
| Salary (numeric) | CV ≤ 0.05 (5% variance) |
| Enum fields | Agreement ≥ 60% |
| Array fields | Jaccard ≥ 0.5 |
| Boolean fields | Agreement ≥ 60% |

---

## 9. Improvements Made

### Issue: Pass 3 Output Truncation

**Symptom**: Pass 3 JSON cut off mid-response (~372 lines, then ~235 lines).

**Root Causes**:
1. Default `max_tokens=4096` too low for Pass 3
2. Hardcoded `max_tokens=4096` in test script overriding client defaults
3. `<reasoning>` tags bloating response before JSON

**Fixes Applied**:

1. **bedrock_client.py** - Pass-specific max_tokens:
```python
DEFAULT_MAX_TOKENS = {
    "pass1": 4096,
    "pass2": 4096,
    "pass3": 32768,
}
```

2. **test_enrichment_passes.py** - Removed hardcoded limit:
```python
# Before: max_tokens=4096
# After: uses DEFAULT_MAX_TOKENS from BedrockClient
```

3. **bedrock_client.py** - Suppressed reasoning:
```python
if self._is_thinking_model(model_id):
    body["include_reasoning"] = False
```

**Result**: Pass 3 now returns complete 266-line JSON.

### Issue: Skills Classification Failure

**Symptom**: Eames Consulting job had 0 must-have skills, 29 nice-to-have.

**Root Cause**: LLM classified based on section title ("Preferred Qualifications") instead of internal qualifiers ("Strong proficiency in...").

**Fix**: Added prominent warning with exact example:
```markdown
⚠️ CRITICAL WARNING
Job Section: "Preferred Qualifications"
Content: "Strong proficiency in SQL and Python"
CORRECT: must_have (due to "Strong")
WRONG: nice_to_have (don't use section title)
```

### Issue: Pass 3 Summary Low Consensus

**Symptom**: 0% consensus on `summary.strengths`, `summary.concerns`, etc.

**Root Cause**: Each model wrote unique descriptive phrases.

**Fix**: v3.4 controlled vocabulary with dual-field approach:
- `strength_categories`: `["transparent_salary", "modern_tech_stack"]`
- `strength_details`: `["Transparent salary ($180k)...", "Modern stack..."]`

**Result**: Pass 3 consensus improved from ~60% to ~65%.

---

## 10. Current Results

### Evaluation Summary (10 Jobs, 5 Models)

| Metric | V1 (Before) | V2 (After) | Change |
|--------|-------------|------------|--------|
| Overall Consensus | 81.5% | 79.8% | -1.7% |
| Pass 1 Consensus | 89.4% | 88.1% | -1.3% |
| Pass 2 Consensus | 96.0% | 93.2% | -2.8% |
| Pass 3 Consensus | 64.4% | 62.8% | -1.6% |

> Note: Small decreases may be due to stricter validation or different field counting.

### Per-Job Results (V2)

| Job ID | Company | Overall | Pass 1 | Pass 2 | Pass 3 |
|--------|---------|---------|--------|--------|--------|
| 4323400548 | SimpliSafe | 80.8% | 87.0% | 96.0% | 65.2% |
| 4325829597 | Tata Consultancy | 84.0% | 94.4% | 96.0% | 65.2% |
| 4325839911 | Mattoni 1873 | 79.2% | 88.9% | 100.0% | 56.5% |
| 4325889818 | aKUBE | 83.2% | 88.9% | 100.0% | 67.4% |
| 4325939213 | Tata Consultancy | 83.2% | 88.9% | 100.0% | 67.4% |
| 4325939525 | Pacer Group | 84.8% | 92.6% | 92.0% | 71.7% |
| 4325948158 | Manchester Digital | 73.6% | 87.0% | 88.0% | 50.0% |
| 4326005551 | Equifax | 71.2% | 81.5% | 76.0% | 56.5% |
| 4342313220 | MUSINSA | 74.4% | 83.3% | 88.0% | 56.5% |
| 4342323073 | Ursa Major | 84.0% | 88.9% | 96.0% | 71.7% |

### High-Disagreement Fields (Recurring)

| Field | Issue | Recommended Fix |
|-------|-------|-----------------|
| `ext_salary_period` | annual vs not_disclosed | Clarify rules |
| `ext_salary_currency` | Currency detection varies | Add location-based fallback |
| `ext_allowed_countries` | Array extraction inconsistent | Structured extraction |
| `summary.*_categories` | Vocabulary interpretation | Add more examples to prompt |

---

## 11. Usage Guide

### Running Enrichment Locally

```bash
#Running by date 
python scripts/ai-enrichment/test_enrichment_local.py --pass3  --s3-source  --date=2025-12-05  --limit=10  --save-json --multiple-models

# Test Pass 1 only
python scripts/ai-enrichment/test_enrichment_local.py --pass1



# Test Pass 2 only (requires Pass 1 cache)
python scripts/ai-enrichment/test_enrichment_local.py --pass2 --cache

# Test all 3 passes
python scripts/ai-enrichment/test_enrichment_local.py --all

# Test with multiple models
python scripts/ai-enrichment/test_enrichment_passes.py --all-models

# Save results for inter-model evaluation
python scripts/ai-enrichment/test_enrichment_passes.py --all-models --save-json
```

### Running Inter-Model Evaluation

```bash
# Evaluate single job
python scripts/evaluate_models.py 4323400548

# Evaluate all jobs
python scripts/evaluate_models.py --all --output reports/

# JSON output format
python scripts/evaluate_models.py 4323400548 --format json
```

### Environment Variables

```bash
# Override model for specific pass
export BEDROCK_MODEL_PASS1="anthropic.claude-3-haiku-20240307-v1:0"
export BEDROCK_MODEL_PASS2="openai.gpt-oss-120b-1:0"
export BEDROCK_MODEL_PASS3="openai.gpt-oss-120b-1:0"

# AWS region
export AWS_REGION="us-east-1"
```

### Data Locations

| Data | Location |
|------|----------|
| Raw LLM responses | `data/local/{job_id}/pass{1,2,3}-{model}-raw.txt` |
| Parsed JSON | `data/local/{job_id}/pass{1,2,3}-{model}.json` |
| Evaluation reports | `reports/evaluation_{job_id}.md` |
| Summary report | `reports/SUMMARY_ALL_JOBS.md` |

---

## Appendix A: Complete Field List

### Pass 1 Fields (57)

| Field | Type | Description |
|-------|------|-------------|
| `ext_salary_disclosed` | bool | Salary mentioned in posting |
| `ext_salary_min` | float | Minimum salary |
| `ext_salary_max` | float | Maximum salary |
| `ext_salary_period` | enum | yearly, monthly, hourly, not_mentioned |
| `ext_salary_currency` | string | USD, EUR, GBP, etc. |
| `ext_work_model_stated` | enum | remote, hybrid, onsite, not_mentioned |
| `ext_employment_type_stated` | enum | full_time, contract, part_time, etc. |
| `ext_contract_type` | enum | permanent, fixed_term, contract_to_hire, etc. |
| `ext_visa_sponsorship_stated` | enum | will_sponsor, will_not_sponsor, etc. |
| `ext_must_have_hard_skills` | array | Required technical skills |
| `ext_nice_to_have_hard_skills` | array | Preferred technical skills |
| `ext_must_have_soft_skills` | array | Required soft skills (22 canonical) |
| `ext_benefits_mentioned` | array | Listed benefits |
| `ext_llm_genai_mentioned` | bool | LLM/GenAI technologies mentioned |
| ... | ... | (see field_registry.py for full list) |

### Pass 2 Fields (25 inference objects = 100 columns)

| Field | Type | Enum Values |
|-------|------|-------------|
| `seniority_level` | enum | intern → distinguished |
| `job_family` | enum | data_engineer, ml_engineer, etc. |
| `primary_cloud` | enum | aws, azure, gcp, multi, on_prem |
| `processing_paradigm` | enum | batch, streaming, hybrid |
| `h1b_friendly` | bool | H1B sponsorship available |
| `growth_path_clarity` | enum | explicit, implied, vague |
| ... | ... | (see field_registry.py for full list) |

### Pass 3 Fields (46 fields = 124 columns)

| Field | Type | Range/Values |
|-------|------|--------------|
| `data_maturity_score` | int | 1-5 |
| `scope_creep_score` | float | 0.0-1.0 |
| `overtime_risk_score` | float | 0.0-1.0 |
| `role_clarity` | enum | clear, vague, multi_role |
| `company_stage_inferred` | enum | startup_seed → enterprise |
| `strength_categories` | array | 20 enum values |
| `recommendation_score` | float | 0.0-1.0 |
| ... | ... | (see field_registry.py for full list) |

---

## Appendix B: Controlled Vocabulary Reference

### Strength Categories (20)

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

### Concern Categories (20)

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

---

## Appendix C: Related Documentation

| Document | Purpose |
|----------|---------|
| [sprint-0-overview.md](planning/ai-enrichment/sprint-0-overview.md) | Original project plan |
| [INTER_MODEL_EVALUATION.md](planning/ai-enrichment/INTER_MODEL_EVALUATION.md) | Evaluation framework spec |
| [PASS3_VOCABULARY_SPEC.md](planning/ai-enrichment/PASS3_VOCABULARY_SPEC.md) | v3.4 vocabulary definitions |
| [CHANGELOG_v3.3.md](planning/ai-enrichment/CHANGELOG_v3.3.md) | Schema v3.3 changes |
| [PRIORITY_FIXES_IMPLEMENTED.md](planning/ai-enrichment/PRIORITY_FIXES_IMPLEMENTED.md) | Pass 1 extraction fixes |

---

*Document generated: 2025-12-07*
