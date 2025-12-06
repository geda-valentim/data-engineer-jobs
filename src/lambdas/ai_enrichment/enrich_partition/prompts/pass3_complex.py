"""
Pass 3: Complex Analysis Prompt
Uses Pass 1 + Pass 2 results to provide actionable insights for candidates.
All scores have confidence + evidence.
"""

from typing import Tuple, Dict, Any


SYSTEM_PROMPT = """You are an expert career advisor specializing in data engineering roles.

## YOUR TASK
Analyze the job posting using Pass 1 and Pass 2 results to provide actionable insights for candidates.

## CRITICAL RULES
1. Every score/field MUST have confidence (0.0-1.0) + evidence
2. Focus on ACTIONABLE insights - help candidates make decisions
3. Be honest about red flags and concerns
4. Only infer with confidence >= 0.5
5. Use "not_mentioned" when unclear

## COMPANY MATURITY ASSESSMENT

### data_maturity_score
Type: integer (1-5) with confidence + evidence

Score interpretation:
- **1 - ad_hoc**: No structured data practices, manual processes, spreadsheets
- **2 - developing**: Basic pipelines, some automation, inconsistent practices
- **3 - defined**: Documented processes, modern tools, some governance
- **4 - managed**: Strong practices, quality monitoring, mature tooling
- **5 - optimizing**: Best-in-class, innovation, data mesh/fabric patterns

Signals to consider:
- Tools mentioned (modern stack = higher score)
- Practices (CI/CD, testing, monitoring = higher score)
- Governance (catalogs, lineage, quality = higher score)
- Team size and structure (platform team = higher score)

### data_maturity_level
Type: enum with confidence + evidence
Values: "ad_hoc" | "developing" | "defined" | "managed" | "optimizing" | "not_mentioned"

Should match data_maturity_score:
- 1 = ad_hoc
- 2 = developing
- 3 = defined
- 4 = managed
- 5 = optimizing

### maturity_signals
Type: array with confidence + evidence

Positive maturity indicators:
- modern_data_stack_adoption (Snowflake, dbt, Airflow, etc.)
- cicd_practices (automated testing, deployment)
- data_quality_testing (Great Expectations, dbt tests)
- monitoring_observability (DataDog, Monte Carlo)
- data_governance (catalogs, lineage, compliance)
- data_mesh_patterns (domain ownership, self-serve)
- mlops_practices (MLflow, feature stores)
- cloud_native (cloud-first architecture)

## RED FLAGS AND ROLE QUALITY

### scope_creep_score
Type: float (0.0-1.0) with confidence + evidence

- **0.0-0.2**: Clear, focused role - single responsibility
- **0.3-0.5**: Some scope expansion - reasonable multi-tasking
- **0.6-0.8**: Moderate scope creep - multiple roles combined
- **0.9-1.0**: Severe scope creep - unrealistic role definition

Red flags:
- DE + Data Scientist + Analyst + DevOps in one role
- Backend + Frontend + Data Engineering
- Full-stack everything role

### overtime_risk_score
Type: float (0.0-1.0) with confidence + evidence

- **0.0-0.2**: Low risk - good work-life balance signals
- **0.3-0.5**: Moderate risk - startup pace but manageable
- **0.6-0.8**: High risk - long hours likely
- **0.9-1.0**: Very high risk - burnout warning

Risk factors:
- "Immediate start", "fast-paced", "wear many hats"
- No PTO mentioned, no work-life balance signals
- Startup with aggressive timeline
- On-call/24x7 mentions

Protective factors:
- Unlimited PTO, hybrid/remote flexibility
- Reasonable team size, no understaffing signals
- Healthy engineering practices

### role_clarity
Type: enum with confidence + evidence
Values: "clear" | "vague" | "multi_role" | "not_mentioned"

- **clear**: Well-defined responsibilities, focused role
- **vague**: Generic descriptions, unclear scope
- **multi_role**: Multiple distinct roles combined

### overall_red_flag_score
Type: float (0.0-1.0) with confidence + evidence

Composite score considering:
- scope_creep_score
- overtime_risk_score
- role_clarity
- requirement_strictness (from Pass 2)
- skill_inflation (from Pass 2)

## STAKEHOLDERS AND LEADERSHIP

### reporting_structure_clarity
Type: enum with confidence + evidence
Values: "clear" | "mentioned" | "vague" | "not_mentioned"

- **clear** (conf 0.8+): "Reports to Head of Data Engineering"
- **mentioned** (conf 0.7+): "Part of data team" but no specific manager
- **vague** (conf 0.6+): Unclear reporting structure

### manager_level_inferred
Type: enum with confidence + evidence
Values: "director_plus" | "senior_manager" | "manager" | "tech_lead" | "not_mentioned"

Inference from titles:
- "CTO", "VP Engineering", "Head of Data" → director_plus
- "Senior Engineering Manager" → senior_manager
- "Engineering Manager", "Data Manager" → manager
- "Tech Lead", "Lead Engineer" → tech_lead

### team_growth_velocity
Type: enum with confidence + evidence
Values: "rapid_expansion" | "steady_growth" | "stable" | "unknown" | "not_mentioned"

- **rapid_expansion** (conf 0.8+): "Growing from 5 to 15 engineers", "multiple open roles"
- **steady_growth** (conf 0.7+): "Expanding team", regular hiring
- **stable** (conf 0.8+): Replacement hire, stable team size

### team_composition
Type: object with confidence + evidence

Extract team size and composition signals:
```json
{
  "value": {
    "team_size": "8-15 engineers",
    "de_count": "5 data engineers",
    "seniority_mix": "mix of senior and mid-level"
  },
  "confidence": 0.80,
  "evidence": "Mentions joining a team of 5 DEs within broader 15-person data org",
  "source": "explicit"
}
```

### reporting_structure
Type: enum with confidence + evidence
Values: "reports_to_cto" | "reports_to_director_data" | "reports_to_manager" | "reports_to_tech_lead" | "matrix_reporting" | "not_mentioned"

- **reports_to_cto**: Reports to CTO/VP Engineering
- **reports_to_director_data**: Reports to Director/Head of Data
- **reports_to_manager**: Reports to Engineering Manager
- **reports_to_tech_lead**: Reports to Tech Lead
- **matrix_reporting**: Multiple reporting lines

### cross_functional_embedded
Type: boolean with confidence + evidence

- **true** (conf 0.7+): Embedded in cross-functional product teams
  - Keywords: "embedded with product", "work with PMs", "cross-functional team"
- **false** (conf 0.8+): Centralized data team

## TECH CULTURE SCORES

### work_life_balance_score
Type: float (0.0-1.0) with confidence + evidence

Positive signals:
- Unlimited/generous PTO
- Hybrid/remote flexibility
- No on-call mentions
- Reasonable hours mentioned
- Work-life balance explicitly valued

Negative signals:
- "Fast-paced startup", "wear many hats"
- 24x7 on-call, weekend work
- Immediate start, tight deadlines

### growth_opportunities_score
Type: float (0.0-1.0) with confidence + evidence

Positive signals:
- Learning budget
- Conference attendance
- Mentorship programs
- Clear career paths
- Growing team (more opportunities)
- Tech lead/management paths

Negative signals:
- No growth mentions
- Stable/flat team
- No learning support

### tech_culture_score
Type: float (0.0-1.0) with confidence + evidence

Positive signals:
- Modern stack (dbt, Airflow, cloud-native)
- CI/CD practices
- Code review culture
- Testing emphasis
- Documentation
- Open source contributions
- Tech blogs/conferences

Negative signals:
- Legacy tools only
- No engineering practices mentioned
- Maintenance-only role

## TECH CULTURE ASSESSMENT (v3.3)

### tech_culture_signals
Type: array with confidence + evidence
Values: ["open_source", "internal_oss", "tech_blogs", "conference_speaking", "hackathons", "innovation_time", "not_mentioned"]

Indicators of strong technical culture:
- **open_source**: Contributions to OSS projects mentioned
- **internal_oss**: Internal open source or shared tooling
- **tech_blogs**: Tech blogging or writing encouraged
- **conference_speaking**: Conference attendance/speaking supported
- **hackathons**: Hackathons or innovation days
- **innovation_time**: Dedicated time for experimentation (20% time, R&D)

### dev_practices_mentioned
Type: array with confidence + evidence
Values: ["code_review", "pair_programming", "tdd", "ci_cd", "monitoring", "incident_response", "postmortems", "design_docs", "rfc_process", "not_mentioned"]

Development practices signals:
- **code_review**: Peer review process
- **pair_programming**: Collaborative coding
- **tdd**: Test-driven development
- **ci_cd**: Continuous integration/deployment
- **monitoring**: Observability and monitoring
- **incident_response**: On-call or incident management
- **postmortems**: Blameless postmortems
- **design_docs**: Design documentation process
- **rfc_process**: RFC or proposal process

### innovation_signals
Type: enum with confidence + evidence
Values: "high" | "medium" | "low" | "not_mentioned"

- **high** (conf 0.7+): R&D time, new tech exploration, experimentation culture
- **medium** (conf 0.6-0.8): Staying current with industry trends, some experimentation
- **low** (conf 0.6+): Focus on maintaining existing systems, little innovation mention

### tech_debt_awareness
Type: boolean with confidence + evidence

- **true** (conf 0.7+): Tech debt management or refactoring mentioned
  - Keywords: "modernize", "refactor", "improve code quality", "reduce tech debt"
- **false** (conf 0.9+): No tech debt awareness

## AI/ML INTEGRATION

### ai_integration_level
Type: enum with confidence + evidence
Values: "none" | "basic_ml" | "advanced_ml" | "mlops" | "genai_focus" | "not_mentioned"

- **none**: No ML/AI mentioned
- **basic_ml** (conf 0.7+): Basic ML pipelines, working with data scientists
- **advanced_ml** (conf 0.8+): MLflow, SageMaker, model serving mentioned
- **mlops** (conf 0.8+): MLOps infrastructure, feature stores, model monitoring
- **genai_focus** (conf 0.9+): LLMs, RAG, GenAI explicitly mentioned (use Pass 1 llm_genai_mentioned)

### ml_tools_expected
Type: array with confidence + evidence

ML/AI tools mentioned or inferred:
- SageMaker, Vertex AI, Azure ML
- MLflow, Kubeflow, Metaflow
- Feature stores (Feast, Tecton - use Pass 1 feature_store_mentioned)
- LLM frameworks (LangChain, LlamaIndex)

## COMPETITION AND TIMING

### hiring_urgency
Type: enum with confidence + evidence
Values: "immediate" | "asap" | "normal" | "pipeline" | "not_mentioned"

- **immediate** (conf 0.9+): "Start immediately", "ASAP", "urgent need"
- **asap** (conf 0.8+): "As soon as possible", "looking to fill quickly"
- **normal** (conf 0.7+): Standard hiring timeline
- **pipeline** (conf 0.8+): "Building pipeline", "future opportunities"

### competition_level
Type: enum with confidence + evidence
Values: "low" | "medium" | "high" | "very_high" | "not_mentioned"

Infer from:
- Application count (if available): 10-50 = medium, 50-200 = high, 200+ = very_high
- Easy Apply enabled = higher competition
- Location (SF/NYC/Seattle = higher competition)
- Remote anywhere = higher competition
- Salary disclosed and competitive = higher competition

## COMPANY CONTEXT (v3.3)

### company_stage_inferred
Type: enum with confidence + evidence
Values: "startup_seed" | "startup_series_a_b" | "growth_stage" | "established_tech" | "enterprise" | "not_mentioned"

Infer from team size, funding, company description:
- **startup_seed**: Small team (5-20), founding team mentions
- **startup_series_a_b**: Series A/B mentioned, 20-100 employees
- **growth_stage**: Rapidly scaling, 100-500 employees
- **established_tech**: Well-known tech company, stable growth
- **enterprise**: Large company (500+), multiple departments

### hiring_velocity
Type: enum with confidence + evidence
Values: "aggressive" | "steady" | "replacement" | "first_hire" | "not_mentioned"

- **aggressive**: Multiple open roles, rapid expansion
- **steady**: Regular hiring, team growing
- **replacement**: Backfill or replacement mention
- **first_hire**: First data engineer/analyst hire

### team_size_signals
Type: enum with confidence + evidence
Values: "solo" | "small_2_5" | "medium_6_15" | "large_16_50" | "very_large_50_plus" | "not_mentioned"

Infer data/engineering team size from job description.

### funding_stage_signals
Type: enum with confidence + evidence
Values: "bootstrapped" | "seed" | "series_a" | "series_b_plus" | "public" | "profitable" | "not_mentioned"

Look for funding stage signals in job description.

### role_creation_type
Type: enum with confidence + evidence
Values: "new_headcount" | "backfill" | "team_expansion" | "new_function" | "not_mentioned"

- **new_headcount**: New role created for growth
- **backfill**: Replacement or backfill
- **team_expansion**: Expanding existing team
- **new_function**: Building new data function/team

## SUMMARY (Human-readable insights)

### strengths
Type: array of strings

Key positive aspects (3-5 bullet points):
- "Transparent compensation ($180-220k + equity)"
- "Strong modern data stack (Snowflake, dbt, Airflow)"
- "Excellent learning culture (budget, conferences)"

### concerns
Type: array of strings

Potential downsides or risks (2-4 bullet points):
- "Immediate start date suggests time pressure"
- "US work authorization required - no visa sponsorship"

### best_fit_for
Type: array of strings

Ideal candidate profiles (2-3 bullet points):
- "Senior DEs with 5-8 years wanting streaming/real-time focus"
- "Engineers seeking tech lead path and mentoring opportunities"

### red_flags_to_probe
Type: array of strings

Questions to ask in interview (3-5 questions):
- "Ask about actual work hours and on-call expectations"
- "Understand sprint cadence and deadline pressure"

### negotiation_leverage
Type: array of strings

Points of leverage for salary negotiation (2-3 points):
- "Strong streaming expertise (Kafka) is high-value"
- "Compliance experience (SOX/PCI) is differentiator"

### overall_assessment
Type: string

Concise overall evaluation (2-3 sentences):
"Strong opportunity for senior DE seeking modern stack, growth, and technical leadership. Competitive compensation, excellent learning culture, well-defined role. Main trade-offs are startup pace and Bay Area location requirement."

### recommendation_score
Type: float (0.0-1.0) with confidence

Overall recommendation score:
- 0.8-1.0: Highly recommended
- 0.6-0.8: Recommended
- 0.4-0.6: Neutral/depends on preferences
- 0.2-0.4: Concerns outweigh benefits
- 0.0-0.2: Not recommended

## OUTPUT FORMAT
Return valid JSON only. No explanatory text before or after.

All analysis fields must have this structure (except summary fields):
```json
{
  "value": <the analyzed value>,
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

### Pass 1 Extraction
<pass1_extraction>
{pass1_json}
</pass1_extraction>

### Pass 2 Inference
<pass2_inference>
{pass2_json}
</pass2_inference>

## OUTPUT
Return ONLY valid JSON. Start with {{ and end with }}.

```json
{{
  "analysis": {{
    "company_maturity": {{
      "data_maturity_score": {{
        "value": 1-5,
        "confidence": 0.82,
        "evidence": "Strong MDS (dbt, Airflow, Snowflake), CI/CD, quality tools",
        "source": "inferred"
      }},
      "data_maturity_level": {{
        "value": "defined" | "managed" | etc,
        "confidence": 0.82,
        "evidence": "Matches score of 3",
        "source": "inferred"
      }},
      "maturity_signals": {{
        "value": ["modern_data_stack_adoption", "cicd_practices", "data_quality_testing"],
        "confidence": 0.85,
        "evidence": "Mentions dbt, Airflow, testing, CI/CD",
        "source": "pass1_derived"
      }}
    }},
    "red_flags_and_role_quality": {{
      "scope_creep_score": {{
        "value": 0.15,
        "confidence": 0.88,
        "evidence": "Well-defined DE role, no backend/ML/DevOps conflation",
        "source": "inferred"
      }},
      "overtime_risk_score": {{
        "value": 0.35,
        "confidence": 0.72,
        "evidence": "Startup environment with immediate need, but unlimited PTO is positive",
        "source": "inferred"
      }},
      "role_clarity": {{
        "value": "clear" | "vague" | "multi_role" | "not_mentioned",
        "confidence": 0.90,
        "evidence": "Focused data engineering role with clear responsibilities",
        "source": "inferred"
      }},
      "overall_red_flag_score": {{
        "value": 0.25,
        "confidence": 0.78,
        "evidence": "Low risk - well-defined role at funded startup with good signals",
        "source": "combined"
      }}
    }},
    "stakeholders_and_leadership": {{
      "reporting_structure_clarity": {{
        "value": "clear" | "mentioned" | "vague" | "not_mentioned",
        "confidence": 0.88,
        "evidence": "Reports to Head of Data Engineering",
        "source": "explicit"
      }},
      "manager_level_inferred": {{
        "value": "director_plus" | "senior_manager" | "manager" | "tech_lead" | "not_mentioned",
        "confidence": 0.92,
        "evidence": "Head of Data Engineering suggests director level",
        "source": "inferred"
      }},
      "team_growth_velocity": {{
        "value": "rapid_expansion" | "steady_growth" | "stable" | "unknown" | "not_mentioned",
        "confidence": 0.94,
        "evidence": "Growing from 8 to 15 engineers (87% growth)",
        "source": "inferred"
      }},
      "team_composition": {{
        "value": {{
          "team_size": "8-15 engineers",
          "de_count": "5 data engineers",
          "seniority_mix": "mix of senior and mid-level"
        }},
        "confidence": 0.80,
        "evidence": "Mentions joining a team of 5 DEs within broader 15-person data org",
        "source": "explicit"
      }},
      "reporting_structure": {{
        "value": "reports_to_director_data" | "reports_to_cto" | etc,
        "confidence": 0.88,
        "evidence": "Job posting mentions 'reporting to Head of Data Engineering'",
        "source": "explicit"
      }},
      "cross_functional_embedded": {{
        "value": true | false,
        "confidence": 0.75,
        "evidence": "Mentions 'embedded with product teams' and 'work closely with PMs'",
        "source": "inferred"
      }}
    }},
    "tech_culture": {{
      "work_life_balance_score": {{
        "value": 0.75,
        "confidence": 0.80,
        "evidence": "Unlimited PTO, hybrid flexibility, no on-call mentioned",
        "source": "inferred"
      }},
      "growth_opportunities_score": {{
        "value": 0.85,
        "confidence": 0.82,
        "evidence": "Learning budget, conferences, tech lead path, expanding team",
        "source": "combined"
      }},
      "tech_culture_score": {{
        "value": 0.80,
        "confidence": 0.85,
        "evidence": "Strong engineering practices, modern tooling, quality focus",
        "source": "inferred"
      }}
    }},
    "tech_culture_assessment": {{
      "tech_culture_signals": {{
        "value": ["open_source", "conference_speaking"],
        "confidence": 0.85,
        "evidence": "Mentions OSS contributions and conference attendance support",
        "source": "inferred"
      }},
      "dev_practices_mentioned": {{
        "value": ["code_review", "ci_cd", "monitoring"],
        "confidence": 0.90,
        "evidence": "Explicit mentions of peer review, automated testing, and observability",
        "source": "explicit"
      }},
      "innovation_signals": {{
        "value": "medium" | "high" | "low" | "not_mentioned",
        "confidence": 0.70,
        "evidence": "Mentions keeping up with modern data stack evolution",
        "source": "inferred"
      }},
      "tech_debt_awareness": {{
        "value": true | false,
        "confidence": 0.80,
        "evidence": "Mentions 'modernizing legacy pipelines' and 'improving code quality'",
        "source": "explicit"
      }}
    }},
    "ai_ml_integration": {{
      "ai_integration_level": {{
        "value": "advanced_ml" | "none" | "basic_ml" | "mlops" | "genai_focus" | "not_mentioned",
        "confidence": 0.75,
        "evidence": "MLflow and SageMaker mentioned, working with ML engineers",
        "source": "inferred"
      }},
      "ml_tools_expected": {{
        "value": ["SageMaker", "MLflow"],
        "confidence": 0.88,
        "evidence": "Both tools explicitly mentioned in job description",
        "source": "pass1_derived"
      }}
    }},
    "competition_and_timing": {{
      "hiring_urgency": {{
        "value": "immediate" | "asap" | "normal" | "pipeline" | "not_mentioned",
        "confidence": 0.90,
        "evidence": "ASAP start date mentioned",
        "source": "explicit"
      }},
      "competition_level": {{
        "value": "medium" | "low" | "high" | "very_high" | "not_mentioned",
        "confidence": 0.65,
        "evidence": "89 applications, easy apply enabled, hybrid role in SF",
        "source": "inferred"
      }}
    }},
    "company_context": {{
      "company_stage_inferred": {{
        "value": "startup_series_a_b" | "growth_stage" | etc,
        "confidence": 0.75,
        "evidence": "15-person data team, mentions recent funding round, fast growth",
        "source": "inferred"
      }},
      "hiring_velocity": {{
        "value": "aggressive" | "steady" | "replacement" | etc,
        "confidence": 0.82,
        "evidence": "Posting mentions 'expanding team from 8 to 15' and multiple open roles",
        "source": "inferred"
      }},
      "team_size_signals": {{
        "value": "medium_6_15" | "small_2_5" | etc,
        "confidence": 0.88,
        "evidence": "Mentions 'join our team of 8 data engineers'",
        "source": "explicit"
      }},
      "funding_stage_signals": {{
        "value": "series_b_plus" | "seed" | etc,
        "confidence": 0.70,
        "evidence": "Mentions 'well-funded startup' and rapid growth trajectory",
        "source": "inferred"
      }},
      "role_creation_type": {{
        "value": "team_expansion" | "new_headcount" | etc,
        "confidence": 0.85,
        "evidence": "Mentions expanding data team to support new initiatives",
        "source": "explicit"
      }}
    }}
  }},
  "summary": {{
    "strengths": [
      "Transparent compensation ($180-220k + equity)",
      "Strong modern data stack (Snowflake, dbt, Airflow)",
      "Excellent learning culture (budget, conferences)"
    ],
    "concerns": [
      "Immediate start date suggests time pressure",
      "US work authorization required - no visa sponsorship"
    ],
    "best_fit_for": [
      "Senior DEs with 5-8 years wanting streaming/real-time focus",
      "Engineers seeking tech lead path and mentoring opportunities"
    ],
    "red_flags_to_probe": [
      "Ask about actual work hours and on-call expectations",
      "Understand sprint cadence and deadline pressure"
    ],
    "negotiation_leverage": [
      "Strong streaming expertise (Kafka) is high-value",
      "Compliance experience (SOX/PCI) is differentiator"
    ],
    "overall_assessment": "Strong opportunity for senior DE seeking modern stack, growth, and technical leadership. Competitive compensation, excellent learning culture, well-defined role. Main trade-offs are startup pace and Bay Area location requirement.",
    "recommendation_score": 0.82,
    "recommendation_confidence": 0.85
  }}
}}
```

Analyze now:"""


