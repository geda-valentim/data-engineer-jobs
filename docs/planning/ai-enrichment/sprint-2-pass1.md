# Sprint 2: Pass 1 - Factual Extraction

> **Duration:** 2-3 days
> **Goal:** Implement Pass 1 prompt and extraction logic with live Bedrock testing
> **Depends on:** Sprint 1 (Foundation)

---

## Objectives

1. Create Bedrock client wrapper with retry logic
2. Implement Pass 1 extraction prompt
3. Create JSON parser for LLM responses
4. Create extraction validator and flattener
5. Live test with 1-3 real jobs

---

## Tasks

### 2.1 Create Bedrock Client Wrapper

**File:** `src/lambdas/ai_enrichment/enrich_partition/bedrock_client.py`

```python
"""
Bedrock client wrapper with retry logic, token counting, and cost calculation.
Supports Claude, Titan, and other Bedrock models.
"""

import json
import logging
import time
from typing import Tuple, Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Pricing per 1K tokens (update as needed)
MODEL_PRICING = {
    # Primary model - extremely cheap for 120B params!
    "openai.gpt-oss-120b-1:0": {"input": 0.00015, "output": 0.0003},
    # Fallback options
    "anthropic.claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
    "anthropic.claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
    "anthropic.claude-3-5-sonnet-20240620": {"input": 0.003, "output": 0.015},
    "anthropic.claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
}


class BedrockClient:
    """Wrapper for Bedrock model invocation with retry and cost tracking."""

    def __init__(
        self,
        model_id: str,
        region: str = "us-east-1",
        max_retries: int = 3,
        base_delay: float = 1.0
    ):
        self.client = boto3.client("bedrock-runtime", region_name=region)
        self.model_id = model_id
        self.max_retries = max_retries
        self.base_delay = base_delay

    def invoke(
        self,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        system: Optional[str] = None
    ) -> Tuple[str, int, int, float]:
        """
        Invoke model and return response with usage metrics.

        Args:
            prompt: User prompt
            max_tokens: Maximum response tokens
            temperature: Sampling temperature (low for structured output)
            system: Optional system prompt

        Returns:
            Tuple of (response_text, input_tokens, output_tokens, cost_usd)
        """
        body = self._build_request_body(prompt, max_tokens, temperature, system)

        for attempt in range(self.max_retries):
            try:
                response = self.client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(body),
                    contentType="application/json",
                    accept="application/json"
                )

                response_body = json.loads(response["body"].read())
                return self._parse_response(response_body)

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")

                # Retry on throttling
                if error_code in ["ThrottlingException", "ServiceUnavailable"]:
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (2 ** attempt)
                        logger.warning(
                            f"Bedrock throttled, retrying in {delay}s "
                            f"(attempt {attempt + 1}/{self.max_retries})"
                        )
                        time.sleep(delay)
                        continue

                raise

        raise Exception(f"Max retries ({self.max_retries}) exceeded")

    def _build_request_body(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        system: Optional[str]
    ) -> Dict[str, Any]:
        """Build request body based on model type."""

        # openai.gpt-oss-120b-1:0 (OpenAI-compatible format)
        if self.model_id == "openai.gpt-oss-120b-1:0":
            body = {
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            if system:
                body["messages"].insert(0, {"role": "system", "content": system})
            return body

        # Claude models
        elif self.model_id.startswith("anthropic.claude"):
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            if system:
                body["system"] = system
            return body

        # Titan models
        elif self.model_id.startswith("amazon.titan"):
            return {
                "inputText": f"{system}\n\n{prompt}" if system else prompt,
                "textGenerationConfig": {
                    "maxTokenCount": max_tokens,
                    "temperature": temperature
                }
            }

        # Default (Claude-like format)
        else:
            return {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature
            }

    def _parse_response(self, response_body: Dict[str, Any]) -> Tuple[str, int, int, float]:
        """Parse response and extract text + usage metrics."""

        # Claude format
        if "content" in response_body:
            text = response_body["content"][0]["text"]
            usage = response_body.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

        # Titan format
        elif "results" in response_body:
            text = response_body["results"][0]["outputText"]
            input_tokens = response_body.get("inputTextTokenCount", 0)
            output_tokens = response_body.get("results", [{}])[0].get("tokenCount", 0)

        # Fallback
        else:
            text = response_body.get("completion", str(response_body))
            input_tokens = 0
            output_tokens = 0

        # Calculate cost
        cost = self._calculate_cost(input_tokens, output_tokens)

        return text, input_tokens, output_tokens, cost

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD based on token usage."""
        pricing = MODEL_PRICING.get(self.model_id, {"input": 0.001, "output": 0.002})

        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]

        return round(input_cost + output_cost, 6)
```

