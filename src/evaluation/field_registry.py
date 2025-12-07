"""
Field type classification registry for all enrichment fields.
"""

from typing import Dict, List, Tuple

# Field type constants
BOOLEAN = "boolean"
ENUM = "enum"
NUMERIC = "numeric"
STRING = "string"
ARRAY = "array"
INFERENCE = "inference"


# Pass 1 - Extraction fields
PASS1_FIELDS: Dict[str, str] = {
    # Boolean fields
    "ext_salary_disclosed": BOOLEAN,
    "ext_equity_mentioned": BOOLEAN,
    "ext_learning_budget_mentioned": BOOLEAN,
    "ext_conference_budget_mentioned": BOOLEAN,
    "ext_hardware_choice_mentioned": BOOLEAN,
    "ext_llm_genai_mentioned": BOOLEAN,
    "ext_feature_store_mentioned": BOOLEAN,

    # Enum fields
    "ext_salary_period": ENUM,
    "ext_salary_currency": ENUM,
    "ext_visa_sponsorship_stated": ENUM,
    "ext_security_clearance_stated": ENUM,
    "ext_work_model_stated": ENUM,
    "ext_employment_type_stated": ENUM,
    "ext_contract_type": ENUM,
    "ext_extension_possible": ENUM,
    "ext_conversion_to_fte": ENUM,
    "ext_start_date": ENUM,
    "ext_pay_type": ENUM,
    "ext_rate_negotiable": ENUM,
    "ext_overtime_paid": ENUM,
    "ext_geo_restriction_type": ENUM,
    "ext_residency_requirement": ENUM,
    "ext_pto_policy": ENUM,

    # Numeric fields
    "ext_salary_min": NUMERIC,
    "ext_salary_max": NUMERIC,
    "ext_hourly_rate_min": NUMERIC,
    "ext_hourly_rate_max": NUMERIC,
    "ext_daily_rate_min": NUMERIC,
    "ext_daily_rate_max": NUMERIC,
    "ext_years_experience_min": NUMERIC,
    "ext_years_experience_max": NUMERIC,
    "ext_contract_duration_months": NUMERIC,

    # String fields
    "ext_salary_text_raw": STRING,
    "ext_hourly_rate_text_raw": STRING,
    "ext_daily_rate_text_raw": STRING,
    "ext_work_auth_text": STRING,
    "ext_citizenship_text": STRING,
    "ext_location_restriction_text": STRING,
    "ext_contract_duration_text": STRING,
    "ext_start_date_text": STRING,
    "ext_probation_period_text": STRING,
    "ext_years_experience_text": STRING,
    "ext_education_stated": STRING,
    "ext_team_info_text": STRING,
    "ext_company_description_text": STRING,

    # Array fields
    "ext_must_have_hard_skills": ARRAY,
    "ext_nice_to_have_hard_skills": ARRAY,
    "ext_must_have_soft_skills": ARRAY,
    "ext_nice_to_have_soft_skills": ARRAY,
    "ext_certifications_mentioned": ARRAY,
    "ext_benefits_mentioned": ARRAY,
    "ext_allowed_countries": ARRAY,
    "ext_excluded_countries": ARRAY,
    "ext_us_state_restrictions": ARRAY,
}


# Pass 2 - Inference fields (nested paths)
PASS2_FIELDS: Dict[str, Tuple[str, str]] = {
    # seniority_and_role
    "seniority_and_role.seniority_level": ("seniority_and_role", "seniority_level"),
    "seniority_and_role.job_family": ("seniority_and_role", "job_family"),
    "seniority_and_role.sub_specialty": ("seniority_and_role", "sub_specialty"),
    "seniority_and_role.leadership_expectation": ("seniority_and_role", "leadership_expectation"),

    # stack_and_cloud
    "stack_and_cloud.primary_cloud": ("stack_and_cloud", "primary_cloud"),
    "stack_and_cloud.secondary_clouds": ("stack_and_cloud", "secondary_clouds"),
    "stack_and_cloud.processing_paradigm": ("stack_and_cloud", "processing_paradigm"),
    "stack_and_cloud.orchestrator_category": ("stack_and_cloud", "orchestrator_category"),
    "stack_and_cloud.storage_layer": ("stack_and_cloud", "storage_layer"),

    # geo_and_work_model
    "geo_and_work_model.remote_restriction": ("geo_and_work_model", "remote_restriction"),
    "geo_and_work_model.timezone_focus": ("geo_and_work_model", "timezone_focus"),
    "geo_and_work_model.relocation_required": ("geo_and_work_model", "relocation_required"),

    # visa_and_authorization
    "visa_and_authorization.h1b_friendly": ("visa_and_authorization", "h1b_friendly"),
    "visa_and_authorization.opt_cpt_friendly": ("visa_and_authorization", "opt_cpt_friendly"),
    "visa_and_authorization.citizenship_required": ("visa_and_authorization", "citizenship_required"),

    # contract_and_compensation
    "contract_and_compensation.w2_vs_1099": ("contract_and_compensation", "w2_vs_1099"),
    "contract_and_compensation.benefits_level": ("contract_and_compensation", "benefits_level"),

    # career_development
    "career_development.growth_path_clarity": ("career_development", "growth_path_clarity"),
    "career_development.mentorship_signals": ("career_development", "mentorship_signals"),
    "career_development.promotion_path_mentioned": ("career_development", "promotion_path_mentioned"),
    "career_development.internal_mobility_mentioned": ("career_development", "internal_mobility_mentioned"),
    "career_development.career_tracks_available": ("career_development", "career_tracks_available"),

    # requirements_classification
    "requirements_classification.requirement_strictness": ("requirements_classification", "requirement_strictness"),
    "requirements_classification.scope_definition": ("requirements_classification", "scope_definition"),
    "requirements_classification.skill_inflation_detected": ("requirements_classification", "skill_inflation_detected"),
}


