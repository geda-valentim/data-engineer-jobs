# Sprint 4: Pass 3 - Complex Analysis

> **Sprint:** 4 of 5
> **Duration:** 2-3 days
> **Predecessor:** Sprint 3 (Pass 2 - Inference)
> **Goal:** Implement Pass 3 analysis with full cascading context, complete pipeline

---

## Overview

Pass 3 is the **analysis phase** that receives full context from Pass 1 (extraction) and Pass 2 (inference) to perform complex assessments:

- **Data maturity assessment** - How sophisticated is the data stack?
- **Red flag detection** - Scope creep, unrealistic expectations, workload risk
- **Company culture signals** - Work-life balance, growth opportunities
- **Summary generation** - Actionable strengths, concerns, and fit recommendations

---

## Tasks

### 4.1 Implement Pass 3 Prompt

**File:** `src/lambdas/ai_enrichment/enrich_partition/prompts/pass3_analysis.py`

```python
"""
Pass 3: Complex Analysis Prompt
Receives Pass 1 extraction + Pass 2 inference for comprehensive analysis.
"""

PASS3_SYSTEM_PROMPT = """You are an expert job market analyst specializing in data engineering roles.
Your task is to analyze job postings and provide actionable insights for candidates.

## Analysis Guidelines

1. **Data Maturity Assessment**
   - Evaluate based on tools, processes, and organizational maturity signals
   - Consider: data governance, MLOps, DataOps, testing practices
   - Score 1-5 where: 1=Ad-hoc, 2=Developing, 3=Defined, 4=Managed, 5=Optimizing

2. **Red Flag Detection**
   - Look for unrealistic expectations (too many skills, low pay)
   - Identify scope creep signals ("wear many hats", "fast-paced")
   - Note workload concerns (on-call without compensation, 24/7 support)
   - Flag vague descriptions hiding actual responsibilities

3. **Company Culture Signals**
   - Work-life balance indicators (flexible hours, remote, PTO policy)
   - Growth opportunities (training budget, conferences, career paths)
   - Team dynamics (collaboration, mentorship mentions)
   - Compensation transparency

4. **Summary Generation**
   - Be specific and actionable
   - Reference evidence from the job posting
   - Tailor fit_for to specific candidate profiles

## Anti-Hallucination Rules

- ONLY analyze information present in the job data or reasonably inferred
- If insufficient information for an assessment, use null
- Be conservative with red flag detection - only flag clear signals
- Confidence scores must reflect actual evidence strength
- Do not make up company information not in the posting"""


PASS3_USER_PROMPT = """Analyze this job posting using the extracted facts and inferences provided.

## Job Information
<job_data>
Title: {title}
Company: {company}
Location: {location}
Description:
{description}
</job_data>

## Pass 1 Extraction (Facts)
<pass1_extraction>
{pass1_json}
</pass1_extraction>

## Pass 2 Inference (Derived Insights)
<pass2_inference>
{pass2_json}
</pass2_inference>

## Required Analysis

Provide your analysis in the following JSON structure:

```json
{{
  "data_maturity": {{
    "score": <1-5 integer or null>,
    "level": "<ad_hoc|developing|defined|managed|optimizing|null>",
    "evidence": "<string explaining the assessment>",
    "confidence": <0.0-1.0>
  }},
  "red_flags": {{
    "scope_creep": {{
      "detected": <boolean>,
      "score": <0.0-1.0 risk level>,
      "signals": ["<signal 1>", "<signal 2>"],
      "evidence": "<string>"
    }},
    "unrealistic_expectations": {{
      "detected": <boolean>,
      "score": <0.0-1.0 risk level>,
      "signals": ["<signal 1>", "<signal 2>"],
      "evidence": "<string>"
    }},
    "workload_concerns": {{
      "detected": <boolean>,
      "score": <0.0-1.0 risk level>,
      "signals": ["<signal 1>", "<signal 2>"],
      "evidence": "<string>"
    }},
    "vague_description": {{
      "detected": <boolean>,
      "score": <0.0-1.0 risk level>,
      "signals": ["<signal 1>", "<signal 2>"],
      "evidence": "<string>"
    }},
    "overall_risk_score": <0.0-1.0 aggregate>,
    "recommendation": "<proceed|proceed_with_caution|investigate_further|avoid>"
  }},
  "culture_signals": {{
    "work_life_balance": {{
      "score": <1-5 or null>,
      "positive_signals": ["<signal>"],
      "negative_signals": ["<signal>"],
      "evidence": "<string>"
    }},
    "growth_opportunities": {{
      "score": <1-5 or null>,
      "signals": ["<signal>"],
      "evidence": "<string>"
    }},
    "team_environment": {{
      "score": <1-5 or null>,
      "signals": ["<signal>"],
      "evidence": "<string>"
    }},
    "compensation_transparency": {{
      "score": <1-5 or null>,
      "signals": ["<signal>"],
      "evidence": "<string>"
    }},
    "overall_culture_score": <1-5 or null>,
    "confidence": <0.0-1.0>
  }},
  "role_assessment": {{
    "technical_depth": "<shallow|moderate|deep|null>",
    "leadership_component": <boolean or null>,
    "cross_functional": <boolean or null>,
    "innovation_focus": <boolean or null>,
    "maintenance_focus": <boolean or null>,
    "evidence": "<string>"
  }},
  "summary": {{
    "strengths": [
      "<strength 1 - specific and actionable>",
      "<strength 2>",
      "<strength 3>"
    ],
    "concerns": [
      "<concern 1 - specific and actionable>",
      "<concern 2>"
    ],
    "fit_for": [
      "<candidate profile 1 this role suits>",
      "<candidate profile 2>"
    ],
    "not_fit_for": [
      "<candidate profile this role does NOT suit>"
    ],
    "key_questions_to_ask": [
      "<question to clarify during interview>",
      "<question 2>"
    ],
    "one_liner": "<single sentence summary of the opportunity>"
  }},
  "metadata": {{
    "analysis_confidence": <0.0-1.0 overall>,
    "low_confidence_fields": ["<field_name>"],
    "analysis_notes": "<any caveats or limitations>"
  }}
}}
```

Return ONLY valid JSON, no additional text."""


def build_pass3_prompt(
    title: str,
    company: str,
    location: str,
    description: str,
    pass1_result: dict,
    pass2_result: dict
) -> tuple[str, str]:
    """
    Build Pass 3 prompt with full cascading context.

    Args:
        title: Job title
        company: Company name
        location: Job location
        description: Full job description
        pass1_result: JSON result from Pass 1 extraction
        pass2_result: JSON result from Pass 2 inference

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    import json

    # Format Pass 1 and Pass 2 results as pretty JSON
    pass1_json = json.dumps(pass1_result, indent=2) if pass1_result else "{}"
    pass2_json = json.dumps(pass2_result, indent=2) if pass2_result else "{}"

    user_prompt = PASS3_USER_PROMPT.format(
        title=title or "Not specified",
        company=company or "Not specified",
        location=location or "Not specified",
        description=description or "No description provided",
        pass1_json=pass1_json,
        pass2_json=pass2_json
    )

    return PASS3_SYSTEM_PROMPT, user_prompt


# Output schema for validation
PASS3_SCHEMA = {
    "type": "object",
    "required": ["data_maturity", "red_flags", "culture_signals", "summary", "metadata"],
    "properties": {
        "data_maturity": {
            "type": "object",
            "properties": {
                "score": {"type": ["integer", "null"], "minimum": 1, "maximum": 5},
                "level": {"type": ["string", "null"], "enum": ["ad_hoc", "developing", "defined", "managed", "optimizing", None]},
                "evidence": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1}
            }
        },
        "red_flags": {
            "type": "object",
            "properties": {
                "scope_creep": {"type": "object"},
                "unrealistic_expectations": {"type": "object"},
                "workload_concerns": {"type": "object"},
                "vague_description": {"type": "object"},
                "overall_risk_score": {"type": "number", "minimum": 0, "maximum": 1},
                "recommendation": {"type": "string", "enum": ["proceed", "proceed_with_caution", "investigate_further", "avoid"]}
            }
        },
        "culture_signals": {
            "type": "object",
            "properties": {
                "work_life_balance": {"type": "object"},
                "growth_opportunities": {"type": "object"},
                "team_environment": {"type": "object"},
                "compensation_transparency": {"type": "object"},
                "overall_culture_score": {"type": ["integer", "null"]},
                "confidence": {"type": "number"}
            }
        },
        "role_assessment": {
            "type": "object"
        },
        "summary": {
            "type": "object",
            "required": ["strengths", "concerns", "fit_for", "one_liner"],
            "properties": {
                "strengths": {"type": "array", "items": {"type": "string"}},
                "concerns": {"type": "array", "items": {"type": "string"}},
                "fit_for": {"type": "array", "items": {"type": "string"}},
                "not_fit_for": {"type": "array", "items": {"type": "string"}},
                "key_questions_to_ask": {"type": "array", "items": {"type": "string"}},
                "one_liner": {"type": "string"}
            }
        },
        "metadata": {
            "type": "object",
            "properties": {
                "analysis_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "low_confidence_fields": {"type": "array", "items": {"type": "string"}},
                "analysis_notes": {"type": "string"}
            }
        }
    }
}
```