---

### 2.2 Implement Pass 1 Prompt

**File:** `src/lambdas/ai_enrichment/enrich_partition/prompts/__init__.py`

```python
"""Prompt templates for AI enrichment passes."""
```

**File:** `src/lambdas/ai_enrichment/enrich_partition/prompts/pass1_extraction.py`

```python
"""
Pass 1: Factual Extraction
Extracts ONLY explicitly stated information from job postings.
No inference, no interpretation.
"""

PASS1_SYSTEM = """You are a precise data extractor. Extract ONLY explicitly stated information from job postings.

## CRITICAL RULES
1. Extract ONLY what is written - NO inference, NO interpretation
2. If information is not explicitly stated, use null
3. Copy exact text for text fields (like work_auth_text)
4. For boolean fields, only return true if explicitly mentioned
5. This data will be used by subsequent analysis - accuracy is critical

## ANTI-HALLUCINATION RULES
- NEVER invent information not present in the text
- "null" is ALWAYS better than a guess
- Use "not_mentioned" for visa/authorization when not explicit
- Do NOT estimate salaries if not disclosed
- If in doubt, use null"""


PASS1_TEMPLATE = '''## INPUT
<job_posting>
Title: {job_title}
Company: {company_name}
Location: {job_location}

Description:
{job_description_text}
</job_posting>

## OUTPUT FORMAT
Return ONLY valid JSON with this exact structure:

```json
{{
  "extraction": {{
    "compensation": {{
      "salary_disclosed": boolean,
      "salary_min": number or null,
      "salary_max": number or null,
      "salary_currency": string or null,
      "salary_period": "yearly" | "monthly" | "hourly" | null,
      "salary_text_raw": string or null,
      "hourly_rate_min": number or null,
      "hourly_rate_max": number or null,
      "equity_mentioned": boolean
    }},
    "work_authorization": {{
      "visa_sponsorship_stated": "yes" | "no" | "not_mentioned",
      "work_auth_text": string or null,
      "citizenship_text": string or null,
      "security_clearance_stated": "required" | "preferred" | "not_mentioned"
    }},
    "work_model": {{
      "work_model_stated": "remote" | "hybrid" | "onsite" | "not_mentioned",
      "location_restriction_text": string or null,
      "employment_type_stated": "full_time" | "contract" | "internship" | "part_time" | "not_mentioned",
      "contract_duration_stated": string or null
    }},
    "requirements": {{
      "skills_mentioned": [array of strings],
      "certifications_mentioned": [array of strings],
      "years_experience_stated": string or null,
      "education_stated": string or null
    }},
    "benefits": {{
      "benefits_mentioned": [array of strings]
    }},
    "context": {{
      "team_info_text": string or null,
      "company_description_text": string or null
    }}
  }},
  "metadata": {{
    "extraction_complete": boolean,
    "fields_found": number,
    "fields_null": number
  }}
}}
```

Extract now:'''


def build_pass1_prompt(
    job_title: str,
    company_name: str,
    job_location: str,
    job_description_text: str
) -> str:
    """Build Pass 1 extraction prompt with job data."""
    return PASS1_TEMPLATE.format(
        job_title=job_title or "Not specified",
        company_name=company_name or "Not specified",
        job_location=job_location or "Not specified",
        job_description_text=job_description_text or "No description available"
    )


def get_pass1_system() -> str:
    """Get Pass 1 system prompt."""
    return PASS1_SYSTEM
```

---

