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
    result["ext_equity_mentioned"] = _get_bool(comp, "equity_mentioned")

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
    result["ext_contract_duration_stated"] = _get_string(wm, "contract_duration_stated")

    # Requirements
    req = extraction.get("requirements", {}) or {}
    result["ext_skills_mentioned"] = _get_array(req, "skills_mentioned")
    result["ext_certifications_mentioned"] = _get_array(req, "certifications_mentioned")
    result["ext_years_experience_min"] = _get_number(req, "years_experience_min")
    result["ext_years_experience_max"] = _get_number(req, "years_experience_max")
    result["ext_years_experience_text"] = _get_string(req, "years_experience_text")
    result["ext_education_stated"] = _get_string(req, "education_stated")

    # Benefits
    benefits = extraction.get("benefits", {}) or {}
    result["ext_benefits_mentioned"] = _get_array(benefits, "benefits_mentioned")

    # Context
    ctx = extraction.get("context", {}) or {}
    result["ext_team_info_text"] = _get_string(ctx, "team_info_text")
    result["ext_company_description_text"] = _get_string(ctx, "company_description_text")

    return result


def _get_empty_extraction_columns() -> Dict[str, Any]:
    """Return dict with all ext_* columns set to None."""
    return {
        "ext_salary_disclosed": None,
        "ext_salary_min": None,
        "ext_salary_max": None,
        "ext_salary_currency": None,
        "ext_salary_period": None,
        "ext_salary_text_raw": None,
        "ext_hourly_rate_min": None,
        "ext_hourly_rate_max": None,
        "ext_equity_mentioned": None,
        "ext_visa_sponsorship_stated": None,
        "ext_work_auth_text": None,
        "ext_citizenship_text": None,
        "ext_security_clearance_stated": None,
        "ext_work_model_stated": None,
        "ext_location_restriction_text": None,
        "ext_employment_type_stated": None,
        "ext_contract_duration_stated": None,
        "ext_skills_mentioned": None,
        "ext_certifications_mentioned": None,
        "ext_years_experience_min": None,
        "ext_years_experience_max": None,
        "ext_years_experience_text": None,
        "ext_education_stated": None,
        "ext_benefits_mentioned": None,
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