---

### 4.2 Add Analysis Validator

**File:** `src/lambdas/ai_enrichment/enrich_partition/parsers/validators.py` (append)

```python
# Add to existing validators.py

def validate_analysis_response(data: dict) -> tuple[bool, list[str]]:
    """
    Validate Pass 3 analysis response structure.

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    # Required top-level keys
    required_keys = ["data_maturity", "red_flags", "culture_signals", "summary", "metadata"]
    for key in required_keys:
        if key not in data:
            errors.append(f"Missing required key: {key}")

    if errors:
        return False, errors

    # Validate data_maturity
    dm = data.get("data_maturity", {})
    if dm.get("score") is not None:
        if not isinstance(dm["score"], int) or not 1 <= dm["score"] <= 5:
            errors.append("data_maturity.score must be integer 1-5 or null")
    if dm.get("confidence") is not None:
        if not isinstance(dm["confidence"], (int, float)) or not 0 <= dm["confidence"] <= 1:
            errors.append("data_maturity.confidence must be 0-1")

    # Validate red_flags
    rf = data.get("red_flags", {})
    flag_types = ["scope_creep", "unrealistic_expectations", "workload_concerns", "vague_description"]
    for flag_type in flag_types:
        flag = rf.get(flag_type, {})
        if flag.get("score") is not None:
            if not isinstance(flag["score"], (int, float)) or not 0 <= flag["score"] <= 1:
                errors.append(f"red_flags.{flag_type}.score must be 0-1")
        if flag.get("detected") is not None and not isinstance(flag["detected"], bool):
            errors.append(f"red_flags.{flag_type}.detected must be boolean")

    if rf.get("overall_risk_score") is not None:
        if not isinstance(rf["overall_risk_score"], (int, float)) or not 0 <= rf["overall_risk_score"] <= 1:
            errors.append("red_flags.overall_risk_score must be 0-1")

    valid_recommendations = ["proceed", "proceed_with_caution", "investigate_further", "avoid"]
    if rf.get("recommendation") and rf["recommendation"] not in valid_recommendations:
        errors.append(f"red_flags.recommendation must be one of {valid_recommendations}")

    # Validate culture_signals
    cs = data.get("culture_signals", {})
    culture_sections = ["work_life_balance", "growth_opportunities", "team_environment", "compensation_transparency"]
    for section in culture_sections:
        sec = cs.get(section, {})
        if sec.get("score") is not None:
            if not isinstance(sec["score"], int) or not 1 <= sec["score"] <= 5:
                errors.append(f"culture_signals.{section}.score must be integer 1-5 or null")

    if cs.get("overall_culture_score") is not None:
        if not isinstance(cs["overall_culture_score"], int) or not 1 <= cs["overall_culture_score"] <= 5:
            errors.append("culture_signals.overall_culture_score must be integer 1-5 or null")

    if cs.get("confidence") is not None:
        if not isinstance(cs["confidence"], (int, float)) or not 0 <= cs["confidence"] <= 1:
            errors.append("culture_signals.confidence must be 0-1")

    # Validate summary
    summary = data.get("summary", {})
    summary_arrays = ["strengths", "concerns", "fit_for"]
    for arr_name in summary_arrays:
        arr = summary.get(arr_name)
        if arr is not None and not isinstance(arr, list):
            errors.append(f"summary.{arr_name} must be an array")

    if not summary.get("one_liner"):
        errors.append("summary.one_liner is required")

    # Validate metadata
    meta = data.get("metadata", {})
    if meta.get("analysis_confidence") is not None:
        if not isinstance(meta["analysis_confidence"], (int, float)) or not 0 <= meta["analysis_confidence"] <= 1:
            errors.append("metadata.analysis_confidence must be 0-1")

    if meta.get("low_confidence_fields") is not None:
        if not isinstance(meta["low_confidence_fields"], list):
            errors.append("metadata.low_confidence_fields must be an array")

    return len(errors) == 0, errors
```

