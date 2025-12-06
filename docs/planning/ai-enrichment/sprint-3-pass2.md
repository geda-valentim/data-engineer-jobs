# Sprint 3: Pass 2 - Structured Inference

> **Duration:** 2-3 days
> **Goal:** Implement Pass 2 with cascading context from Pass 1
> **Depends on:** Sprint 2 (Pass 1)

---

## Objectives

1. Implement Pass 2 inference prompt with Pass 1 context
2. Add confidence scoring and evidence tracking
3. Create inference validator and flattener
4. Chain Pass 1 → Pass 2 in handler
5. Live test cascading context

---

## Tasks

### 3.1 Implement Pass 2 Prompt

**File:** `src/lambdas/ai_enrichment/enrich_partition/prompts/pass2_inference.py`

```python
"""
Pass 2: Structured Inference
Normalizes and infers fields with confidence scores.
Receives Pass 1 extraction as context.
"""

PASS2_SYSTEM = """You are a job market analyst. Normalize and infer structured data from job postings.
You have access to already-extracted factual data from Pass 1.

## INFERENCE RULES
1. Use Pass 1 data as PRIMARY source - it's validated
2. Use raw description to FILL GAPS and add context
3. Every inference needs: value, confidence (0-1), evidence, source
4. Reference Pass 1 fields in evidence when applicable
5. If Pass 1 has the answer explicitly, confidence should be 0.9+
6. If you cannot infer with reasonable confidence, use null

## CONFIDENCE SCALE
- 0.9-1.0: From Pass 1 or explicit in text
- 0.7-0.9: Strong inference, multiple signals
- 0.5-0.7: Moderate inference, 1-2 signals
- 0.3-0.5: Weak inference (include but flag)
- <0.3: Do NOT include, use null instead

## SOURCE TYPES
- "pass1_derived": Directly from Pass 1 extraction
- "inferred": Deduced from text patterns
- "combined": Mix of Pass 1 + text inference"""


PASS2_TEMPLATE = '''## ALREADY EXTRACTED (Pass 1)
<pass1_extraction>
{pass1_extraction_json}
</pass1_extraction>

## RAW JOB POSTING
<job_posting>
Title: {job_title}
Company: {company_name}
Location: {job_location}

Description:
{job_description_text}
</job_posting>

## OUTPUT FORMAT
Return ONLY valid JSON:

```json
{{
  "inference": {{
    "seniority_and_role": {{
      "seniority_level": {{
        "value": "intern" | "junior" | "mid" | "senior" | "staff" | "principal" | "lead" | null,
        "confidence": 0.0-1.0,
        "evidence": "string explaining why",
        "source": "pass1_derived" | "inferred" | "combined"
      }},
      "years_experience": {{
        "value": {{ "min": number, "max": number }} or null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "job_family": {{
        "value": "data_engineer" | "analytics_engineer" | "ml_engineer" | "platform" | null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "sub_specialty": {{
        "value": "streaming" | "batch" | "governance" | "platform" | "modeling" | "general" | null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }}
    }},
    "stack_and_cloud": {{
      "primary_cloud": {{
        "value": "aws" | "azure" | "gcp" | "multi" | "on_prem" | null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "secondary_clouds": {{
        "value": ["array"] or null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "processing_paradigm": {{
        "value": "batch" | "streaming" | "hybrid" | null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "storage_layer": {{
        "value": "warehouse" | "lake" | "lakehouse" | "mixed" | null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "orchestration_type": {{
        "value": "airflow" | "dagster" | "prefect" | "dbt_cloud" | "cloud_native" | null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "tooling_modernity": {{
        "value": "modern_data_stack" | "traditional" | "mixed" | null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }}
    }},
    "geo_and_work_model": {{
      "geo_restriction": {{
        "value": "us_only" | "eu_only" | "latam_ok" | "global" | null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "remote_level": {{
        "value": "fully_remote" | "hybrid" | "onsite" | "remote_restricted" | null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "timezone_requirement": {{
        "value": "americas" | "europe" | "apac" | "flexible" | null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "allowed_countries": {{
        "value": ["array"] or null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "us_states_allowed": {{
        "value": ["array"] or null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }}
    }},
    "visa_and_authorization": {{
      "visa_sponsorship": {{
        "value": "sponsors" | "no_sponsorship" | null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "accepted_work_auth": {{
        "value": ["citizen", "gc", "h1b", "opt", "cpt", "ead", "tn", "l1", "o1"] or null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "h1b_friendly": {{
        "value": boolean or null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "opt_cpt_friendly": {{
        "value": boolean or null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }}
    }},
    "contract_and_compensation": {{
      "employment_type": {{
        "value": "full_time" | "contract" | "c2h" | "part_time" | "internship" | null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "contract_structure": {{
        "value": "w2" | "c2c" | "1099" | "any" | null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "pay_structure": {{
        "value": "salary" | "hourly" | "daily" | "project" | null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "contract_duration_months": {{
        "value": number or null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }}
    }},
    "requirements_classification": {{
      "must_have_skills": {{
        "value": ["array"] or null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "nice_to_have_skills": {{
        "value": ["array"] or null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }},
      "must_have_soft_skills": {{
        "value": ["array"] or null,
        "confidence": 0.0-1.0,
        "evidence": "string",
        "source": "string"
      }}
    }}
  }},
  "metadata": {{
    "fields_from_pass1": number,
    "fields_inferred": number,
    "avg_confidence": number
  }}
}}
```

Infer now:'''


def build_pass2_prompt(
    job_title: str,
    company_name: str,
    job_location: str,
    job_description_text: str,
    pass1_extraction: dict
) -> str:
    """Build Pass 2 inference prompt with Pass 1 context."""
    import json

    return PASS2_TEMPLATE.format(
        job_title=job_title or "Not specified",
        company_name=company_name or "Not specified",
        job_location=job_location or "Not specified",
        job_description_text=job_description_text or "No description available",
        pass1_extraction_json=json.dumps(pass1_extraction, indent=2)
    )


def get_pass2_system() -> str:
    """Get Pass 2 system prompt."""
    return PASS2_SYSTEM
```

---

### 3.2 Create Inference Flattener

**File:** `src/lambdas/ai_enrichment/enrich_partition/flatteners/inference.py`

```python
"""
Flatten Pass 2 inference results to inf_* columns.
Includes _confidence and _evidence columns.
"""

from typing import Dict, Any, Optional


def get_value(obj: Dict, key: str) -> Any:
    """Extract value from inference object."""
    field = obj.get(key, {})
    return field.get("value") if isinstance(field, dict) else None


def get_confidence(obj: Dict, key: str) -> Optional[float]:
    """Extract confidence from inference object."""
    field = obj.get(key, {})
    conf = field.get("confidence") if isinstance(field, dict) else None
    # Clamp to 0-1 range
    if conf is not None:
        return max(0.0, min(1.0, float(conf)))
    return None


def get_evidence(obj: Dict, key: str) -> Optional[str]:
    """Extract evidence from inference object."""
    field = obj.get(key, {})
    return field.get("evidence") if isinstance(field, dict) else None


def flatten_inference(enriched: Dict[str, Any], inference: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten Pass 2 inference into prefixed columns.

    Args:
        enriched: Existing enriched record dict
        inference: Pass 2 inference result

    Returns:
        Updated enriched dict with inf_* columns
    """
    # Seniority and Role
    sr = inference.get("seniority_and_role", {})
    enriched["inf_seniority_level"] = get_value(sr, "seniority_level")
    enriched["inf_seniority_confidence"] = get_confidence(sr, "seniority_level")
    enriched["inf_seniority_evidence"] = get_evidence(sr, "seniority_level")

    yrs = sr.get("years_experience", {}).get("value") or {}
    enriched["inf_years_experience_min"] = yrs.get("min") if isinstance(yrs, dict) else None
    enriched["inf_years_experience_max"] = yrs.get("max") if isinstance(yrs, dict) else None

    enriched["inf_job_family"] = get_value(sr, "job_family")
    enriched["inf_job_family_confidence"] = get_confidence(sr, "job_family")
    enriched["inf_sub_specialty"] = get_value(sr, "sub_specialty")

    # Stack and Cloud
    sc = inference.get("stack_and_cloud", {})
    enriched["inf_primary_cloud"] = get_value(sc, "primary_cloud")
    enriched["inf_primary_cloud_confidence"] = get_confidence(sc, "primary_cloud")
    enriched["inf_secondary_clouds"] = get_value(sc, "secondary_clouds")
    enriched["inf_processing_paradigm"] = get_value(sc, "processing_paradigm")
    enriched["inf_storage_layer"] = get_value(sc, "storage_layer")
    enriched["inf_orchestration_type"] = get_value(sc, "orchestration_type")
    enriched["inf_tooling_modernity"] = get_value(sc, "tooling_modernity")

    # Geo and Work Model
    gw = inference.get("geo_and_work_model", {})
    enriched["inf_geo_restriction"] = get_value(gw, "geo_restriction")
    enriched["inf_geo_restriction_confidence"] = get_confidence(gw, "geo_restriction")
    enriched["inf_remote_level"] = get_value(gw, "remote_level")
    enriched["inf_timezone_requirement"] = get_value(gw, "timezone_requirement")
    enriched["inf_allowed_countries"] = get_value(gw, "allowed_countries")
    enriched["inf_us_states_allowed"] = get_value(gw, "us_states_allowed")

    # Visa and Authorization
    va = inference.get("visa_and_authorization", {})
    enriched["inf_visa_sponsorship"] = get_value(va, "visa_sponsorship")
    enriched["inf_visa_sponsorship_confidence"] = get_confidence(va, "visa_sponsorship")
    enriched["inf_accepted_work_auth"] = get_value(va, "accepted_work_auth")
    enriched["inf_h1b_friendly"] = get_value(va, "h1b_friendly")
    enriched["inf_opt_cpt_friendly"] = get_value(va, "opt_cpt_friendly")

    # Contract and Compensation
    cc = inference.get("contract_and_compensation", {})
    enriched["inf_employment_type"] = get_value(cc, "employment_type")
    enriched["inf_contract_structure"] = get_value(cc, "contract_structure")
    enriched["inf_pay_structure"] = get_value(cc, "pay_structure")
    enriched["inf_contract_duration_months"] = get_value(cc, "contract_duration_months")

    # Requirements Classification
    rc = inference.get("requirements_classification", {})
    enriched["inf_must_have_skills"] = get_value(rc, "must_have_skills")
    enriched["inf_nice_to_have_skills"] = get_value(rc, "nice_to_have_skills")
    enriched["inf_must_have_soft_skills"] = get_value(rc, "must_have_soft_skills")

    return enriched


def calculate_avg_confidence(inference: Dict[str, Any]) -> float:
    """Calculate average confidence across all inference fields."""
    confidences = []

    def extract_confidences(obj: Dict):
        for key, value in obj.items():
            if isinstance(value, dict):
                if "confidence" in value:
                    conf = value.get("confidence")
                    if conf is not None and isinstance(conf, (int, float)) and conf > 0:
                        confidences.append(float(conf))
                else:
                    extract_confidences(value)

    for section in inference.values():
        if isinstance(section, dict):
            extract_confidences(section)

    return round(sum(confidences) / len(confidences), 3) if confidences else 0.0
```

---

### 3.3 Update Handler for Pass 1 → Pass 2 Chain

**Update:** `src/lambdas/ai_enrichment/enrich_partition/handler.py`

Add the following function after imports:

```python
def enrich_single_job_pass1_pass2(
    job: Dict[str, Any],
    bedrock_pass1: BedrockClient,
    bedrock_pass2: BedrockClient
) -> Tuple[Dict[str, Any], int, float]:
    """
    Enrich a single job with Pass 1 + Pass 2.

    Returns:
        Tuple of (enriched_dict, total_tokens, total_cost)
    """
    from prompts.pass1_extraction import build_pass1_prompt, get_pass1_system
    from prompts.pass2_inference import build_pass2_prompt, get_pass2_system
    from parsers.json_parser import parse_llm_response
    from parsers.validators import validate_extraction, validate_inference
    from flatteners.extraction import flatten_extraction
    from flatteners.inference import flatten_inference, calculate_avg_confidence

    job_id = job.get("job_posting_id", "unknown")
    description = job.get("job_description_text", "")
    title = job.get("job_title", "")
    company = job.get("company_name", "")
    location = job.get("job_location", "")

    total_tokens = 0
    total_cost = 0.0
    enriched = job.copy()

    # ═══════════════════════════════════════════════════════════════
    # PASS 1: Extraction
    # ═══════════════════════════════════════════════════════════════
    try:
        pass1_prompt = build_pass1_prompt(
            title=title,
            company=company,
            location=location,
            description=description
        )

        pass1_response, in_tokens, out_tokens, cost = bedrock_pass1.invoke(
            prompt=pass1_prompt,
            system=get_pass1_system()
        )
        total_tokens += in_tokens + out_tokens
        total_cost += cost

        pass1_result = parse_llm_response(pass1_response)
        extraction = pass1_result.get("extraction", {})

        if validate_extraction(extraction):
            enriched = flatten_extraction(enriched, extraction)
            enriched["pass1_success"] = True
        else:
            logger.warning(f"Pass 1 validation failed for {job_id}")
            enriched["pass1_success"] = False
            extraction = {}

    except Exception as e:
        logger.error(f"Pass 1 failed for {job_id}: {e}")
        enriched["pass1_success"] = False
        extraction = {}

    # ═══════════════════════════════════════════════════════════════
    # PASS 2: Inference (receives Pass 1 context)
    # ═══════════════════════════════════════════════════════════════
    try:
        pass2_prompt = build_pass2_prompt(
            title=title,
            company=company,
            location=location,
            description=description,
            pass1_extraction=extraction  # ← CASCADING CONTEXT
        )

        pass2_response, in_tokens, out_tokens, cost = bedrock_pass2.invoke(
            prompt=pass2_prompt,
            system=get_pass2_system()
        )
        total_tokens += in_tokens + out_tokens
        total_cost += cost

        pass2_result = parse_llm_response(pass2_response)
        inference = pass2_result.get("inference", {})

        if validate_inference(inference):
            enriched = flatten_inference(enriched, inference)
            enriched["pass2_success"] = True
            enriched["avg_confidence_pass2"] = calculate_avg_confidence(inference)
        else:
            logger.warning(f"Pass 2 validation failed for {job_id}")
            enriched["pass2_success"] = False

    except Exception as e:
        logger.error(f"Pass 2 failed for {job_id}: {e}")
        enriched["pass2_success"] = False

    enriched["total_tokens_used"] = total_tokens
    enriched["enrichment_cost_usd"] = round(total_cost, 6)

    return enriched, total_tokens, total_cost
```

---

### 3.4 Update Local Test Script

**Add to:** `scripts/test_enrichment_local.py`

```python
def test_pass1_pass2_chain():
    """Test Pass 1 → Pass 2 cascading context."""
    print("\n" + "=" * 60)
    print("Testing Pass 1 + Pass 2 Chain...")
    print("=" * 60)

    import json
    from pathlib import Path

    # Load sample jobs
    fixtures_path = Path(__file__).parent.parent / "tests" / "ai_enrichment" / "fixtures" / "sample_jobs.json"

    with open(fixtures_path) as f:
        sample_jobs = json.load(f)

    # Import modules
    from enrich_partition.bedrock_client import BedrockClient
    from enrich_partition.prompts.pass1_extraction import build_pass1_prompt, get_pass1_system
    from enrich_partition.prompts.pass2_inference import build_pass2_prompt, get_pass2_system
    from enrich_partition.parsers.json_parser import parse_llm_response
    from enrich_partition.parsers.validators import validate_extraction, validate_inference
    from enrich_partition.flatteners.extraction import flatten_extraction
    from enrich_partition.flatteners.inference import flatten_inference, calculate_avg_confidence

    model_pass1 = os.getenv("BEDROCK_MODEL_PASS1", "openai.gpt-oss-120b-1:0")
    model_pass2 = os.getenv("BEDROCK_MODEL_PASS2", "openai.gpt-oss-120b-1:0")
    region = os.getenv("AWS_REGION", "us-east-1")

    client_pass1 = BedrockClient(model_id=model_pass1, region=region)
    client_pass2 = BedrockClient(model_id=model_pass2, region=region)

    total_cost = 0.0
    all_passed = True

    # Test with first job
    job = sample_jobs[0]
    print(f"\n--- Job: {job['job_posting_id']} ---")
    print(f"Title: {job['job_title']}")

    # Pass 1
    print("\n[Pass 1: Extraction]")
    pass1_prompt = build_pass1_prompt(
        job_title=job["job_title"],
        company_name=job["company_name"],
        job_location=job["job_location"],
        job_description_text=job["job_description_text"]
    )

    pass1_response, in1, out1, cost1 = client_pass1.invoke(
        prompt=pass1_prompt,
        system=get_pass1_system()
    )
    total_cost += cost1
    print(f"Tokens: {in1} in, {out1} out | Cost: ${cost1:.6f}")

    pass1_result = parse_llm_response(pass1_response)
    extraction = pass1_result.get("extraction", {})

    if validate_extraction(extraction):
        print("✓ Pass 1 valid")
        enriched = flatten_extraction({}, extraction)
    else:
        print("✗ Pass 1 failed")
        all_passed = False
        extraction = {}
        enriched = {}

    # Pass 2 (with Pass 1 context)
    print("\n[Pass 2: Inference with Pass 1 context]")
    pass2_prompt = build_pass2_prompt(
        job_title=job["job_title"],
        company_name=job["company_name"],
        job_location=job["job_location"],
        job_description_text=job["job_description_text"],
        pass1_extraction=extraction
    )

    pass2_response, in2, out2, cost2 = client_pass2.invoke(
        prompt=pass2_prompt,
        system=get_pass2_system()
    )
    total_cost += cost2
    print(f"Tokens: {in2} in, {out2} out | Cost: ${cost2:.6f}")

    pass2_result = parse_llm_response(pass2_response)
    inference = pass2_result.get("inference", {})

    if validate_inference(inference):
        print("✓ Pass 2 valid")
        enriched = flatten_inference(enriched, inference)
        avg_conf = calculate_avg_confidence(inference)
        print(f"  Average confidence: {avg_conf:.2f}")

        # Check cascading context
        print("\n[Cascading Context Check]")
        sr = inference.get("seniority_and_role", {})
        seniority = sr.get("seniority_level", {})
        print(f"  Seniority: {seniority.get('value')}")
        print(f"  Evidence: {seniority.get('evidence', 'N/A')[:100]}...")
        print(f"  Source: {seniority.get('source')}")

        # Check if evidence references Pass 1
        if "pass1" in str(seniority.get("evidence", "")).lower() or \
           seniority.get("source") == "pass1_derived":
            print("  ✓ Evidence references Pass 1")
        else:
            print("  ⚠ Evidence may not reference Pass 1 (check manually)")
    else:
        print("✗ Pass 2 failed")
        all_passed = False

    print(f"\n--- Summary ---")
    print(f"Total tokens: {in1 + out1 + in2 + out2}")
    print(f"Total cost: ${total_cost:.6f}")

    if all_passed:
        print("\n✓ Pass 1 + Pass 2 chain test PASSED")
    else:
        print("\n✗ Pass 1 + Pass 2 chain test FAILED")

    return all_passed
```

---

## Validation Checklist

- [ ] Pass 2 prompt includes Pass 1 output in `<pass1_extraction>` block
- [ ] Confidence scores are in 0-1 range
- [ ] Evidence strings reference Pass 1 field names (or "pass1_derived" source)
- [ ] All `inf_` columns populated (with nulls where appropriate)
- [ ] `avg_confidence_pass2` calculated correctly
- [ ] Cascading context improves inference quality vs standalone

---

## Files Created/Modified

| Action | File |
|--------|------|
| CREATE | `src/lambdas/ai_enrichment/enrich_partition/prompts/pass2_inference.py` |
| CREATE | `src/lambdas/ai_enrichment/enrich_partition/flatteners/inference.py` |
| MODIFY | `src/lambdas/ai_enrichment/enrich_partition/parsers/validators.py` |
| MODIFY | `src/lambdas/ai_enrichment/enrich_partition/handler.py` |
| MODIFY | `scripts/test_enrichment_local.py` |

---

## Next Sprint

[Sprint 4: Pass 3 - Complex Analysis](sprint-4-pass3.md)
