"""
Flattener for Pass 2 inference results.
Converts nested JSON with confidence/evidence to flat inf_* columns.
"""

from typing import Dict, Any, Optional, List


def flatten_inference(inference: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Flatten Pass 2 inference into prefixed columns.

    Each field with confidence returns:
    - inf_{field_name}: The value
    - inf_{field_name}_confidence: Confidence score (0.0-1.0)
    - inf_{field_name}_evidence: Evidence string
    - inf_{field_name}_source: Source type

    Args:
        inference: The "inference" dict from LLM response

    Returns:
        Dict with flat inf_* columns
    """
    result = {}

    if inference is None:
        return _get_empty_inference_columns()

    # Seniority and Role
    sr = inference.get("seniority_and_role", {}) or {}
    _add_confidence_field(result, "inf_seniority_level", sr.get("seniority_level"))
    _add_confidence_field(result, "inf_job_family", sr.get("job_family"))
    _add_confidence_field(result, "inf_sub_specialty", sr.get("sub_specialty"))
    _add_confidence_field(result, "inf_leadership_expectation", sr.get("leadership_expectation"))

    # Stack and Cloud
    sc = inference.get("stack_and_cloud", {}) or {}
    _add_confidence_field(result, "inf_primary_cloud", sc.get("primary_cloud"))
    _add_confidence_field(result, "inf_secondary_clouds", sc.get("secondary_clouds"))
    _add_confidence_field(result, "inf_processing_paradigm", sc.get("processing_paradigm"))
    _add_confidence_field(result, "inf_orchestrator_category", sc.get("orchestrator_category"))
    _add_confidence_field(result, "inf_storage_layer", sc.get("storage_layer"))

    # Geo and Work Model
    gwm = inference.get("geo_and_work_model", {}) or {}
    _add_confidence_field(result, "inf_remote_restriction", gwm.get("remote_restriction"))
    _add_confidence_field(result, "inf_timezone_focus", gwm.get("timezone_focus"))
    _add_confidence_field(result, "inf_relocation_required", gwm.get("relocation_required"))

    # Visa and Authorization
    va = inference.get("visa_and_authorization", {}) or {}
    _add_confidence_field(result, "inf_h1b_friendly", va.get("h1b_friendly"))
    _add_confidence_field(result, "inf_opt_cpt_friendly", va.get("opt_cpt_friendly"))
    _add_confidence_field(result, "inf_citizenship_required", va.get("citizenship_required"))

    # Contract and Compensation
    cc = inference.get("contract_and_compensation", {}) or {}
    _add_confidence_field(result, "inf_w2_vs_1099", cc.get("w2_vs_1099"))
    _add_confidence_field(result, "inf_benefits_level", cc.get("benefits_level"))

    # Career Development (v3.3)
    cd = inference.get("career_development", {}) or {}
    _add_confidence_field(result, "inf_growth_path_clarity", cd.get("growth_path_clarity"))
    _add_confidence_field(result, "inf_mentorship_signals", cd.get("mentorship_signals"))
    _add_confidence_field(result, "inf_promotion_path_mentioned", cd.get("promotion_path_mentioned"))
    _add_confidence_field(result, "inf_internal_mobility_mentioned", cd.get("internal_mobility_mentioned"))
    _add_confidence_field(result, "inf_career_tracks_available", cd.get("career_tracks_available"))

    # Requirements Classification
    rc = inference.get("requirements_classification", {}) or {}
    _add_confidence_field(result, "inf_requirement_strictness", rc.get("requirement_strictness"))
    _add_confidence_field(result, "inf_scope_definition", rc.get("scope_definition"))
    _add_confidence_field(result, "inf_skill_inflation_detected", rc.get("skill_inflation_detected"))

    return result


def _get_empty_inference_columns() -> Dict[str, Any]:
    """Return dict with all inf_* columns set to None."""
    return {
        # Seniority and Role
        "inf_seniority_level": None,
        "inf_seniority_level_confidence": None,
        "inf_seniority_level_evidence": None,
        "inf_seniority_level_source": None,
        "inf_job_family": None,
        "inf_job_family_confidence": None,
        "inf_job_family_evidence": None,
        "inf_job_family_source": None,
        "inf_sub_specialty": None,
        "inf_sub_specialty_confidence": None,
        "inf_sub_specialty_evidence": None,
        "inf_sub_specialty_source": None,
        "inf_leadership_expectation": None,
        "inf_leadership_expectation_confidence": None,
        "inf_leadership_expectation_evidence": None,
        "inf_leadership_expectation_source": None,
        # Stack and Cloud
        "inf_primary_cloud": None,
        "inf_primary_cloud_confidence": None,
        "inf_primary_cloud_evidence": None,
        "inf_primary_cloud_source": None,
        "inf_secondary_clouds": None,
        "inf_secondary_clouds_confidence": None,
        "inf_secondary_clouds_evidence": None,
        "inf_secondary_clouds_source": None,
        "inf_processing_paradigm": None,
        "inf_processing_paradigm_confidence": None,
        "inf_processing_paradigm_evidence": None,
        "inf_processing_paradigm_source": None,
        "inf_orchestrator_category": None,
        "inf_orchestrator_category_confidence": None,
        "inf_orchestrator_category_evidence": None,
        "inf_orchestrator_category_source": None,
        "inf_storage_layer": None,
        "inf_storage_layer_confidence": None,
        "inf_storage_layer_evidence": None,
        "inf_storage_layer_source": None,
        # Geo and Work Model
        "inf_remote_restriction": None,
        "inf_remote_restriction_confidence": None,
        "inf_remote_restriction_evidence": None,
        "inf_remote_restriction_source": None,
        "inf_timezone_focus": None,
        "inf_timezone_focus_confidence": None,
        "inf_timezone_focus_evidence": None,
        "inf_timezone_focus_source": None,
        "inf_relocation_required": None,
        "inf_relocation_required_confidence": None,
        "inf_relocation_required_evidence": None,
        "inf_relocation_required_source": None,
        # Visa and Authorization
        "inf_h1b_friendly": None,
        "inf_h1b_friendly_confidence": None,
        "inf_h1b_friendly_evidence": None,
        "inf_h1b_friendly_source": None,
        "inf_opt_cpt_friendly": None,
        "inf_opt_cpt_friendly_confidence": None,
        "inf_opt_cpt_friendly_evidence": None,
        "inf_opt_cpt_friendly_source": None,
        "inf_citizenship_required": None,
        "inf_citizenship_required_confidence": None,
        "inf_citizenship_required_evidence": None,
        "inf_citizenship_required_source": None,
        # Contract and Compensation
        "inf_w2_vs_1099": None,
        "inf_w2_vs_1099_confidence": None,
        "inf_w2_vs_1099_evidence": None,
        "inf_w2_vs_1099_source": None,
        "inf_benefits_level": None,
        "inf_benefits_level_confidence": None,
        "inf_benefits_level_evidence": None,
        "inf_benefits_level_source": None,
        # Career Development (v3.3)
        "inf_growth_path_clarity": None,
        "inf_growth_path_clarity_confidence": None,
        "inf_growth_path_clarity_evidence": None,
        "inf_growth_path_clarity_source": None,
        "inf_mentorship_signals": None,
        "inf_mentorship_signals_confidence": None,
        "inf_mentorship_signals_evidence": None,
        "inf_mentorship_signals_source": None,
        "inf_promotion_path_mentioned": None,
        "inf_promotion_path_mentioned_confidence": None,
        "inf_promotion_path_mentioned_evidence": None,
        "inf_promotion_path_mentioned_source": None,
        "inf_internal_mobility_mentioned": None,
        "inf_internal_mobility_mentioned_confidence": None,
        "inf_internal_mobility_mentioned_evidence": None,
        "inf_internal_mobility_mentioned_source": None,
        "inf_career_tracks_available": None,
        "inf_career_tracks_available_confidence": None,
        "inf_career_tracks_available_evidence": None,
        "inf_career_tracks_available_source": None,
        # Requirements Classification
        "inf_requirement_strictness": None,
        "inf_requirement_strictness_confidence": None,
        "inf_requirement_strictness_evidence": None,
        "inf_requirement_strictness_source": None,
        "inf_scope_definition": None,
        "inf_scope_definition_confidence": None,
        "inf_scope_definition_evidence": None,
        "inf_scope_definition_source": None,
        "inf_skill_inflation_detected": None,
        "inf_skill_inflation_detected_confidence": None,
        "inf_skill_inflation_detected_evidence": None,
        "inf_skill_inflation_detected_source": None,
    }


def _add_confidence_field(result: Dict[str, Any], field_name: str, field_data: Optional[Dict[str, Any]]) -> None:
    """
    Add a field with confidence/evidence/source to result dict.

    Args:
        result: Result dict to update
        field_name: Base field name (e.g., "inf_seniority_level")
        field_data: Dict with {value, confidence, evidence, source}
    """
    if field_data is None or not isinstance(field_data, dict):
        result[field_name] = None
        result[f"{field_name}_confidence"] = None
        result[f"{field_name}_evidence"] = None
        result[f"{field_name}_source"] = None
        return

    # Extract value (handle different types)
    value = field_data.get("value")
    if isinstance(value, list):
        # For arrays, convert to list of strings
        result[field_name] = [str(v).strip() for v in value if v is not None and str(v).strip()]
    elif isinstance(value, dict):
        # For nested objects (like team_composition), keep as dict
        result[field_name] = value
    elif isinstance(value, bool):
        result[field_name] = value
    elif isinstance(value, (int, float)):
        result[field_name] = value
    elif isinstance(value, str):
        result[field_name] = value.strip() if value.strip() else None
    else:
        result[field_name] = value

    # Extract metadata
    result[f"{field_name}_confidence"] = _get_confidence(field_data)
    result[f"{field_name}_evidence"] = _get_string_value(field_data, "evidence")
    result[f"{field_name}_source"] = _get_string_value(field_data, "source")


def _get_confidence(field_data: Dict[str, Any]) -> Optional[float]:
    """Extract confidence score."""
    conf = field_data.get("confidence")
    if conf is None:
        return None
    if isinstance(conf, (int, float)):
        return float(conf)
    if isinstance(conf, str):
        try:
            return float(conf)
        except ValueError:
            return None
    return None


def _get_string_value(field_data: Dict[str, Any], key: str) -> Optional[str]:
    """Extract string value."""
    value = field_data.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() if value.strip() else None
    return str(value)