---

### 4.3 Create Analysis Flattener

**File:** `src/lambdas/ai_enrichment/enrich_partition/flatteners/analysis.py`

```python
"""
Flattener for Pass 3 (Analysis) nested JSON to flat columns.
All output columns are prefixed with 'anl_'.
"""

from typing import Any, Optional


def flatten_analysis(data: dict) -> dict:
    """
    Flatten Pass 3 analysis JSON to flat column structure.

    Args:
        data: Pass 3 analysis JSON response

    Returns:
        Dict with flat column names (anl_* prefix)
    """
    result = {}

    # Helper functions
    def safe_get(d: dict, *keys, default=None) -> Any:
        """Safely get nested dict value."""
        for key in keys:
            if isinstance(d, dict):
                d = d.get(key, default)
            else:
                return default
        return d

    def join_list(items: Optional[list], sep: str = "; ") -> Optional[str]:
        """Join list items into string, return None if empty."""
        if not items:
            return None
        return sep.join(str(item) for item in items if item)

    # Data Maturity
    dm = data.get("data_maturity", {})
    result["anl_data_maturity_score"] = dm.get("score")
    result["anl_data_maturity_level"] = dm.get("level")
    result["anl_data_maturity_evidence"] = dm.get("evidence")
    result["anl_data_maturity_confidence"] = dm.get("confidence")

    # Red Flags - Scope Creep
    rf = data.get("red_flags", {})
    sc = rf.get("scope_creep", {})
    result["anl_red_flag_scope_creep"] = sc.get("detected")
    result["anl_red_flag_scope_creep_score"] = sc.get("score")
    result["anl_red_flag_scope_creep_signals"] = join_list(sc.get("signals"))
    result["anl_red_flag_scope_creep_evidence"] = sc.get("evidence")

    # Red Flags - Unrealistic Expectations
    ue = rf.get("unrealistic_expectations", {})
    result["anl_red_flag_unrealistic"] = ue.get("detected")
    result["anl_red_flag_unrealistic_score"] = ue.get("score")
    result["anl_red_flag_unrealistic_signals"] = join_list(ue.get("signals"))
    result["anl_red_flag_unrealistic_evidence"] = ue.get("evidence")

    # Red Flags - Workload Concerns
    wc = rf.get("workload_concerns", {})
    result["anl_red_flag_workload"] = wc.get("detected")
    result["anl_red_flag_workload_score"] = wc.get("score")
    result["anl_red_flag_workload_signals"] = join_list(wc.get("signals"))
    result["anl_red_flag_workload_evidence"] = wc.get("evidence")

    # Red Flags - Vague Description
    vd = rf.get("vague_description", {})
    result["anl_red_flag_vague"] = vd.get("detected")
    result["anl_red_flag_vague_score"] = vd.get("score")
    result["anl_red_flag_vague_signals"] = join_list(vd.get("signals"))
    result["anl_red_flag_vague_evidence"] = vd.get("evidence")

    # Red Flags - Aggregate
    result["anl_red_flag_overall_risk"] = rf.get("overall_risk_score")
    result["anl_red_flag_recommendation"] = rf.get("recommendation")

    # Culture Signals - Work-Life Balance
    cs = data.get("culture_signals", {})
    wlb = cs.get("work_life_balance", {})
    result["anl_culture_wlb_score"] = wlb.get("score")
    result["anl_culture_wlb_positive"] = join_list(wlb.get("positive_signals"))
    result["anl_culture_wlb_negative"] = join_list(wlb.get("negative_signals"))
    result["anl_culture_wlb_evidence"] = wlb.get("evidence")

    # Culture Signals - Growth
    go = cs.get("growth_opportunities", {})
    result["anl_culture_growth_score"] = go.get("score")
    result["anl_culture_growth_signals"] = join_list(go.get("signals"))
    result["anl_culture_growth_evidence"] = go.get("evidence")

    # Culture Signals - Team
    te = cs.get("team_environment", {})
    result["anl_culture_team_score"] = te.get("score")
    result["anl_culture_team_signals"] = join_list(te.get("signals"))
    result["anl_culture_team_evidence"] = te.get("evidence")

    # Culture Signals - Compensation Transparency
    ct = cs.get("compensation_transparency", {})
    result["anl_culture_comp_score"] = ct.get("score")
    result["anl_culture_comp_signals"] = join_list(ct.get("signals"))
    result["anl_culture_comp_evidence"] = ct.get("evidence")

    # Culture Signals - Aggregate
    result["anl_culture_overall_score"] = cs.get("overall_culture_score")
    result["anl_culture_confidence"] = cs.get("confidence")

    # Role Assessment
    ra = data.get("role_assessment", {})
    result["anl_role_technical_depth"] = ra.get("technical_depth")
    result["anl_role_leadership"] = ra.get("leadership_component")
    result["anl_role_cross_functional"] = ra.get("cross_functional")
    result["anl_role_innovation_focus"] = ra.get("innovation_focus")
    result["anl_role_maintenance_focus"] = ra.get("maintenance_focus")
    result["anl_role_evidence"] = ra.get("evidence")

    # Summary
    summary = data.get("summary", {})
    result["anl_summary_strengths"] = join_list(summary.get("strengths"))
    result["anl_summary_concerns"] = join_list(summary.get("concerns"))
    result["anl_summary_fit_for"] = join_list(summary.get("fit_for"))
    result["anl_summary_not_fit_for"] = join_list(summary.get("not_fit_for"))
    result["anl_summary_questions"] = join_list(summary.get("key_questions_to_ask"))
    result["anl_summary_one_liner"] = summary.get("one_liner")

    # Metadata
    meta = data.get("metadata", {})
    result["anl_confidence"] = meta.get("analysis_confidence")
    result["anl_low_confidence_fields"] = join_list(meta.get("low_confidence_fields"))
    result["anl_notes"] = meta.get("analysis_notes")

    return result


# Column definitions for schema documentation
ANALYSIS_COLUMNS = {
    # Data Maturity
    "anl_data_maturity_score": "integer (1-5)",
    "anl_data_maturity_level": "string (ad_hoc|developing|defined|managed|optimizing)",
    "anl_data_maturity_evidence": "string",
    "anl_data_maturity_confidence": "float (0-1)",

    # Red Flags - Individual
    "anl_red_flag_scope_creep": "boolean",
    "anl_red_flag_scope_creep_score": "float (0-1)",
    "anl_red_flag_scope_creep_signals": "string (semicolon-separated)",
    "anl_red_flag_scope_creep_evidence": "string",

    "anl_red_flag_unrealistic": "boolean",
    "anl_red_flag_unrealistic_score": "float (0-1)",
    "anl_red_flag_unrealistic_signals": "string (semicolon-separated)",
    "anl_red_flag_unrealistic_evidence": "string",

    "anl_red_flag_workload": "boolean",
    "anl_red_flag_workload_score": "float (0-1)",
    "anl_red_flag_workload_signals": "string (semicolon-separated)",
    "anl_red_flag_workload_evidence": "string",

    "anl_red_flag_vague": "boolean",
    "anl_red_flag_vague_score": "float (0-1)",
    "anl_red_flag_vague_signals": "string (semicolon-separated)",
    "anl_red_flag_vague_evidence": "string",

    # Red Flags - Aggregate
    "anl_red_flag_overall_risk": "float (0-1)",
    "anl_red_flag_recommendation": "string (proceed|proceed_with_caution|investigate_further|avoid)",

    # Culture Signals
    "anl_culture_wlb_score": "integer (1-5)",
    "anl_culture_wlb_positive": "string (semicolon-separated)",
    "anl_culture_wlb_negative": "string (semicolon-separated)",
    "anl_culture_wlb_evidence": "string",

    "anl_culture_growth_score": "integer (1-5)",
    "anl_culture_growth_signals": "string (semicolon-separated)",
    "anl_culture_growth_evidence": "string",

    "anl_culture_team_score": "integer (1-5)",
    "anl_culture_team_signals": "string (semicolon-separated)",
    "anl_culture_team_evidence": "string",

    "anl_culture_comp_score": "integer (1-5)",
    "anl_culture_comp_signals": "string (semicolon-separated)",
    "anl_culture_comp_evidence": "string",

    "anl_culture_overall_score": "integer (1-5)",
    "anl_culture_confidence": "float (0-1)",

    # Role Assessment
    "anl_role_technical_depth": "string (shallow|moderate|deep)",
    "anl_role_leadership": "boolean",
    "anl_role_cross_functional": "boolean",
    "anl_role_innovation_focus": "boolean",
    "anl_role_maintenance_focus": "boolean",
    "anl_role_evidence": "string",

    # Summary
    "anl_summary_strengths": "string (semicolon-separated)",
    "anl_summary_concerns": "string (semicolon-separated)",
    "anl_summary_fit_for": "string (semicolon-separated)",
    "anl_summary_not_fit_for": "string (semicolon-separated)",
    "anl_summary_questions": "string (semicolon-separated)",
    "anl_summary_one_liner": "string",

    # Metadata
    "anl_confidence": "float (0-1)",
    "anl_low_confidence_fields": "string (semicolon-separated)",
    "anl_notes": "string",
}
```

