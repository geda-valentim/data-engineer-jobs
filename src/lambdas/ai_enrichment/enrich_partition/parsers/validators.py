"""
Validators for Pass 1, 2, and 3 responses.
Ensures LLM output matches expected schema.
"""

from typing import Dict, Any, List, Tuple, Optional
import logging

logger = logging.getLogger()


# Valid enum values for Pass 1
VALID_VISA_SPONSORSHIP = {"will_sponsor", "will_not_sponsor", "must_be_authorized", "not_mentioned"}
VALID_SECURITY_CLEARANCE = {"required", "preferred", "not_mentioned"}
VALID_WORK_MODEL = {"remote", "hybrid", "onsite", "not_mentioned"}
VALID_EMPLOYMENT_TYPE = {"full_time", "contract", "internship", "part_time", "not_mentioned"}
VALID_SALARY_PERIOD = {"yearly", "monthly", "hourly", None}
VALID_CONTRACT_TYPE = {"permanent", "fixed_term", "contract_to_hire", "project_based", "seasonal", "not_mentioned", None}
VALID_EXTENSION_POSSIBLE = {"yes", "likely", "no", "not_mentioned", None}
VALID_CONVERSION_TO_FTE = {"yes_guaranteed", "yes_possible", "no", "not_mentioned", None}
VALID_START_DATE = {"immediate", "within_2_weeks", "within_month", "flexible", "specific_date", "not_mentioned", None}
VALID_PAY_TYPE = {"salary", "hourly", "daily", "weekly", "monthly", "project_fixed", "not_mentioned", None}
VALID_RATE_NEGOTIABLE = {"yes", "doe", "fixed", "not_mentioned", None}
VALID_OVERTIME_PAID = {"yes", "no", "exempt", "not_mentioned", None}
VALID_GEO_RESTRICTION_TYPE = {"us_only", "eu_only", "uk_only", "latam_only", "apac_only", "specific_countries", "global", "not_mentioned", None}
VALID_RESIDENCY_REQUIREMENT = {"must_be_resident", "willing_to_relocate", "no_requirement", "not_mentioned", None}
VALID_PTO_POLICY = {"unlimited", "generous", "standard", "limited", "not_mentioned", None}