### 2.3 Create JSON Parser

**File:** `src/lambdas/ai_enrichment/enrich_partition/parsers/__init__.py`

```python
"""Parsers for LLM responses."""
```

**File:** `src/lambdas/ai_enrichment/enrich_partition/parsers/json_parser.py`

```python
"""
JSON parser for LLM responses.
Handles malformed JSON, markdown code blocks, and partial responses.
"""

import json
import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger()


def parse_llm_response(response_text: str) -> Dict[str, Any]:
    """
    Parse LLM response to extract JSON.

    Handles:
    - Clean JSON
    - Markdown code blocks (```json ... ```)
    - JSON with trailing text
    - Partial/malformed JSON (returns empty dict)

    Returns:
        Parsed dict or empty dict on failure
    """
    if not response_text:
        logger.warning("Empty response text")
        return {}

    # Try direct JSON parse first
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Extract from markdown code block
    json_text = extract_from_markdown(response_text)
    if json_text:
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            pass

    # Try to find JSON object in text
    json_text = extract_json_object(response_text)
    if json_text:
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            pass

    logger.warning(f"Could not parse JSON from response: {response_text[:200]}...")
    return {}


def extract_from_markdown(text: str) -> Optional[str]:
    """Extract JSON from markdown code blocks."""

    # Pattern: ```json ... ``` or ``` ... ```
    patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```'
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            content = match.group(1).strip()
            if content.startswith('{') or content.startswith('['):
                return content

    return None


def extract_json_object(text: str) -> Optional[str]:
    """Extract JSON object from text using brace matching."""

    # Find first { or [
    start_idx = -1
    start_char = None

    for i, char in enumerate(text):
        if char == '{':
            start_idx = i
            start_char = '{'
            break
        elif char == '[':
            start_idx = i
            start_char = '['
            break

    if start_idx == -1:
        return None

    # Find matching closing brace
    end_char = '}' if start_char == '{' else ']'
    depth = 0
    in_string = False
    escape_next = False

    for i in range(start_idx, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == '\\':
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == start_char:
            depth += 1
        elif char == end_char:
            depth -= 1
            if depth == 0:
                return text[start_idx:i + 1]

    return None


def safe_get(obj: Dict[str, Any], *keys, default=None):
    """Safely get nested dictionary value."""
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key)
        else:
            return default
        if obj is None:
            return default
    return obj