---

### 4.4 Update Handler with Complete 3-Pass Chain

**File:** `src/lambdas/ai_enrichment/enrich_partition/handler.py` (update)

```python
"""
EnrichPartition Lambda Handler - Complete 3-Pass Implementation
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .bedrock_client import BedrockClient
from .prompts.pass1_extraction import build_pass1_prompt
from .prompts.pass2_inference import build_pass2_prompt
from .prompts.pass3_analysis import build_pass3_prompt
from .parsers.json_parser import parse_llm_json
from .parsers.validators import (
    validate_extraction_response,
    validate_inference_response,
    validate_analysis_response
)
from .flatteners.extraction import flatten_extraction
from .flatteners.inference import flatten_inference
from .flatteners.analysis import flatten_analysis

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Enrichment version - increment on schema changes
ENRICHMENT_VERSION = "1.0"


class EnrichmentResult:
    """Container for enrichment results and metadata."""

    def __init__(self):
        self.pass1_result: Optional[dict] = None
        self.pass2_result: Optional[dict] = None
        self.pass3_result: Optional[dict] = None

        self.pass1_success: bool = False
        self.pass2_success: bool = False
        self.pass3_success: bool = False

        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cost_usd: float = 0.0

        self.pass1_model: Optional[str] = None
        self.pass2_model: Optional[str] = None
        self.pass3_model: Optional[str] = None

        self.errors: list[str] = []

    def add_pass_result(
        self,
        pass_num: int,
        result: Optional[dict],
        success: bool,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        model_id: str,
        error: Optional[str] = None
    ):
        """Record result for a pass."""
        if pass_num == 1:
            self.pass1_result = result
            self.pass1_success = success
            self.pass1_model = model_id
        elif pass_num == 2:
            self.pass2_result = result
            self.pass2_success = success
            self.pass2_model = model_id
        elif pass_num == 3:
            self.pass3_result = result
            self.pass3_success = success
            self.pass3_model = model_id

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost

        if error:
            self.errors.append(f"Pass {pass_num}: {error}")

    def get_avg_confidence_pass2(self) -> Optional[float]:
        """Calculate average confidence from Pass 2 results."""
        if not self.pass2_result:
            return None

        confidences = []
        for field in ["seniority", "cloud_provider", "geo_restriction", "contract_type",
                      "team_size_category", "data_scale"]:
            conf = self.pass2_result.get(field, {}).get("confidence")
            if conf is not None:
                confidences.append(conf)

        return sum(confidences) / len(confidences) if confidences else None

    def get_avg_confidence_pass3(self) -> Optional[float]:
        """Calculate average confidence from Pass 3 results."""
        if not self.pass3_result:
            return None

        confidences = []

        # Data maturity confidence
        dm_conf = self.pass3_result.get("data_maturity", {}).get("confidence")
        if dm_conf is not None:
            confidences.append(dm_conf)

        # Culture confidence
        culture_conf = self.pass3_result.get("culture_signals", {}).get("confidence")
        if culture_conf is not None:
            confidences.append(culture_conf)

        # Analysis confidence
        analysis_conf = self.pass3_result.get("metadata", {}).get("analysis_confidence")
        if analysis_conf is not None:
            confidences.append(analysis_conf)

        return sum(confidences) / len(confidences) if confidences else None

    def get_low_confidence_fields(self) -> list[str]:
        """Get list of low confidence fields from Pass 3."""
        if not self.pass3_result:
            return []
        return self.pass3_result.get("metadata", {}).get("low_confidence_fields", [])


def enrich_job(
    job: dict,
    bedrock_client: BedrockClient
) -> tuple[dict, EnrichmentResult]:
    """
    Run full 3-pass enrichment on a single job.

    Args:
        job: Job record dict with title, company, location, description
        bedrock_client: Configured Bedrock client

    Returns:
        Tuple of (flat enrichment dict, EnrichmentResult metadata)
    """
    result = EnrichmentResult()

    title = job.get("title", "")
    company = job.get("company_name", "")
    location = job.get("location", "")
    description = job.get("description", "")

    # ============= PASS 1: EXTRACTION =============
    logger.info(f"Starting Pass 1 for job: {job.get('job_posting_id', 'unknown')}")

    try:
        system_prompt, user_prompt = build_pass1_prompt(title, company, location, description)
        response, input_tokens, output_tokens, cost = bedrock_client.invoke(
            prompt=user_prompt,
            system=system_prompt,
            pass_name="pass1"
        )

        pass1_data, parse_error = parse_llm_json(response)
        if parse_error:
            raise ValueError(f"JSON parse error: {parse_error}")

        is_valid, errors = validate_extraction_response(pass1_data)
        if not is_valid:
            raise ValueError(f"Validation errors: {errors}")

        result.add_pass_result(1, pass1_data, True, input_tokens, output_tokens, cost,
                               bedrock_client.get_model_id("pass1"))

    except Exception as e:
        logger.error(f"Pass 1 failed: {e}")
        result.add_pass_result(1, None, False, 0, 0, 0,
                               bedrock_client.get_model_id("pass1"), str(e))

    # ============= PASS 2: INFERENCE =============
    if result.pass1_success:
        logger.info(f"Starting Pass 2 for job: {job.get('job_posting_id', 'unknown')}")

        try:
            system_prompt, user_prompt = build_pass2_prompt(
                title, company, location, description, result.pass1_result
            )
            response, input_tokens, output_tokens, cost = bedrock_client.invoke(
                prompt=user_prompt,
                system=system_prompt,
                pass_name="pass2"
            )

            pass2_data, parse_error = parse_llm_json(response)
            if parse_error:
                raise ValueError(f"JSON parse error: {parse_error}")

            is_valid, errors = validate_inference_response(pass2_data)
            if not is_valid:
                raise ValueError(f"Validation errors: {errors}")

            result.add_pass_result(2, pass2_data, True, input_tokens, output_tokens, cost,
                                   bedrock_client.get_model_id("pass2"))

        except Exception as e:
            logger.error(f"Pass 2 failed: {e}")
            result.add_pass_result(2, None, False, 0, 0, 0,
                                   bedrock_client.get_model_id("pass2"), str(e))

    # ============= PASS 3: ANALYSIS =============
    if result.pass1_success and result.pass2_success:
        logger.info(f"Starting Pass 3 for job: {job.get('job_posting_id', 'unknown')}")

        try:
            system_prompt, user_prompt = build_pass3_prompt(
                title, company, location, description,
                result.pass1_result, result.pass2_result
            )
            response, input_tokens, output_tokens, cost = bedrock_client.invoke(
                prompt=user_prompt,
                system=system_prompt,
                pass_name="pass3"
            )

            pass3_data, parse_error = parse_llm_json(response)
            if parse_error:
                raise ValueError(f"JSON parse error: {parse_error}")

            is_valid, errors = validate_analysis_response(pass3_data)
            if not is_valid:
                raise ValueError(f"Validation errors: {errors}")

            result.add_pass_result(3, pass3_data, True, input_tokens, output_tokens, cost,
                                   bedrock_client.get_model_id("pass3"))

        except Exception as e:
            logger.error(f"Pass 3 failed: {e}")
            result.add_pass_result(3, None, False, 0, 0, 0,
                                   bedrock_client.get_model_id("pass3"), str(e))

    # ============= FLATTEN RESULTS =============
    flat = {}

    # Flatten each pass result
    if result.pass1_result:
        flat.update(flatten_extraction(result.pass1_result))

    if result.pass2_result:
        flat.update(flatten_inference(result.pass2_result))

    if result.pass3_result:
        flat.update(flatten_analysis(result.pass3_result))

    # Add metadata columns
    flat["enriched_at"] = datetime.now(timezone.utc).isoformat()
    flat["enrichment_version"] = ENRICHMENT_VERSION
    flat["enrichment_model_pass1"] = result.pass1_model
    flat["enrichment_model_pass2"] = result.pass2_model
    flat["enrichment_model_pass3"] = result.pass3_model
    flat["total_tokens_used"] = result.total_input_tokens + result.total_output_tokens
    flat["enrichment_cost_usd"] = round(result.total_cost_usd, 6)
    flat["pass1_success"] = result.pass1_success
    flat["pass2_success"] = result.pass2_success
    flat["pass3_success"] = result.pass3_success
    flat["avg_confidence_pass2"] = result.get_avg_confidence_pass2()
    flat["avg_confidence_pass3"] = result.get_avg_confidence_pass3()
    flat["low_confidence_fields"] = "; ".join(result.get_low_confidence_fields()) or None
    flat["enrichment_errors"] = "; ".join(result.errors) or None

    return flat, result


def handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for partition enrichment.

    Event structure:
    {
        "partition": {
            "year": "2024",
            "month": "01",
            "day": "15",
            "hour": "12"
        }
    }
    """
    logger.info(f"Received event: {json.dumps(event)}")

    # This will be implemented in Sprint 5 with S3 I/O
    # For now, return placeholder
    return {
        "statusCode": 200,
        "body": "Handler skeleton - implement S3 I/O in Sprint 5"
    }
```