def validate_extraction_response(data: Optional[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Validate Pass 1 extraction response.

    Args:
        data: Parsed JSON response

    Returns:
        Tuple of (is_valid, list of errors)
    """
    errors = []

    if data is None:
        return False, ["Response is None"]

    extraction = data.get("extraction")
    if not isinstance(extraction, dict):
        return False, ["Missing or invalid 'extraction' key"]

    # Validate compensation section
    comp = extraction.get("compensation", {})
    if not isinstance(comp, dict):
        errors.append("Invalid compensation section")
    else:
        if "salary_disclosed" in comp and not isinstance(comp["salary_disclosed"], bool):
            errors.append("salary_disclosed must be boolean")
        if comp.get("salary_period") not in VALID_SALARY_PERIOD:
            if comp.get("salary_period") is not None:
                errors.append(f"Invalid salary_period: {comp.get('salary_period')}")

    # Validate work_authorization section
    auth = extraction.get("work_authorization", {})
    if not isinstance(auth, dict):
        errors.append("Invalid work_authorization section")
    else:
        visa = auth.get("visa_sponsorship_stated")
        if visa is not None and visa not in VALID_VISA_SPONSORSHIP:
            errors.append(f"Invalid visa_sponsorship_stated: {visa}")

        clearance = auth.get("security_clearance_stated")
        if clearance is not None and clearance not in VALID_SECURITY_CLEARANCE:
            errors.append(f"Invalid security_clearance_stated: {clearance}")

    # Validate work_model section
    wm = extraction.get("work_model", {})
    if not isinstance(wm, dict):
        errors.append("Invalid work_model section")
    else:
        model = wm.get("work_model_stated")
        if model is not None and model not in VALID_WORK_MODEL:
            errors.append(f"Invalid work_model_stated: {model}")

        emp_type = wm.get("employment_type_stated")
        if emp_type is not None and emp_type not in VALID_EMPLOYMENT_TYPE:
            errors.append(f"Invalid employment_type_stated: {emp_type}")

    # Validate contract_details section
    cd = extraction.get("contract_details", {})
    if isinstance(cd, dict):
        contract_type = cd.get("contract_type")
        if contract_type is not None and contract_type not in VALID_CONTRACT_TYPE:
            errors.append(f"Invalid contract_type: {contract_type}")

        extension = cd.get("extension_possible")
        if extension is not None and extension not in VALID_EXTENSION_POSSIBLE:
            errors.append(f"Invalid extension_possible: {extension}")

        conversion = cd.get("conversion_to_fte")
        if conversion is not None and conversion not in VALID_CONVERSION_TO_FTE:
            errors.append(f"Invalid conversion_to_fte: {conversion}")

        start = cd.get("start_date")
        if start is not None and start not in VALID_START_DATE:
            errors.append(f"Invalid start_date: {start}")

        duration_months = cd.get("contract_duration_months")
        if duration_months is not None and not isinstance(duration_months, (int, float)):
            errors.append("contract_duration_months must be number or null")

    # Validate contractor_rates section
    cr = extraction.get("contractor_rates", {})
    if isinstance(cr, dict):
        pay_type = cr.get("pay_type")
        if pay_type is not None and pay_type not in VALID_PAY_TYPE:
            errors.append(f"Invalid pay_type: {pay_type}")

        negotiable = cr.get("rate_negotiable")
        if negotiable is not None and negotiable not in VALID_RATE_NEGOTIABLE:
            errors.append(f"Invalid rate_negotiable: {negotiable}")

        overtime = cr.get("overtime_paid")
        if overtime is not None and overtime not in VALID_OVERTIME_PAID:
            errors.append(f"Invalid overtime_paid: {overtime}")

    # Validate skills_classified section
    sc = extraction.get("skills_classified", {})
    if not isinstance(sc, dict):
        errors.append("Invalid skills_classified section")
    else:
        for skill_field in ["must_have_hard_skills", "nice_to_have_hard_skills",
                           "must_have_soft_skills", "nice_to_have_soft_skills"]:
            skills = sc.get(skill_field)
            if skills is not None and not isinstance(skills, list):
                errors.append(f"{skill_field} must be array or null")

        certs = sc.get("certifications_mentioned")
        if certs is not None and not isinstance(certs, list):
            errors.append("certifications_mentioned must be array or null")

        # Validate years_experience fields
        years_min = sc.get("years_experience_min")
        if years_min is not None and not isinstance(years_min, (int, float)):
            errors.append("years_experience_min must be number or null")

        years_max = sc.get("years_experience_max")
        if years_max is not None and not isinstance(years_max, (int, float)):
            errors.append("years_experience_max must be number or null")

        # Validate min <= max if both provided
        if years_min is not None and years_max is not None:
            if years_min > years_max:
                errors.append(f"years_experience_min ({years_min}) > years_experience_max ({years_max})")

        # Validate AI/ML detection fields
        llm_genai = sc.get("llm_genai_mentioned")
        if llm_genai is not None and not isinstance(llm_genai, bool):
            errors.append("llm_genai_mentioned must be boolean or null")

        feature_store = sc.get("feature_store_mentioned")
        if feature_store is not None and not isinstance(feature_store, bool):
            errors.append("feature_store_mentioned must be boolean or null")

    # Validate geographic_restrictions section
    geo = extraction.get("geographic_restrictions", {})
    if isinstance(geo, dict):
        geo_type = geo.get("geo_restriction_type")
        if geo_type is not None and geo_type not in VALID_GEO_RESTRICTION_TYPE:
            errors.append(f"Invalid geo_restriction_type: {geo_type}")

        residency = geo.get("residency_requirement")
        if residency is not None and residency not in VALID_RESIDENCY_REQUIREMENT:
            errors.append(f"Invalid residency_requirement: {residency}")

        for country_field in ["allowed_countries", "excluded_countries", "us_state_restrictions"]:
            countries = geo.get(country_field)
            if countries is not None and not isinstance(countries, list):
                errors.append(f"{country_field} must be array or null")

    # Validate benefits_structured section
    benefits = extraction.get("benefits_structured", {})
    if isinstance(benefits, dict):
        mentioned = benefits.get("benefits_mentioned")
        if mentioned is not None and not isinstance(mentioned, list):
            errors.append("benefits_mentioned must be array or null")

        for bool_field in ["equity_mentioned", "learning_budget_mentioned",
                          "conference_budget_mentioned", "hardware_choice_mentioned"]:
            value = benefits.get(bool_field)
            if value is not None and not isinstance(value, bool):
                errors.append(f"{bool_field} must be boolean or null")

        pto = benefits.get("pto_policy")
        if pto is not None and pto not in VALID_PTO_POLICY:
            errors.append(f"Invalid pto_policy: {pto}")

    is_valid = len(errors) == 0
    if not is_valid:
        logger.warning(f"Extraction validation failed: {errors}")

    return is_valid, errors


def validate_inference_response(data: Optional[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Validate Pass 2 inference response (v3.3 schema).
    Checks for proper confidence scores and evidence fields.

    Args:
        data: Parsed JSON response

    Returns:
        Tuple of (is_valid, list of errors)
    """
    errors = []

    if data is None:
        return False, ["Response is None"]

    inference = data.get("inference")
    if not isinstance(inference, dict):
        return False, ["Missing or invalid 'inference' key"]

    # Check that main sections exist (v3.3)
    expected_sections = [
        "seniority_and_role",
        "career_development",
    ]

    for section in expected_sections:
        if section not in inference:
            errors.append(f"Missing section: {section}")

    # Validate seniority_and_role fields
    sr = inference.get("seniority_and_role", {})
    if isinstance(sr, dict):
        for field in ["seniority_level", "job_family", "sub_specialty", "leadership_expectation"]:
            if field not in sr:
                errors.append(f"Missing field in seniority_and_role: {field}")

    # Validate career_development fields (v3.3)
    cd = inference.get("career_development", {})
    if isinstance(cd, dict):
        for field in ["growth_path_clarity", "mentorship_signals", "promotion_path_mentioned",
                     "internal_mobility_mentioned", "career_tracks_available"]:
            if field not in cd:
                errors.append(f"Missing field in career_development: {field}")

    # Validate confidence scores are in range
    confidence_errors = _validate_confidence_scores(inference)
    errors.extend(confidence_errors)

    is_valid = len(errors) == 0
    if not is_valid:
        logger.warning(f"Inference validation failed: {errors}")

    return is_valid, errors


def validate_analysis_response(data: Optional[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Validate Pass 3 analysis response (complete schema).

    Args:
        data: Parsed JSON response

    Returns:
        Tuple of (is_valid, list of errors)
    """
    errors = []

    if data is None:
        return False, ["Response is None"]

    analysis = data.get("analysis")
    if not isinstance(analysis, dict):
        return False, ["Missing or invalid 'analysis' key"]

    # Check all main sections
    expected_sections = [
        "company_maturity",
        "red_flags_and_role_quality",
        "stakeholders_and_leadership",
        "tech_culture",
        "tech_culture_assessment",
        "ai_ml_integration",
        "competition_and_timing",
        "company_context",
    ]

    for section in expected_sections:
        if section not in analysis:
            errors.append(f"Missing section: {section}")

    # Validate company_maturity fields
    cm = analysis.get("company_maturity", {})
    if isinstance(cm, dict):
        for field in ["data_maturity_score", "data_maturity_level", "maturity_signals"]:
            if field not in cm:
                errors.append(f"Missing field in company_maturity: {field}")

    # Validate red_flags_and_role_quality fields
    rf = analysis.get("red_flags_and_role_quality", {})
    if isinstance(rf, dict):
        for field in ["scope_creep_score", "overtime_risk_score", "role_clarity", "overall_red_flag_score"]:
            if field not in rf:
                errors.append(f"Missing field in red_flags_and_role_quality: {field}")

    # Validate stakeholders_and_leadership fields
    sal = analysis.get("stakeholders_and_leadership", {})
    if isinstance(sal, dict):
        for field in ["reporting_structure_clarity", "manager_level_inferred", "team_growth_velocity",
                     "team_composition", "reporting_structure", "cross_functional_embedded"]:
            if field not in sal:
                errors.append(f"Missing field in stakeholders_and_leadership: {field}")

    # Validate tech_culture fields
    tc = analysis.get("tech_culture", {})
    if isinstance(tc, dict):
        for field in ["work_life_balance_score", "growth_opportunities_score", "tech_culture_score"]:
            if field not in tc:
                errors.append(f"Missing field in tech_culture: {field}")

    # Validate tech_culture_assessment fields (v3.3)
    tca = analysis.get("tech_culture_assessment", {})
    if isinstance(tca, dict):
        for field in ["tech_culture_signals", "dev_practices_mentioned", "innovation_signals", "tech_debt_awareness"]:
            if field not in tca:
                errors.append(f"Missing field in tech_culture_assessment: {field}")

    # Validate ai_ml_integration fields
    ai = analysis.get("ai_ml_integration", {})
    if isinstance(ai, dict):
        for field in ["ai_integration_level", "ml_tools_expected"]:
            if field not in ai:
                errors.append(f"Missing field in ai_ml_integration: {field}")

    # Validate competition_and_timing fields
    ct = analysis.get("competition_and_timing", {})
    if isinstance(ct, dict):
        for field in ["hiring_urgency", "competition_level"]:
            if field not in ct:
                errors.append(f"Missing field in competition_and_timing: {field}")

    # Validate company_context fields (v3.3)
    cc = analysis.get("company_context", {})
    if isinstance(cc, dict):
        for field in ["company_stage_inferred", "hiring_velocity", "team_size_signals",
                     "funding_stage_signals", "role_creation_type"]:
            if field not in cc:
                errors.append(f"Missing field in company_context: {field}")

    # Check summary section
    summary = data.get("summary")
    if not isinstance(summary, dict):
        errors.append("Missing or invalid 'summary' section")
    else:
        # v3.4 schema: *_categories + *_details (preferred)
        # v3.3 schema: strengths, concerns, etc. (legacy)
        # Accept either format for backward compatibility

        # Required scalar fields (both versions)
        for field in ["overall_assessment", "recommendation_score"]:
            if field not in summary:
                errors.append(f"Missing field in summary: {field}")

        # Check for v3.4 OR v3.3 format for each array field
        array_field_pairs = [
            ("strength_categories", "strengths"),
            ("concern_categories", "concerns"),
            ("best_fit_categories", "best_fit_for"),
            ("probe_categories", "red_flags_to_probe"),
            ("leverage_categories", "negotiation_leverage"),
        ]

        for new_field, old_field in array_field_pairs:
            has_new = new_field in summary
            has_old = old_field in summary
            if not has_new and not has_old:
                errors.append(f"Missing field in summary: {new_field} or {old_field}")

    # Validate confidence scores
    confidence_errors = _validate_confidence_scores(analysis)
    errors.extend(confidence_errors)

    is_valid = len(errors) == 0
    if not is_valid:
        logger.warning(f"Analysis validation failed: {errors}")

    return is_valid, errors


def _validate_confidence_scores(data: Dict[str, Any], path: str = "") -> List[str]:
    """
    Recursively validate confidence scores are in 0-1 range.

    Args:
        data: Dict to check
        path: Current path for error messages

    Returns:
        List of validation errors
    """
    errors = []

    if not isinstance(data, dict):
        return errors

    for key, value in data.items():
        current_path = f"{path}.{key}" if path else key

        if isinstance(value, dict):
            # Check if this is a field with confidence
            if "confidence" in value:
                conf = value["confidence"]
                if conf is not None:
                    if not isinstance(conf, (int, float)):
                        errors.append(f"{current_path}.confidence must be numeric")
                    elif conf < 0 or conf > 1:
                        errors.append(f"{current_path}.confidence must be between 0 and 1: {conf}")

            # Recurse into nested dicts
            errors.extend(_validate_confidence_scores(value, current_path))

    return errors
