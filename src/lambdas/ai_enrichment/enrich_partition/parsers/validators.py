"""
Validators for Pass 1, 2, and 3 responses.
Ensures LLM output matches expected schema.
"""

from typing import Dict, Any, List, Tuple, Optional
import logging

logger = logging.getLogger()


# Valid enum values for Pass 1
VALID_VISA_SPONSORSHIP = {"yes", "no", "not_mentioned"}
VALID_SECURITY_CLEARANCE = {"required", "preferred", "not_mentioned"}
VALID_WORK_MODEL = {"remote", "hybrid", "onsite", "not_mentioned"}
VALID_EMPLOYMENT_TYPE = {"full_time", "contract", "internship", "part_time", "not_mentioned"}
VALID_SALARY_PERIOD = {"yearly", "monthly", "hourly", None}


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

    # Validate requirements section
    req = extraction.get("requirements", {})
    if not isinstance(req, dict):
        errors.append("Invalid requirements section")
    else:
        skills = req.get("skills_mentioned")
        if skills is not None and not isinstance(skills, list):
            errors.append("skills_mentioned must be array or null")

        certs = req.get("certifications_mentioned")
        if certs is not None and not isinstance(certs, list):
            errors.append("certifications_mentioned must be array or null")

        # Validate years_experience fields
        years_min = req.get("years_experience_min")
        if years_min is not None and not isinstance(years_min, (int, float)):
            errors.append("years_experience_min must be number or null")

        years_max = req.get("years_experience_max")
        if years_max is not None and not isinstance(years_max, (int, float)):
            errors.append("years_experience_max must be number or null")

        # Validate min <= max if both provided
        if years_min is not None and years_max is not None:
            if years_min > years_max:
                errors.append(f"years_experience_min ({years_min}) > years_experience_max ({years_max})")

    # Validate benefits section
    benefits = extraction.get("benefits", {})
    if isinstance(benefits, dict):
        mentioned = benefits.get("benefits_mentioned")
        if mentioned is not None and not isinstance(mentioned, list):
            errors.append("benefits_mentioned must be array or null")

    is_valid = len(errors) == 0
    if not is_valid:
        logger.warning(f"Extraction validation failed: {errors}")

    return is_valid, errors


def validate_inference_response(data: Optional[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Validate Pass 2 inference response.
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

    # Check that main sections exist
    expected_sections = [
        "seniority_and_role",
        "stack_and_cloud",
        "geo_and_work_model",
        "visa_and_authorization",
        "contract_and_compensation",
        "requirements_classification",
    ]

    for section in expected_sections:
        if section not in inference:
            errors.append(f"Missing section: {section}")

    # Validate confidence scores are in range
    confidence_errors = _validate_confidence_scores(inference)
    errors.extend(confidence_errors)

    is_valid = len(errors) == 0
    if not is_valid:
        logger.warning(f"Inference validation failed: {errors}")

    return is_valid, errors


def validate_analysis_response(data: Optional[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Validate Pass 3 analysis response.

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

    # Check main sections
    expected_sections = [
        "company_maturity",
        "red_flags_and_role_quality",
        "stakeholders_and_leadership",
        "tech_culture",
        "ai_ml_integration",
        "competition_and_timing",
    ]

    for section in expected_sections:
        if section not in analysis:
            errors.append(f"Missing section: {section}")

    # Check summary section
    summary = data.get("summary")
    if not isinstance(summary, dict):
        errors.append("Missing or invalid 'summary' section")
    else:
        if "recommendation" not in summary:
            errors.append("Missing recommendation in summary")
        if "strengths" not in summary:
            errors.append("Missing strengths in summary")
        if "concerns" not in summary:
            errors.append("Missing concerns in summary")

    # Validate confidence scores
    confidence_errors = _validate_confidence_scores(analysis)
    errors.extend(confidence_errors)

    # Validate score ranges (0-1)
    red_flags = analysis.get("red_flags_and_role_quality", {})
    for score_field in ["scope_creep_score", "workload_risk_score"]:
        field_data = red_flags.get(score_field, {})
        if isinstance(field_data, dict):
            value = field_data.get("value")
            if value is not None and (not isinstance(value, (int, float)) or value < 0 or value > 1):
                errors.append(f"{score_field} value must be between 0 and 1")

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