---

### 4.5 Update Local Test Script

**File:** `scripts/test_enrichment_local.py` (append)

```python
# Add to existing test script

def test_full_pipeline(sample_jobs: list[dict], bedrock_client: BedrockClient):
    """
    Test complete 3-pass enrichment pipeline.

    Args:
        sample_jobs: List of job dicts from Silver layer
        bedrock_client: Configured Bedrock client
    """
    from src.lambdas.ai_enrichment.enrich_partition.handler import enrich_job

    print("\n" + "=" * 60)
    print("FULL PIPELINE TEST (Pass 1 → Pass 2 → Pass 3)")
    print("=" * 60)

    results = []

    for i, job in enumerate(sample_jobs):
        print(f"\n--- Job {i+1}/{len(sample_jobs)}: {job.get('title', 'Unknown')} ---")

        flat_result, enrichment_result = enrich_job(job, bedrock_client)
        results.append((flat_result, enrichment_result))

        # Print summary
        print(f"\nPass Results:")
        print(f"  Pass 1: {'✓' if enrichment_result.pass1_success else '✗'}")
        print(f"  Pass 2: {'✓' if enrichment_result.pass2_success else '✗'}")
        print(f"  Pass 3: {'✓' if enrichment_result.pass3_success else '✗'}")

        print(f"\nToken Usage:")
        print(f"  Total: {enrichment_result.total_input_tokens + enrichment_result.total_output_tokens}")
        print(f"  Cost: ${enrichment_result.total_cost_usd:.6f}")

        print(f"\nConfidence Scores:")
        print(f"  Pass 2 avg: {enrichment_result.get_avg_confidence_pass2()}")
        print(f"  Pass 3 avg: {enrichment_result.get_avg_confidence_pass3()}")

        if enrichment_result.pass3_result:
            summary = enrichment_result.pass3_result.get("summary", {})
            print(f"\nSummary:")
            print(f"  One-liner: {summary.get('one_liner', 'N/A')}")
            print(f"  Strengths: {len(summary.get('strengths', []))} items")
            print(f"  Concerns: {len(summary.get('concerns', []))} items")

            red_flags = enrichment_result.pass3_result.get("red_flags", {})
            print(f"\nRed Flags:")
            print(f"  Overall risk: {red_flags.get('overall_risk_score', 'N/A')}")
            print(f"  Recommendation: {red_flags.get('recommendation', 'N/A')}")

        if enrichment_result.errors:
            print(f"\nErrors: {enrichment_result.errors}")

    # Aggregate stats
    print("\n" + "=" * 60)
    print("AGGREGATE STATISTICS")
    print("=" * 60)

    total_jobs = len(results)
    pass1_success = sum(1 for _, r in results if r.pass1_success)
    pass2_success = sum(1 for _, r in results if r.pass2_success)
    pass3_success = sum(1 for _, r in results if r.pass3_success)
    full_success = sum(1 for _, r in results if r.pass1_success and r.pass2_success and r.pass3_success)

    total_cost = sum(r.total_cost_usd for _, r in results)
    total_tokens = sum(r.total_input_tokens + r.total_output_tokens for _, r in results)

    print(f"\nSuccess Rates:")
    print(f"  Pass 1: {pass1_success}/{total_jobs} ({100*pass1_success/total_jobs:.1f}%)")
    print(f"  Pass 2: {pass2_success}/{total_jobs} ({100*pass2_success/total_jobs:.1f}%)")
    print(f"  Pass 3: {pass3_success}/{total_jobs} ({100*pass3_success/total_jobs:.1f}%)")
    print(f"  Full pipeline: {full_success}/{total_jobs} ({100*full_success/total_jobs:.1f}%)")

    print(f"\nCost Summary:")
    print(f"  Total cost: ${total_cost:.4f}")
    print(f"  Avg cost per job: ${total_cost/total_jobs:.6f}")
    print(f"  Total tokens: {total_tokens}")
    print(f"  Avg tokens per job: {total_tokens/total_jobs:.0f}")

    # Calculate average confidences
    pass2_confs = [r.get_avg_confidence_pass2() for _, r in results if r.get_avg_confidence_pass2()]
    pass3_confs = [r.get_avg_confidence_pass3() for _, r in results if r.get_avg_confidence_pass3()]

    if pass2_confs:
        print(f"\nConfidence Averages:")
        print(f"  Pass 2: {sum(pass2_confs)/len(pass2_confs):.3f}")
    if pass3_confs:
        print(f"  Pass 3: {sum(pass3_confs)/len(pass3_confs):.3f}")

    return results


if __name__ == "__main__":
    import sys

    # Load sample jobs
    sample_jobs = load_sample_jobs()

    # Initialize client
    client = BedrockClient()

    # Check command line args for test type
    test_type = sys.argv[1] if len(sys.argv) > 1 else "full"

    if test_type == "pass1":
        test_pass1_extraction(sample_jobs, client)
    elif test_type == "pass2":
        test_pass2_inference(sample_jobs, client)
    elif test_type == "full":
        test_full_pipeline(sample_jobs, client)
    else:
        print(f"Unknown test type: {test_type}")
        print("Usage: python test_enrichment_local.py [pass1|pass2|full]")
```