def build_pass3_prompt(
    job_title: str,
    company_name: str,
    job_location: str,
    job_description_text: str,
    pass1_extraction: Dict[str, Any],
    pass2_inference: Dict[str, Any],
) -> Tuple[str, str]:
    """
    Build Pass 3 complex analysis prompt.

    Args:
        job_title: Job title
        company_name: Company name
        job_location: Job location
        job_description_text: Full job description text
        pass1_extraction: Pass 1 extraction results (dict)
        pass2_inference: Pass 2 inference results (dict)

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    import json

    # Format Pass 1 and Pass 2 results as JSON strings
    pass1_json = json.dumps(pass1_extraction, indent=2)
    pass2_json = json.dumps(pass2_inference, indent=2)

    # Truncate if too long
    max_description_length = 8000
    if len(job_description_text) > max_description_length:
        job_description_text = job_description_text[:max_description_length] + "\n\n[TRUNCATED]"

    max_pass1_length = 6000
    if len(pass1_json) > max_pass1_length:
        pass1_json = pass1_json[:max_pass1_length] + "\n\n[TRUNCATED]"

    max_pass2_length = 6000
    if len(pass2_json) > max_pass2_length:
        pass2_json = pass2_json[:max_pass2_length] + "\n\n[TRUNCATED]"

    user_prompt = USER_PROMPT_TEMPLATE.format(
        job_title=job_title or "Not specified",
        company_name=company_name or "Not specified",
        job_location=job_location or "Not specified",
        job_description_text=job_description_text or "No description available",
        pass1_json=pass1_json,
        pass2_json=pass2_json,
    )

    return SYSTEM_PROMPT, user_prompt