```

---

### 2.4 Create Extraction Validator

**File:** `src/lambdas/ai_enrichment/enrich_partition/parsers/validators.py`

```python
"""
Validators for LLM responses.
Validates structure and types of extracted/inferred data.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger()


def validate_extraction(extraction: Dict[str, Any]) -> bool:
    """
    Validate Pass 1 extraction structure.

    Returns True if structure is valid (may have null values).
    Returns False if structure is malformed.
    """
    if not extraction:
        logger.warning("Empty extraction")
        return False

    required_sections = [
        "compensation",
        "work_authorization",
        "work_model",
        "requirements",
        "benefits",
        "context"
    ]

    for section in required_sections:
        if section not in extraction:
            logger.warning(f"Missing section: {section}")
            return False

    # Validate compensation
    comp = extraction.get("compensation", {})
    if not isinstance(comp, dict):
        logger.warning("Invalid compensation section")
        return False

    # Validate work_authorization
    auth = extraction.get("work_authorization", {})
    if not isinstance(auth, dict):
        logger.warning("Invalid work_authorization section")
        return False

    valid_visa_values = ["yes", "no", "not_mentioned"]
    visa_stated = auth.get("visa_sponsorship_stated")
    if visa_stated is not None and visa_stated not in valid_visa_values:
        logger.warning(f"Invalid visa_sponsorship_stated: {visa_stated}")
        # Don't fail, just log

    # Validate requirements
    req = extraction.get("requirements", {})
    if not isinstance(req, dict):
        logger.warning("Invalid requirements section")
        return False

    # Check arrays are arrays
    for field in ["skills_mentioned", "certifications_mentioned"]:
        value = req.get(field)
        if value is not None and not isinstance(value, list):
            logger.warning(f"{field} should be array, got {type(value)}")
            return False

    # Validate benefits
    ben = extraction.get("benefits", {})
    benefits_list = ben.get("benefits_mentioned")
    if benefits_list is not None and not isinstance(benefits_list, list):
        logger.warning("benefits_mentioned should be array")
        return False

    return True


def validate_inference(inference: Dict[str, Any]) -> bool:
    """
    Validate Pass 2 inference structure.
    Check confidence ranges and evidence presence.
    """
    if not inference:
        logger.warning("Empty inference")
        return False

    required_sections = [
        "seniority_and_role",
        "stack_and_cloud",
        "geo_and_work_model",
        "visa_and_authorization",
        "contract_and_compensation",
        "requirements_classification"
    ]

    for section in required_sections:
        if section not in inference:
            logger.warning(f"Missing inference section: {section}")
            return False

    # Validate confidence values are 0-1
    def check_confidence(obj: Dict, path: str = ""):
        for key, value in obj.items():
            current_path = f"{path}.{key}" if path else key

            if isinstance(value, dict):
                # Check for confidence field
                conf = value.get("confidence")
                if conf is not None:
                    if not isinstance(conf, (int, float)):
                        logger.warning(f"Invalid confidence type at {current_path}")
                        return False
                    if not (0 <= conf <= 1):
                        logger.warning(f"Confidence out of range at {current_path}: {conf}")
                        # Don't fail, clamp later

                # Recurse into nested dicts
                check_confidence(value, current_path)

        return True

    for section in required_sections:
        if not check_confidence(inference[section], section):
            return False

    return True


def validate_analysis(analysis: Dict[str, Any]) -> bool:
    """
    Validate Pass 3 analysis structure.
    Check score ranges and summary presence.
    """
    if not analysis:
        logger.warning("Empty analysis")
        return False

    required_sections = [
        "company_maturity",
        "red_flags_and_role_quality",
        "stakeholders_and_leadership",
        "tech_culture",
        "ai_ml_integration",
        "competition_and_timing"
    ]

    for section in required_sections:
        if section not in analysis:
            logger.warning(f"Missing analysis section: {section}")
            return False

    # Validate score ranges (0-1)
    red_flags = analysis.get("red_flags_and_role_quality", {})

    for score_field in ["scope_creep_score", "workload_risk_score"]:
        score_obj = red_flags.get(score_field, {})
        if isinstance(score_obj, dict):
            value = score_obj.get("value")
            if value is not None:
                if not isinstance(value, (int, float)):
                    logger.warning(f"Invalid {score_field} type")
                elif not (0 <= value <= 1):
                    logger.warning(f"{score_field} out of range: {value}")

    return True
```

---

### 2.5 Create Extraction Flattener

**File:** `src/lambdas/ai_enrichment/enrich_partition/flatteners/__init__.py`

```python
"""Flatteners for converting nested LLM responses to flat columns."""
```

**File:** `src/lambdas/ai_enrichment/enrich_partition/flatteners/extraction.py`

```python
"""
Flatten Pass 1 extraction results to ext_* columns.
"""

from typing import Dict, Any


def flatten_extraction(enriched: Dict[str, Any], extraction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten Pass 1 extraction into prefixed columns.

    Args:
        enriched: Existing enriched record dict
        extraction: Pass 1 extraction result

    Returns:
        Updated enriched dict with ext_* columns
    """
    # Compensation
    comp = extraction.get("compensation", {})
    enriched["ext_salary_disclosed"] = comp.get("salary_disclosed")
    enriched["ext_salary_min"] = comp.get("salary_min")
    enriched["ext_salary_max"] = comp.get("salary_max")
    enriched["ext_salary_currency"] = comp.get("salary_currency")
    enriched["ext_salary_period"] = comp.get("salary_period")
    enriched["ext_salary_text_raw"] = comp.get("salary_text_raw")
    enriched["ext_hourly_rate_min"] = comp.get("hourly_rate_min")
    enriched["ext_hourly_rate_max"] = comp.get("hourly_rate_max")
    enriched["ext_equity_mentioned"] = comp.get("equity_mentioned")

    # Work Authorization
    auth = extraction.get("work_authorization", {})
    enriched["ext_visa_sponsorship_stated"] = auth.get("visa_sponsorship_stated")
    enriched["ext_work_auth_text"] = auth.get("work_auth_text")
    enriched["ext_citizenship_text"] = auth.get("citizenship_text")
    enriched["ext_security_clearance_stated"] = auth.get("security_clearance_stated")

    # Work Model
    wm = extraction.get("work_model", {})
    enriched["ext_work_model_stated"] = wm.get("work_model_stated")
    enriched["ext_location_restriction_text"] = wm.get("location_restriction_text")
    enriched["ext_employment_type_stated"] = wm.get("employment_type_stated")
    enriched["ext_contract_duration_stated"] = wm.get("contract_duration_stated")

    # Requirements
    req = extraction.get("requirements", {})
    enriched["ext_skills_mentioned"] = req.get("skills_mentioned")
    enriched["ext_certifications_mentioned"] = req.get("certifications_mentioned")
    enriched["ext_years_experience_stated"] = req.get("years_experience_stated")
    enriched["ext_education_stated"] = req.get("education_stated")

    # Benefits
    ben = extraction.get("benefits", {})
    enriched["ext_benefits_mentioned"] = ben.get("benefits_mentioned")

    # Context
    ctx = extraction.get("context", {})
    enriched["ext_team_info_text"] = ctx.get("team_info_text")
    enriched["ext_company_description_text"] = ctx.get("company_description_text")

    return enriched