---

## Validation Checklist

### Pass 3 Implementation

- [ ] Pass 3 prompt includes both Pass 1 and Pass 2 in context
- [ ] System prompt has anti-hallucination rules
- [ ] User prompt clearly defines JSON structure
- [ ] All red flag types covered (scope_creep, unrealistic, workload, vague)
- [ ] Culture signals include all dimensions
- [ ] Summary has actionable strengths/concerns/fit_for

### Validator

- [ ] All score ranges validated (0-1 for risk, 1-5 for culture)
- [ ] Boolean fields validated
- [ ] Required fields checked
- [ ] Enum values validated (recommendation, data_maturity_level)

### Flattener

- [ ] All Pass 3 fields mapped to `anl_*` columns
- [ ] Array fields joined with semicolons
- [ ] Null handling consistent
- [ ] Column names documented

### Handler

- [ ] 3-pass chain executes sequentially
- [ ] Pass 2 requires Pass 1 success
- [ ] Pass 3 requires Pass 1 + Pass 2 success
- [ ] Metadata columns calculated correctly
- [ ] Average confidence calculations work
- [ ] Low confidence fields extracted

### Local Test

- [ ] Full pipeline test available
- [ ] Aggregate statistics calculated
- [ ] Cost tracking accurate
- [ ] Command-line test selection works

