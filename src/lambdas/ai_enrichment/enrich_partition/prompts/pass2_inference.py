"""
Pass 2: Inference and Normalization Prompt
Uses Pass 1 extraction results to infer and normalize job characteristics.
All fields include confidence scores and evidence.
"""

from typing import Tuple, Dict, Any


SYSTEM_PROMPT = """You are an expert job analyst specializing in data engineering roles.

## YOUR TASK
Use the Pass 1 extraction results and the original job posting to infer and normalize job characteristics.

## CRITICAL RULES
1. ONLY infer with confidence >= 0.5. If lower, use "not_mentioned" or null
2. Every field MUST have: value + confidence (0.0-1.0) + evidence + source
3. Source must be one of: "pass1_derived" | "inferred" | "combined"
4. Never guess - use "not_mentioned" when unclear
5. Confidence scale:
   - 0.9-1.0: Directly from Pass 1 or explicit in text
   - 0.7-0.9: Strong inference with multiple signals
   - 0.5-0.7: Moderate inference with 1-2 signals
   - <0.5: Use "not_mentioned" instead

## CAREER DEVELOPMENT INFERENCE RULES

### growth_path_clarity
Values: "explicit" | "implied" | "vague" | "not_mentioned"

- **explicit** (conf 0.8+): Clear career tracks mentioned
  - Examples: "IC track to Staff/Principal", "path to management", "promotion ladder"

- **implied** (conf 0.6-0.8): Growth mentioned but not specific
  - Examples: "growth opportunities", "advancement potential", "career development"

- **vague** (conf 0.5-0.7): Generic mentions only
  - Examples: "room to grow", "opportunities ahead"

- **not_mentioned**: No career path discussion

### mentorship_signals
Values: "explicit_yes" | "implied" | "not_mentioned"

- **explicit_yes** (conf 0.9+): Formal mentorship program mentioned
  - Examples: "mentorship program", "assigned mentor", "formal coaching"

- **implied** (conf 0.6-0.9): Working with senior people mentioned
  - Examples: "work with senior engineers", "learn from experienced team", "collaborative environment"

- **not_mentioned**: No mentorship signals

### promotion_path_mentioned
Type: boolean with confidence

- **true** (conf 0.8+): Explicit promotion or advancement mentioned
  - Keywords: "promotion", "advancement", "path to", "grow to", "move to"

- **false** (conf 0.9): No promotion mentions

### internal_mobility_mentioned
Type: boolean with confidence

- **true** (conf 0.8+): Internal transfers or role changes mentioned
  - Keywords: "internal mobility", "lateral moves", "explore roles", "team changes"

- **false** (conf 0.9): No mobility mentions

### career_tracks_available
Type: array of ["ic_track", "management_track", "specialist_track", "architect_track"]

- **ic_track**: Individual contributor path (Staff, Principal, Distinguished)
  - Keywords: "IC path", "Staff Engineer", "Principal Engineer", "tech track"

- **management_track**: People management path
  - Keywords: "EM path", "Engineering Manager", "management track", "lead teams"

- **specialist_track**: Deep expertise in specific domain
  - Keywords: "specialist", "subject matter expert", "deep technical expertise"

- **architect_track**: Architecture and design leadership
  - Keywords: "architect path", "system design", "technical architecture"

## SENIORITY INFERENCE RULES

### seniority_level
Values: "intern" | "entry" | "associate" | "junior" | "mid" | "senior" | "staff" | "principal" | "distinguished" | "not_mentioned"

Use IC hierarchy: intern < entry < associate < junior < mid < senior < staff < principal < distinguished

Confidence guidelines:
- 0.9-1.0: Title + years match perfectly (e.g., "Senior Data Engineer" + 5-8 years)
- 0.7-0.9: Title OR years match strongly
- 0.5-0.7: Inferred from responsibilities only
- <0.5: Conflicting signals → use "not_mentioned"

### job_family
Values: "data_engineer" | "analytics_engineer" | "ml_engineer" | "mlops_engineer" | "data_platform_engineer" | "data_architect" | "data_scientist" | "data_analyst" | "bi_engineer" | "research_engineer" | "not_mentioned"

Use title and core responsibilities to determine primary role family.

### sub_specialty
Values: "streaming_realtime" | "batch_etl" | "data_warehouse" | "data_lakehouse" | "ml_infra" | "mlops" | "data_governance" | "data_quality" | "data_modeling" | "cloud_migration" | "reverse_etl" | "api_development" | "observability" | "general" | "not_mentioned"

Focus area within the role based on tools and responsibilities mentioned.

### leadership_expectation
Values: "ic" | "tech_lead_ic" | "architect" | "people_manager" | "tech_and_people_lead" | "not_mentioned"

- **ic**: Pure IC, no leadership
- **tech_lead_ic**: Technical leadership without direct reports
- **architect**: Architecture/design leadership
- **people_manager**: Direct reports, hiring, reviews
- **tech_and_people_lead**: Both technical direction AND people management

## STACK AND CLOUD INFERENCE RULES

### primary_cloud
Values: "aws" | "azure" | "gcp" | "multi" | "on_prem" | "not_mentioned"

- **aws** (conf 0.9+): AWS services mentioned (S3, Redshift, EMR, Glue, etc.)
- **azure** (conf 0.9+): Azure services mentioned (Data Factory, Synapse, Databricks on Azure, etc.)
- **gcp** (conf 0.9+): GCP services mentioned (BigQuery, Dataflow, Composer, etc.)
- **multi** (conf 0.8+): Multiple clouds mentioned with no clear primary
- **on_prem** (conf 0.8+): On-premise focus, Hadoop/Spark clusters, no cloud mentions
- Use Pass 1 ext_cloud_providers to determine

### secondary_clouds
Type: array of cloud providers
- List any additional clouds mentioned beyond primary
- Empty array if only one cloud or none mentioned

### processing_paradigm
Values: "streaming" | "batch" | "hybrid" | "not_mentioned"

- **streaming** (conf 0.8+): Kafka, Kinesis, Flink, real-time, event-driven
- **batch** (conf 0.8+): Airflow, scheduled jobs, daily/hourly pipelines
- **hybrid** (conf 0.7+): Both batch and streaming mentioned

### orchestrator_category
Values: "airflow_like" | "spark_native" | "dbt_core" | "cloud_native" | "dagster_prefect" | "not_mentioned"

- **airflow_like**: Airflow, Luigi, Oozie
- **spark_native**: Spark job scheduling, Databricks workflows
- **dbt_core**: dbt-focused orchestration
- **cloud_native**: AWS Step Functions, GCP Composer, Azure Data Factory
- **dagster_prefect**: Dagster, Prefect modern orchestrators

### storage_layer
Values: "warehouse" | "lake" | "lakehouse" | "mixed" | "not_mentioned"

- **warehouse**: Snowflake, Redshift, BigQuery, Synapse
- **lake**: S3, ADLS, GCS with raw data patterns
- **lakehouse**: Delta Lake, Iceberg, Hudi mentioned
- **mixed**: Both warehouse and lake mentioned

## GEO AND WORK MODEL INFERENCE RULES

### remote_restriction
Values: "same_country" | "same_timezone" | "same_region" | "anywhere" | "not_mentioned"

- **same_country** (conf 0.8+): "US only", "Canada only", specific country required
- **same_timezone** (conf 0.8+): "EST timezone", "Pacific hours", timezone overlap required
- **same_region** (conf 0.7+): "Bay Area", "NYC metro", specific region required
- **anywhere** (conf 0.9+): "Remote from anywhere", "fully distributed"
- Use Pass 1 ext_work_model and ext_location

### timezone_focus
Values: "americas" | "europe" | "apac" | "global" | "specific_country" | "not_mentioned"

- Infer from location, timezone requirements, or team distribution
- **global**: Multi-timezone teams mentioned
- **specific_country**: Single country like "US only"

### relocation_required
Type: boolean

- **true** (conf 0.8+): "Relocation package", "must relocate", "moving to [city]"
- **false** (conf 0.8+): "Remote", "no relocation", "must already be in [location]"

## VISA AND AUTHORIZATION INFERENCE RULES

### h1b_friendly
Type: boolean

- **true** (conf 0.9+): "H1B sponsorship available", "will sponsor H1B"
- **false** (conf 0.9+): "No visa sponsorship", "US citizens only"
- Use Pass 1 ext_visa_sponsorship

### opt_cpt_friendly
Type: boolean

- **true** (conf 0.8+): "OPT/CPT welcome", "students eligible", "F1 visa accepted"
- **false** (conf 0.8+): "Work authorization required" (implies no student visas)

### citizenship_required
Values: "work_auth_only" | "us_citizen_only" | "us_or_gc" | "any" | "not_mentioned"

- **us_citizen_only**: "US citizenship required", "clearance required"
- **us_or_gc**: "US citizen or green card holder"
- **work_auth_only**: "Authorized to work in US" (includes H1B, EAD)
- **any**: "All immigration statuses accepted", no restrictions

## CONTRACT AND COMPENSATION INFERENCE RULES

### w2_vs_1099
Values: "w2" | "c2c" | "1099" | "any" | "not_mentioned"

- **w2** (conf 0.9+): "Full-time employee", "W2 only", benefits mentioned
- **c2c** (conf 0.9+): "Corp to corp", "C2C accepted"
- **1099** (conf 0.9+): "Independent contractor", "1099 contract"
- **any**: Multiple contract types accepted
- Infer from Pass 1 ext_employment_type and ext_contract_type

### benefits_level
Values: "comprehensive" | "standard" | "basic" | "none_mentioned" | "not_mentioned"

- **comprehensive** (conf 0.8+): Equity, unlimited PTO, learning budget, conferences, unique perks (3+ premium benefits)
- **standard** (conf 0.7+): Health insurance, 401k, PTO, standard package (2-3 basic benefits)
- **basic** (conf 0.6+): Minimal benefits mentioned (1 benefit)
- **none_mentioned**: No benefits discussed
- Use Pass 1 ext_benefits array

## REQUIREMENTS CLASSIFICATION INFERENCE RULES

### requirement_strictness
Values: "low" | "medium" | "high" | "not_mentioned"

- **low** (conf 0.7+): Many "nice to have", "preferred", flexible language, welcoming tone
- **medium** (conf 0.7+): Mix of "must have" and "nice to have", balanced requirements
- **high** (conf 0.8+): Many "required", "must have", strict qualifiers, long lists
- Use Pass 1 must_have vs nice_to_have ratio

### scope_definition
Values: "clear" | "vague" | "multi_role" | "not_mentioned"

- **clear** (conf 0.8+): Focused job description, single clear role, well-defined responsibilities
- **vague** (conf 0.7+): Generic descriptions, unclear focus, ambiguous duties
- **multi_role** (conf 0.8+): Multiple roles combined (data engineer + scientist + analyst)

### skill_inflation_detected
Type: boolean

- **true** (conf 0.7+): Junior role with senior requirements, unrealistic skill combinations, 10+ years for mid-level
- **false** (conf 0.8+): Reasonable skills for seniority level, realistic expectations
- Compare Pass 1 ext_years_experience with inferred seniority_level

## OUTPUT FORMAT
Return valid JSON only. No explanatory text before or after.

All inference fields must have this structure:
```json
{
  "value": <the inferred value>,
  "confidence": <float 0.0-1.0>,
  "evidence": "<string explaining reasoning>",
  "source": "pass1_derived" | "inferred" | "combined"
}
```"""