```

---

### 2.6 Create Sample Jobs Fixture

**File:** `tests/ai_enrichment/fixtures/sample_jobs.json`

```json
[
  {
    "job_posting_id": "test-001",
    "job_title": "Senior Data Engineer",
    "company_name": "TechCorp Inc",
    "job_location": "San Francisco, CA",
    "job_description_text": "We are looking for a Senior Data Engineer to join our team. Requirements: 5+ years of experience with Python, Spark, and AWS. Experience with Airflow and dbt preferred. Salary range: $180,000 - $220,000 per year. Benefits include health insurance, 401k matching, and unlimited PTO. This is a hybrid role with 3 days in office. Must be authorized to work in the US."
  },
  {
    "job_posting_id": "test-002",
    "job_title": "Data Engineer",
    "company_name": "StartupXYZ",
    "job_location": "Remote (US)",
    "job_description_text": "Join our fast-paced startup as a Data Engineer! We need someone who can wear many hats and work in a dynamic environment. Required: SQL, Python, cloud experience. Nice to have: Kafka, Snowflake. We offer equity participation. Fully remote position. H1B sponsorship available for exceptional candidates."
  },
  {
    "job_posting_id": "test-003",
    "job_title": "Jr Data Modeler - Day 1 onsite",
    "company_name": "M3BI / Zensar",
    "job_location": "Phoenix, AZ",
    "job_description_text": "Full time with Zensar. Banking client in Phoenix. Requirements: 5 years experience with GCP, BigQuery, Dataflow, SQL, Python. Knowledge of data warehousing, dimensional modeling, normalization. Tools: Wherescape, ERwin, ER/Studio. Nice to Have: GCP Professional Data Engineer certification, data governance, data mesh. Bachelor's degree in Computer Science or related STEM field. Excellent communication and documentation skills. Attention to detail."
  }
]
```

---

### 2.7 Update Local Test Script

**Add to:** `scripts/test_enrichment_local.py`

```python
def test_pass1_extraction():
    """Test Pass 1 extraction with sample jobs."""
    print("\n" + "=" * 60)
    print("Testing Pass 1 Extraction...")
    print("=" * 60)

    import json
    from pathlib import Path

    # Load sample jobs
    fixtures_path = Path(__file__).parent.parent / "tests" / "ai_enrichment" / "fixtures" / "sample_jobs.json"

    if not fixtures_path.exists():
        print(f"✗ Fixtures file not found: {fixtures_path}")
        return False

    with open(fixtures_path) as f:
        sample_jobs = json.load(f)

    print(f"Loaded {len(sample_jobs)} sample jobs")

    # Import modules
    try:
        from enrich_partition.bedrock_client import BedrockClient
        from enrich_partition.prompts.pass1_extraction import build_pass1_prompt, get_pass1_system
        from enrich_partition.parsers.json_parser import parse_llm_response
        from enrich_partition.parsers.validators import validate_extraction
        from enrich_partition.flatteners.extraction import flatten_extraction
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

    model_id = os.getenv("BEDROCK_MODEL_PASS1", "openai.gpt-oss-120b-1:0")
    region = os.getenv("AWS_REGION", "us-east-1")

    client = BedrockClient(model_id=model_id, region=region)

    total_cost = 0.0
    all_passed = True

    # Test with first 1-3 jobs
    for job in sample_jobs[:3]:
        print(f"\n--- Job: {job['job_posting_id']} ---")
        print(f"Title: {job['job_title']}")

        prompt = build_pass1_prompt(
            job_title=job["job_title"],
            company_name=job["company_name"],
            job_location=job["job_location"],
            job_description_text=job["job_description_text"]
        )

        try:
            response_text, input_tokens, output_tokens, cost = client.invoke(
                prompt=prompt,
                system=get_pass1_system(),
                max_tokens=2048
            )

            print(f"Tokens: {input_tokens} in, {output_tokens} out")
            print(f"Cost: ${cost:.6f}")
            total_cost += cost

            # Parse response
            result = parse_llm_response(response_text)
            extraction = result.get("extraction", {})

            # Validate
            if validate_extraction(extraction):
                print("✓ Extraction valid")

                # Flatten
                enriched = flatten_extraction({}, extraction)
                print(f"  ext_salary_disclosed: {enriched.get('ext_salary_disclosed')}")
                print(f"  ext_skills_mentioned: {enriched.get('ext_skills_mentioned')}")
                print(f"  ext_visa_sponsorship_stated: {enriched.get('ext_visa_sponsorship_stated')}")
            else:
                print("✗ Extraction validation failed")
                all_passed = False

        except Exception as e:
            print(f"✗ Error: {e}")
            all_passed = False

    print(f"\n--- Summary ---")
    print(f"Total cost: ${total_cost:.6f}")
    print(f"Avg cost per job: ${total_cost / min(3, len(sample_jobs)):.6f}")

    if all_passed:
        print("\n✓ Pass 1 extraction test PASSED")
    else:
        print("\n✗ Pass 1 extraction test FAILED")

    return all_passed
