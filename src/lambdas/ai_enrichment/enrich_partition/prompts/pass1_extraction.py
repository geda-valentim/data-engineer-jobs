"""
Pass 1: Factual Extraction Prompt
Extracts ONLY explicitly stated information from job postings.
No inference, no interpretation - if not written, return null.
"""

from typing import Tuple


SYSTEM_PROMPT = """You are a precise data extractor. Extract ONLY explicitly stated information from job postings.

## CRITICAL RULES
1. Extract ONLY what is written - NO inference, NO interpretation
2. If information is not explicitly stated, use null
3. Copy exact text for text fields (like work_auth_text)
4. For boolean fields, only return true if explicitly mentioned
5. This data will be used by subsequent analysis - accuracy is critical

## ANTI-HALLUCINATION RULES
1. NEVER invent information not present in the text
2. "null" is ALWAYS better than a guess
3. Use "not_mentioned" for visa/authorization when not explicit
4. Do NOT estimate salaries if not disclosed
5. When in doubt, under-extract rather than over-extract

## EXPERIENCE EXTRACTION RULES
- "5+ years" → min: 5, max: null, text: "5+ years"
- "3-5 years" → min: 3, max: 5, text: "3-5 years"
- "At least 7 years" → min: 7, max: null, text: "At least 7 years"
- "5 years experience" → min: 5, max: 5, text: "5 years experience"
- "Senior level" (no number) → min: null, max: null, text: "Senior level"
- If no experience mentioned → min: null, max: null, text: null"""


USER_PROMPT_TEMPLATE = """## INPUT
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
      "years_experience_min": number or null,
      "years_experience_max": number or null,
      "years_experience_text": string or null,
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

Extract now:"""


def build_pass1_prompt(
    job_title: str,
    company_name: str,
    job_location: str,
    job_description_text: str,
) -> Tuple[str, str]:
    """
    Build Pass 1 extraction prompt.

    Args:
        job_title: Job title
        company_name: Company name
        job_location: Job location
        job_description_text: Full job description text

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    # Truncate description if too long (to stay within token limits)
    max_description_length = 12000  # ~3000 tokens
    if len(job_description_text) > max_description_length:
        job_description_text = job_description_text[:max_description_length] + "\n\n[TRUNCATED]"

    user_prompt = USER_PROMPT_TEMPLATE.format(
        job_title=job_title or "Not specified",
        company_name=company_name or "Not specified",
        job_location=job_location or "Not specified",
        job_description_text=job_description_text or "No description available",
    )

    return SYSTEM_PROMPT, user_prompt