# Pass 3 - Analysis fields (nested paths)
PASS3_FIELDS: Dict[str, Tuple[str, str]] = {
    # company_maturity
    "company_maturity.data_maturity_score": ("company_maturity", "data_maturity_score"),
    "company_maturity.data_maturity_level": ("company_maturity", "data_maturity_level"),
    "company_maturity.maturity_signals": ("company_maturity", "maturity_signals"),

    # red_flags_and_role_quality
    "red_flags_and_role_quality.scope_creep_score": ("red_flags_and_role_quality", "scope_creep_score"),
    "red_flags_and_role_quality.overtime_risk_score": ("red_flags_and_role_quality", "overtime_risk_score"),
    "red_flags_and_role_quality.role_clarity": ("red_flags_and_role_quality", "role_clarity"),
    "red_flags_and_role_quality.overall_red_flag_score": ("red_flags_and_role_quality", "overall_red_flag_score"),

    # stakeholders_and_leadership
    "stakeholders_and_leadership.reporting_structure_clarity": ("stakeholders_and_leadership", "reporting_structure_clarity"),
    "stakeholders_and_leadership.manager_level_inferred": ("stakeholders_and_leadership", "manager_level_inferred"),
    "stakeholders_and_leadership.team_growth_velocity": ("stakeholders_and_leadership", "team_growth_velocity"),
    "stakeholders_and_leadership.reporting_structure": ("stakeholders_and_leadership", "reporting_structure"),
    "stakeholders_and_leadership.cross_functional_embedded": ("stakeholders_and_leadership", "cross_functional_embedded"),

    # tech_culture
    "tech_culture.work_life_balance_score": ("tech_culture", "work_life_balance_score"),
    "tech_culture.growth_opportunities_score": ("tech_culture", "growth_opportunities_score"),
    "tech_culture.tech_culture_score": ("tech_culture", "tech_culture_score"),

    # tech_culture_assessment
    "tech_culture_assessment.tech_culture_signals": ("tech_culture_assessment", "tech_culture_signals"),
    "tech_culture_assessment.dev_practices_mentioned": ("tech_culture_assessment", "dev_practices_mentioned"),
    "tech_culture_assessment.innovation_signals": ("tech_culture_assessment", "innovation_signals"),
    "tech_culture_assessment.tech_debt_awareness": ("tech_culture_assessment", "tech_debt_awareness"),

    # ai_ml_integration
    "ai_ml_integration.ai_integration_level": ("ai_ml_integration", "ai_integration_level"),
    "ai_ml_integration.ml_tools_expected": ("ai_ml_integration", "ml_tools_expected"),

    # competition_and_timing
    "competition_and_timing.hiring_urgency": ("competition_and_timing", "hiring_urgency"),
    "competition_and_timing.competition_level": ("competition_and_timing", "competition_level"),

    # company_context
    "company_context.company_stage_inferred": ("company_context", "company_stage_inferred"),
    "company_context.hiring_velocity": ("company_context", "hiring_velocity"),
    "company_context.team_size_signals": ("company_context", "team_size_signals"),
    "company_context.funding_stage_signals": ("company_context", "funding_stage_signals"),
    "company_context.role_creation_type": ("company_context", "role_creation_type"),
}

# Summary fields from Pass 3 (not inference objects)
PASS3_SUMMARY_FIELDS: Dict[str, str] = {
    "summary.strengths": ARRAY,
    "summary.concerns": ARRAY,
    "summary.best_fit_for": ARRAY,
    "summary.red_flags_to_probe": ARRAY,
    "summary.negotiation_leverage": ARRAY,
    "summary.overall_assessment": STRING,
    "summary.recommendation_score": NUMERIC,
    "summary.recommendation_confidence": NUMERIC,
}


def get_field_type(field_name: str) -> str:
    """Get the type of a field by name."""
    if field_name in PASS1_FIELDS:
        return PASS1_FIELDS[field_name]
    if field_name in PASS2_FIELDS:
        return INFERENCE
    if field_name in PASS3_FIELDS:
        return INFERENCE
    if field_name in PASS3_SUMMARY_FIELDS:
        return PASS3_SUMMARY_FIELDS[field_name]
    return STRING  # Default to string


def get_all_pass1_fields() -> List[str]:
    """Get all Pass 1 field names."""
    return list(PASS1_FIELDS.keys())


def get_all_pass2_fields() -> List[str]:
    """Get all Pass 2 field paths."""
    return list(PASS2_FIELDS.keys())


def get_all_pass3_fields() -> List[str]:
    """Get all Pass 3 field paths."""
    return list(PASS3_FIELDS.keys()) + list(PASS3_SUMMARY_FIELDS.keys())