```

---

## Validation Checklist

- [ ] Bedrock client invokes configurable model successfully
- [ ] Client handles throttling with exponential backoff
- [ ] Pass 1 returns valid JSON for all test jobs
- [ ] JSON parser extracts from markdown code blocks
- [ ] All `ext_` fields present in output (even if null)
- [ ] Validator catches malformed responses
- [ ] Cost per job is within expected range (~$0.0003-0.0008)

---

## Files Created/Modified

| Action | File |
|--------|------|
| CREATE | `src/lambdas/ai_enrichment/enrich_partition/bedrock_client.py` |
| CREATE | `src/lambdas/ai_enrichment/enrich_partition/prompts/__init__.py` |
| CREATE | `src/lambdas/ai_enrichment/enrich_partition/prompts/pass1_extraction.py` |
| CREATE | `src/lambdas/ai_enrichment/enrich_partition/parsers/__init__.py` |
| CREATE | `src/lambdas/ai_enrichment/enrich_partition/parsers/json_parser.py` |
| CREATE | `src/lambdas/ai_enrichment/enrich_partition/parsers/validators.py` |
| CREATE | `src/lambdas/ai_enrichment/enrich_partition/flatteners/__init__.py` |
| CREATE | `src/lambdas/ai_enrichment/enrich_partition/flatteners/extraction.py` |
| CREATE | `tests/ai_enrichment/fixtures/sample_jobs.json` |
| MODIFY | `scripts/test_enrichment_local.py` |

---

## Next Sprint

[Sprint 3: Pass 2 - Structured Inference](sprint-3-pass2.md)