USER_PROMPT_TEMPLATE = """## INPUTS

### Original Job Posting
<job_posting>
Title: {job_title}
Company: {company_name}
Location: {job_location}

Description:
{job_description_text}
</job_posting>

### Pass 1 Extraction Results
<pass1_extraction>
{pass1_json}
</pass1_extraction>

## OUTPUT
Return ONLY valid JSON. Start with {{ and end with }}.

```json
{{
  "inference": {{
    "seniority_and_role": {{
      "seniority_level": {{
        "value": "senior" | "mid" | etc,
        "confidence": 0.92,
        "evidence": "5-8 years + senior in title",
        "source": "combined"
      }},
      "job_family": {{
        "value": "data_engineer" | "analytics_engineer" | etc,
        "confidence": 0.98,
        "evidence": "Title is Data Engineer, core focus on pipelines",
        "source": "pass1_derived"
      }},
      "sub_specialty": {{
        "value": "streaming_realtime" | "batch_etl" | etc,
        "confidence": 0.85,
        "evidence": "Kafka + Flink mentioned heavily",
        "source": "inferred"
      }},
      "leadership_expectation": {{
        "value": "tech_lead_ic" | "ic" | etc,
        "confidence": 0.78,
        "evidence": "Mentoring and code review mentioned, no direct reports",
        "source": "inferred"
      }}
    }},
    "stack_and_cloud": {{
      "primary_cloud": {{
        "value": "aws" | "azure" | "gcp" | "multi" | "on_prem" | "not_mentioned",
        "confidence": 0.95,
        "evidence": "AWS mentioned explicitly multiple times",
        "source": "pass1_derived"
      }},
      "secondary_clouds": {{
        "value": [],
        "confidence": 0.90,
        "evidence": "No other clouds mentioned",
        "source": "pass1_derived"
      }},
      "processing_paradigm": {{
        "value": "streaming" | "batch" | "hybrid" | "not_mentioned",
        "confidence": 0.88,
        "evidence": "Kafka, real-time processing emphasis",
        "source": "inferred"
      }},
      "orchestrator_category": {{
        "value": "airflow_like" | "spark_native" | "dbt_core" | "cloud_native" | "dagster_prefect" | "not_mentioned",
        "confidence": 0.95,
        "evidence": "Airflow explicitly mentioned",
        "source": "pass1_derived"
      }},
      "storage_layer": {{
        "value": "warehouse" | "lake" | "lakehouse" | "mixed" | "not_mentioned",
        "confidence": 0.82,
        "evidence": "Snowflake mentioned with S3 data lake patterns",
        "source": "inferred"
      }}
    }},
    "geo_and_work_model": {{
      "remote_restriction": {{
        "value": "same_country" | "same_timezone" | "same_region" | "anywhere" | "not_mentioned",
        "confidence": 0.88,
        "evidence": "Bay Area required but hybrid model allows flexibility",
        "source": "combined"
      }},
      "timezone_focus": {{
        "value": "americas" | "europe" | "apac" | "global" | "specific_country" | "not_mentioned",
        "confidence": 0.92,
        "evidence": "Pacific Time Zone preferred mentioned",
        "source": "pass1_derived"
      }},
      "relocation_required": {{
        "value": false,
        "confidence": 0.85,
        "evidence": "Must be based in Bay Area - already resident",
        "source": "inferred"
      }}
    }},
    "visa_and_authorization": {{
      "h1b_friendly": {{
        "value": false,
        "confidence": 0.90,
        "evidence": "No visa sponsorship stated explicitly",
        "source": "pass1_derived"
      }},
      "opt_cpt_friendly": {{
        "value": false,
        "confidence": 0.85,
        "evidence": "Work authorization required suggests no student visa support",
        "source": "inferred"
      }},
      "citizenship_required": {{
        "value": "work_auth_only" | "us_citizen_only" | "us_or_gc" | "any" | "not_mentioned",
        "confidence": 0.88,
        "evidence": "Must be authorized to work - no citizenship requirement",
        "source": "pass1_derived"
      }}
    }},
    "contract_and_compensation": {{
      "w2_vs_1099": {{
        "value": "w2" | "c2c" | "1099" | "any" | "not_mentioned",
        "confidence": 0.90,
        "evidence": "Full-time employee position suggests W2",
        "source": "inferred"
      }},
      "benefits_level": {{
        "value": "comprehensive" | "standard" | "basic" | "none_mentioned" | "not_mentioned",
        "confidence": 0.85,
        "evidence": "Equity, unlimited PTO, learning budget, conferences mentioned",
        "source": "pass1_derived"
      }}
    }},
    "career_development": {{
      "growth_path_clarity": {{
        "value": "explicit" | "implied" | "vague" | "not_mentioned",
        "confidence": 0.75,
        "evidence": "Mentions growth opportunities but no specific tracks",
        "source": "inferred"
      }},
      "mentorship_signals": {{
        "value": "explicit_yes" | "implied" | "not_mentioned",
        "confidence": 0.80,
        "evidence": "Mentions working with senior staff engineers",
        "source": "inferred"
      }},
      "promotion_path_mentioned": {{
        "value": true | false,
        "confidence": 0.90,
        "evidence": "Explicitly states 'path to Staff Engineer'",
        "source": "pass1_derived"
      }},
      "internal_mobility_mentioned": {{
        "value": true | false,
        "confidence": 0.95,
        "evidence": "No mention of internal transfers",
        "source": "pass1_derived"
      }},
      "career_tracks_available": {{
        "value": ["ic_track", "management_track"],
        "confidence": 0.70,
        "evidence": "Mentions both IC (Staff/Principal) and management paths",
        "source": "inferred"
      }}
    }},
    "requirements_classification": {{
      "requirement_strictness": {{
        "value": "low" | "medium" | "high" | "not_mentioned",
        "confidence": 0.73,
        "evidence": "Clear must-haves vs nice-to-haves distinction",
        "source": "inferred"
      }},
      "scope_definition": {{
        "value": "clear" | "vague" | "multi_role" | "not_mentioned",
        "confidence": 0.82,
        "evidence": "Focused on data engineering, not multi-role hybrid",
        "source": "inferred"
      }},
      "skill_inflation_detected": {{
        "value": false,
        "confidence": 0.75,
        "evidence": "Reasonable skill set for senior level",
        "source": "inferred"
      }}
    }}
  }}
}}
```

Analyze now:"""


def build_pass2_prompt(
    job_title: str,
    company_name: str,
    job_location: str,
    job_description_text: str,
    pass1_extraction: Dict[str, Any],
) -> Tuple[str, str]:
    """
    Build Pass 2 inference prompt.

    Args:
        job_title: Job title
        company_name: Company name
        job_location: Job location
        job_description_text: Full job description text
        pass1_extraction: Pass 1 extraction results (dict)

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    import json

    # Format Pass 1 results as JSON string
    pass1_json = json.dumps(pass1_extraction, indent=2)

    # Truncate if too long
    max_description_length = 10000
    if len(job_description_text) > max_description_length:
        job_description_text = job_description_text[:max_description_length] + "\n\n[TRUNCATED]"

    max_pass1_length = 8000
    if len(pass1_json) > max_pass1_length:
        pass1_json = pass1_json[:max_pass1_length] + "\n\n[TRUNCATED]"

    user_prompt = USER_PROMPT_TEMPLATE.format(
        job_title=job_title or "Not specified",
        company_name=company_name or "Not specified",
        job_location=job_location or "Not specified",
        job_description_text=job_description_text or "No description available",
        pass1_json=pass1_json,
    )

    return SYSTEM_PROMPT, user_prompt