---

## Manual QA Checklist

After running `python scripts/test_enrichment_local.py full`:

### Data Maturity Assessment
- [ ] Score (1-5) aligns with tech stack sophistication
- [ ] Level matches score (1=ad_hoc, 5=optimizing)
- [ ] Evidence references specific tools/practices mentioned

### Red Flag Detection
- [ ] Scope creep detected for "wear many hats" type descriptions
- [ ] Unrealistic expectations flagged for excessive skill requirements
- [ ] Workload concerns identified for on-call/24-7 mentions
- [ ] Vague descriptions caught for generic postings
- [ ] Overall risk score is weighted average of individual flags
- [ ] Recommendation aligns with risk level

### Culture Signals
- [ ] Work-life balance scores reflect remote/flexible mentions
- [ ] Growth opportunities reflect training/conference budgets
- [ ] Team environment reflects collaboration mentions
- [ ] Compensation transparency reflects salary disclosure

### Summary Quality
- [ ] Strengths are specific and actionable (not generic)
- [ ] Concerns are specific and actionable
- [ ] Fit_for describes actual candidate profiles
- [ ] Not_fit_for is useful for self-selection
- [ ] Key_questions_to_ask are relevant to role
- [ ] One_liner captures essence of opportunity

### Metadata
- [ ] Analysis confidence reflects overall evidence quality
- [ ] Low confidence fields list is accurate
- [ ] Analysis notes capture any caveats

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/lambdas/ai_enrichment/enrich_partition/prompts/pass3_analysis.py` | CREATE | Pass 3 prompt template |
| `src/lambdas/ai_enrichment/enrich_partition/parsers/validators.py` | MODIFY | Add `validate_analysis_response()` |
| `src/lambdas/ai_enrichment/enrich_partition/flatteners/analysis.py` | CREATE | Analysis flattener |
| `src/lambdas/ai_enrichment/enrich_partition/handler.py` | MODIFY | Complete 3-pass chain |
| `scripts/test_enrichment_local.py` | MODIFY | Add full pipeline test |

---

## Expected Output Schema (Pass 3 Columns)

| Column | Type | Description |
|--------|------|-------------|
| `anl_data_maturity_score` | int | 1-5 maturity score |
| `anl_data_maturity_level` | string | Maturity level name |
| `anl_data_maturity_evidence` | string | Supporting evidence |
| `anl_data_maturity_confidence` | float | 0-1 confidence |
| `anl_red_flag_scope_creep` | bool | Scope creep detected |
| `anl_red_flag_scope_creep_score` | float | 0-1 risk score |
| `anl_red_flag_unrealistic` | bool | Unrealistic expectations |
| `anl_red_flag_workload` | bool | Workload concerns |
| `anl_red_flag_vague` | bool | Vague description |
| `anl_red_flag_overall_risk` | float | 0-1 aggregate risk |
| `anl_red_flag_recommendation` | string | proceed/caution/investigate/avoid |
| `anl_culture_wlb_score` | int | Work-life balance 1-5 |
| `anl_culture_growth_score` | int | Growth opportunities 1-5 |
| `anl_culture_team_score` | int | Team environment 1-5 |
| `anl_culture_overall_score` | int | Overall culture 1-5 |
| `anl_role_technical_depth` | string | shallow/moderate/deep |
| `anl_role_leadership` | bool | Leadership component |
| `anl_summary_strengths` | string | Semicolon-separated |
| `anl_summary_concerns` | string | Semicolon-separated |
| `anl_summary_fit_for` | string | Candidate profiles |
| `anl_summary_one_liner` | string | Single sentence summary |
| `anl_confidence` | float | Overall analysis confidence |

---

## Next Sprint

**Sprint 5: Orchestration & Integration** - Complete Step Functions, EventBridge, S3 I/O, and deploy.
