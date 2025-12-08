"""
Flattener for Pass 1 extraction results.
Converts nested JSON to flat ext_* columns.
"""

from typing import Dict, Any, Optional, List


def flatten_extraction(extraction: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Flatten Pass 1 extraction into prefixed columns.

    Args:
        extraction: The "extraction" dict from LLM response

    Returns:
        Dict with flat ext_* columns
    """
    result = {}

    if extraction is None:
        return _get_empty_extraction_columns()

    # Compensation
    comp = extraction.get("compensation", {}) or {}
    result["ext_salary_disclosed"] = _get_bool(comp, "salary_disclosed")
    result["ext_salary_min"] = _get_number(comp, "salary_min")
    result["ext_salary_max"] = _get_number(comp, "salary_max")
    result["ext_salary_currency"] = _get_string(comp, "salary_currency")
    result["ext_salary_period"] = _get_string(comp, "salary_period")
    result["ext_salary_text_raw"] = _get_string(comp, "salary_text_raw")
    result["ext_hourly_rate_min"] = _get_number(comp, "hourly_rate_min")
    result["ext_hourly_rate_max"] = _get_number(comp, "hourly_rate_max")
    result["ext_hourly_rate_currency"] = _get_string(comp, "hourly_rate_currency")
    result["ext_hourly_rate_text_raw"] = _get_string(comp, "hourly_rate_text_raw")

    # Work Authorization
    auth = extraction.get("work_authorization", {}) or {}
    result["ext_visa_sponsorship_stated"] = _get_string(auth, "visa_sponsorship_stated")
    result["ext_work_auth_text"] = _get_string(auth, "work_auth_text")
    result["ext_citizenship_text"] = _get_string(auth, "citizenship_text")
    result["ext_security_clearance_stated"] = _get_string(auth, "security_clearance_stated")

    # Work Model
    wm = extraction.get("work_model", {}) or {}
    result["ext_work_model_stated"] = _get_string(wm, "work_model_stated")
    result["ext_location_restriction_text"] = _get_string(wm, "location_restriction_text")
    result["ext_employment_type_stated"] = _get_string(wm, "employment_type_stated")

    # Contract Details
    cd = extraction.get("contract_details", {}) or {}
    result["ext_contract_type"] = _get_string(cd, "contract_type")
    result["ext_contract_duration_months"] = _get_number(cd, "contract_duration_months")
    result["ext_contract_duration_text"] = _get_string(cd, "contract_duration_text")
    result["ext_extension_possible"] = _get_string(cd, "extension_possible")
    result["ext_conversion_to_fte"] = _get_string(cd, "conversion_to_fte")
    result["ext_start_date"] = _get_string(cd, "start_date")
    result["ext_start_date_text"] = _get_string(cd, "start_date_text")
    result["ext_probation_period_text"] = _get_string(cd, "probation_period_text")

    # Contractor Rates
    cr = extraction.get("contractor_rates", {}) or {}
    result["ext_pay_type"] = _get_string(cr, "pay_type")
    result["ext_daily_rate_min"] = _get_number(cr, "daily_rate_min")
    result["ext_daily_rate_max"] = _get_number(cr, "daily_rate_max")
    result["ext_daily_rate_currency"] = _get_string(cr, "daily_rate_currency")
    result["ext_daily_rate_text_raw"] = _get_string(cr, "daily_rate_text_raw")
    result["ext_rate_negotiable"] = _get_string(cr, "rate_negotiable")
    result["ext_overtime_paid"] = _get_string(cr, "overtime_paid")

    # Skills Classified
    sc = extraction.get("skills_classified", {}) or {}
    result["ext_must_have_hard_skills"] = _get_array(sc, "must_have_hard_skills")
    result["ext_nice_to_have_hard_skills"] = _get_array(sc, "nice_to_have_hard_skills")
    result["ext_must_have_soft_skills"] = _get_array(sc, "must_have_soft_skills")
    result["ext_nice_to_have_soft_skills"] = _get_array(sc, "nice_to_have_soft_skills")
    result["ext_certifications_mentioned"] = _get_array(sc, "certifications_mentioned")
    result["ext_years_experience_min"] = _get_number(sc, "years_experience_min")
    result["ext_years_experience_max"] = _get_number(sc, "years_experience_max")
    result["ext_years_experience_text"] = _get_string(sc, "years_experience_text")
    # Education - new structured fields
    result["ext_education_level"] = _get_string(sc, "education_level")
    result["ext_education_area"] = _get_string(sc, "education_area")
    result["ext_education_requirement"] = _get_string(sc, "education_requirement")
    result["ext_education_text_raw"] = _get_string(sc, "education_text_raw")
    # Legacy field for backward compatibility (deprecated)
    result["ext_education_stated"] = _get_string(sc, "education_stated")
    result["ext_llm_genai_mentioned"] = _get_bool(sc, "llm_genai_mentioned")
    result["ext_feature_store_mentioned"] = _get_bool(sc, "feature_store_mentioned")

    # Geographic Restrictions
    geo = extraction.get("geographic_restrictions", {}) or {}
    result["ext_geo_restriction_type"] = _get_string(geo, "geo_restriction_type")
    result["ext_allowed_countries"] = _get_array(geo, "allowed_countries")
    result["ext_excluded_countries"] = _get_array(geo, "excluded_countries")
    result["ext_us_state_restrictions"] = _get_array(geo, "us_state_restrictions")
    result["ext_residency_requirement"] = _get_string(geo, "residency_requirement")

    # Benefits Structured
    benefits = extraction.get("benefits_structured", {}) or {}
    result["ext_benefits_mentioned"] = _get_array(benefits, "benefits_mentioned")
    result["ext_equity_mentioned"] = _get_bool(benefits, "equity_mentioned")
    result["ext_learning_budget_mentioned"] = _get_bool(benefits, "learning_budget_mentioned")
    result["ext_conference_budget_mentioned"] = _get_bool(benefits, "conference_budget_mentioned")
    result["ext_hardware_choice_mentioned"] = _get_bool(benefits, "hardware_choice_mentioned")
    result["ext_pto_policy"] = _get_string(benefits, "pto_policy")

    # Context
    ctx = extraction.get("context", {}) or {}
    result["ext_team_info_text"] = _get_string(ctx, "team_info_text")
    result["ext_company_description_text"] = _get_string(ctx, "company_description_text")

    return result


def _get_empty_extraction_columns() -> Dict[str, Any]:
    """Return dict with all ext_* columns set to None."""
    return {
        # Compensation
        "ext_salary_disclosed": None,
        "ext_salary_min": None,
        "ext_salary_max": None,
        "ext_salary_currency": None,
        "ext_salary_period": None,
        "ext_salary_text_raw": None,
        "ext_hourly_rate_min": None,
        "ext_hourly_rate_max": None,
        "ext_hourly_rate_currency": None,
        "ext_hourly_rate_text_raw": None,
        # Work Authorization
        "ext_visa_sponsorship_stated": None,
        "ext_work_auth_text": None,
        "ext_citizenship_text": None,
        "ext_security_clearance_stated": None,
        # Work Model
        "ext_work_model_stated": None,
        "ext_location_restriction_text": None,
        "ext_employment_type_stated": None,
        # Contract Details
        "ext_contract_type": None,
        "ext_contract_duration_months": None,
        "ext_contract_duration_text": None,
        "ext_extension_possible": None,
        "ext_conversion_to_fte": None,
        "ext_start_date": None,
        "ext_start_date_text": None,
        "ext_probation_period_text": None,
        # Contractor Rates
        "ext_pay_type": None,
        "ext_daily_rate_min": None,
        "ext_daily_rate_max": None,
        "ext_daily_rate_currency": None,
        "ext_daily_rate_text_raw": None,
        "ext_rate_negotiable": None,
        "ext_overtime_paid": None,
        # Skills Classified
        "ext_must_have_hard_skills": None,
        "ext_nice_to_have_hard_skills": None,
        "ext_must_have_soft_skills": None,
        "ext_nice_to_have_soft_skills": None,
        "ext_certifications_mentioned": None,
        "ext_years_experience_min": None,
        "ext_years_experience_max": None,
        "ext_years_experience_text": None,
        # Education - new structured fields
        "ext_education_level": None,
        "ext_education_area": None,
        "ext_education_requirement": None,
        "ext_education_text_raw": None,
        # Legacy field for backward compatibility (deprecated)
        "ext_education_stated": None,
        "ext_llm_genai_mentioned": None,
        "ext_feature_store_mentioned": None,
        # Geographic Restrictions
        "ext_geo_restriction_type": None,
        "ext_allowed_countries": None,
        "ext_excluded_countries": None,
        "ext_us_state_restrictions": None,
        "ext_residency_requirement": None,
        # Benefits Structured
        "ext_benefits_mentioned": None,
        "ext_equity_mentioned": None,
        "ext_learning_budget_mentioned": None,
        "ext_conference_budget_mentioned": None,
        "ext_hardware_choice_mentioned": None,
        "ext_pto_policy": None,
        # Context
        "ext_team_info_text": None,
        "ext_company_description_text": None,
    }


def _get_bool(obj: Dict, key: str) -> Optional[bool]:
    """Get boolean value, converting if needed."""
    value = obj.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "yes", "1")
    return bool(value)


def _get_number(obj: Dict, key: str) -> Optional[float]:
    """Get numeric value."""
    value = obj.get(key)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            # Remove currency symbols and commas
            cleaned = value.replace(",", "").replace("$", "").replace("€", "").replace("£", "").strip()
            return float(cleaned)
        except ValueError:
            return None
    return None


def _get_string(obj: Dict, key: str) -> Optional[str]:
    """Get string value, converting if needed."""
    value = obj.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() if value.strip() else None
    return str(value)


def _get_array(obj: Dict, key: str) -> Optional[List[str]]:
    """Get array value, ensuring list of strings."""
    value = obj.get(key)
    if value is None:
        return None
    if isinstance(value, list):
        # Filter out None and empty strings, convert to strings
        return [str(v).strip() for v in value if v is not None and str(v).strip()]
    if isinstance(value, str):
        # Handle comma-separated string
        return [s.strip() for s in value.split(",") if s.strip()]
    return None
