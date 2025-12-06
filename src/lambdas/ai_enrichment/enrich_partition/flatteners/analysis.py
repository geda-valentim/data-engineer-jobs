"""
Flattener for Pass 3 analysis results.
Converts nested JSON with confidence/evidence to flat anl_* columns.
"""

from typing import Dict, Any, Optional


def flatten_analysis(analysis: Optional[Dict[str, Any]], summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Flatten Pass 3 analysis into prefixed columns.

    Each field with confidence returns:
    - anl_{field_name}: The value
    - anl_{field_name}_confidence: Confidence score (0.0-1.0)
    - anl_{field_name}_evidence: Evidence string
    - anl_{field_name}_source: Source type

    Args:
        analysis: The "analysis" dict from LLM response
        summary: The "summary" dict from LLM response (optional)

    Returns:
        Dict with flat anl_* columns
    """
    result = {}

    if analysis is None:
        return _get_empty_analysis_columns()

    # Company Maturity (3 fields)
    cm = analysis.get("company_maturity", {}) or {}
    _add_confidence_field(result, "anl_data_maturity_score", cm.get("data_maturity_score"))
    _add_confidence_field(result, "anl_data_maturity_level", cm.get("data_maturity_level"))
    _add_confidence_field(result, "anl_maturity_signals", cm.get("maturity_signals"))

    # Red Flags and Role Quality (4 fields)
    rf = analysis.get("red_flags_and_role_quality", {}) or {}
    _add_confidence_field(result, "anl_scope_creep_score", rf.get("scope_creep_score"))
    _add_confidence_field(result, "anl_overtime_risk_score", rf.get("overtime_risk_score"))
    _add_confidence_field(result, "anl_role_clarity", rf.get("role_clarity"))
    _add_confidence_field(result, "anl_overall_red_flag_score", rf.get("overall_red_flag_score"))

    # Stakeholders and Leadership (6 fields)
    sal = analysis.get("stakeholders_and_leadership", {}) or {}
    _add_confidence_field(result, "anl_reporting_structure_clarity", sal.get("reporting_structure_clarity"))
    _add_confidence_field(result, "anl_manager_level_inferred", sal.get("manager_level_inferred"))
    _add_confidence_field(result, "anl_team_growth_velocity", sal.get("team_growth_velocity"))
    _add_confidence_field(result, "anl_team_composition", sal.get("team_composition"))
    _add_confidence_field(result, "anl_reporting_structure", sal.get("reporting_structure"))
    _add_confidence_field(result, "anl_cross_functional_embedded", sal.get("cross_functional_embedded"))

    # Tech Culture (3 fields)
    tc = analysis.get("tech_culture", {}) or {}
    _add_confidence_field(result, "anl_work_life_balance_score", tc.get("work_life_balance_score"))
    _add_confidence_field(result, "anl_growth_opportunities_score", tc.get("growth_opportunities_score"))
    _add_confidence_field(result, "anl_tech_culture_score", tc.get("tech_culture_score"))

    # Tech Culture Assessment (v3.3) (4 fields)
    tca = analysis.get("tech_culture_assessment", {}) or {}
    _add_confidence_field(result, "anl_tech_culture_signals", tca.get("tech_culture_signals"))
    _add_confidence_field(result, "anl_dev_practices_mentioned", tca.get("dev_practices_mentioned"))
    _add_confidence_field(result, "anl_innovation_signals", tca.get("innovation_signals"))
    _add_confidence_field(result, "anl_tech_debt_awareness", tca.get("tech_debt_awareness"))

    # AI/ML Integration (2 fields)
    ai = analysis.get("ai_ml_integration", {}) or {}
    _add_confidence_field(result, "anl_ai_integration_level", ai.get("ai_integration_level"))
    _add_confidence_field(result, "anl_ml_tools_expected", ai.get("ml_tools_expected"))

    # Competition and Timing (2 fields)
    ct = analysis.get("competition_and_timing", {}) or {}
    _add_confidence_field(result, "anl_hiring_urgency", ct.get("hiring_urgency"))
    _add_confidence_field(result, "anl_competition_level", ct.get("competition_level"))

    # Company Context (v3.3) (5 fields)
    cc = analysis.get("company_context", {}) or {}
    _add_confidence_field(result, "anl_company_stage_inferred", cc.get("company_stage_inferred"))
    _add_confidence_field(result, "anl_hiring_velocity", cc.get("hiring_velocity"))
    _add_confidence_field(result, "anl_team_size_signals", cc.get("team_size_signals"))
    _add_confidence_field(result, "anl_funding_stage_signals", cc.get("funding_stage_signals"))
    _add_confidence_field(result, "anl_role_creation_type", cc.get("role_creation_type"))

    # Summary (7 fields - no confidence scores, plain values)
    if summary and isinstance(summary, dict):
        result["anl_strengths"] = summary.get("strengths")
        result["anl_concerns"] = summary.get("concerns")
        result["anl_best_fit_for"] = summary.get("best_fit_for")
        result["anl_red_flags_to_probe"] = summary.get("red_flags_to_probe")
        result["anl_negotiation_leverage"] = summary.get("negotiation_leverage")
        result["anl_overall_assessment"] = summary.get("overall_assessment")
        result["anl_recommendation_score"] = summary.get("recommendation_score")
        result["anl_recommendation_confidence"] = summary.get("recommendation_confidence")

    return result


def _get_empty_analysis_columns() -> Dict[str, Any]:
    """Return dict with all anl_* columns set to None."""
    return {
        # Company Maturity
        "anl_data_maturity_score": None,
        "anl_data_maturity_score_confidence": None,
        "anl_data_maturity_score_evidence": None,
        "anl_data_maturity_score_source": None,
        "anl_data_maturity_level": None,
        "anl_data_maturity_level_confidence": None,
        "anl_data_maturity_level_evidence": None,
        "anl_data_maturity_level_source": None,
        "anl_maturity_signals": None,
        "anl_maturity_signals_confidence": None,
        "anl_maturity_signals_evidence": None,
        "anl_maturity_signals_source": None,
        # Red Flags and Role Quality
        "anl_scope_creep_score": None,
        "anl_scope_creep_score_confidence": None,
        "anl_scope_creep_score_evidence": None,
        "anl_scope_creep_score_source": None,
        "anl_overtime_risk_score": None,
        "anl_overtime_risk_score_confidence": None,
        "anl_overtime_risk_score_evidence": None,
        "anl_overtime_risk_score_source": None,
        "anl_role_clarity": None,
        "anl_role_clarity_confidence": None,
        "anl_role_clarity_evidence": None,
        "anl_role_clarity_source": None,
        "anl_overall_red_flag_score": None,
        "anl_overall_red_flag_score_confidence": None,
        "anl_overall_red_flag_score_evidence": None,
        "anl_overall_red_flag_score_source": None,
        # Stakeholders and Leadership
        "anl_reporting_structure_clarity": None,
        "anl_reporting_structure_clarity_confidence": None,
        "anl_reporting_structure_clarity_evidence": None,
        "anl_reporting_structure_clarity_source": None,
        "anl_manager_level_inferred": None,
        "anl_manager_level_inferred_confidence": None,
        "anl_manager_level_inferred_evidence": None,
        "anl_manager_level_inferred_source": None,
        "anl_team_growth_velocity": None,
        "anl_team_growth_velocity_confidence": None,
        "anl_team_growth_velocity_evidence": None,
        "anl_team_growth_velocity_source": None,
        "anl_team_composition": None,
        "anl_team_composition_confidence": None,
        "anl_team_composition_evidence": None,
        "anl_team_composition_source": None,
        "anl_reporting_structure": None,
        "anl_reporting_structure_confidence": None,
        "anl_reporting_structure_evidence": None,
        "anl_reporting_structure_source": None,
        "anl_cross_functional_embedded": None,
        "anl_cross_functional_embedded_confidence": None,
        "anl_cross_functional_embedded_evidence": None,
        "anl_cross_functional_embedded_source": None,
        # Tech Culture
        "anl_work_life_balance_score": None,
        "anl_work_life_balance_score_confidence": None,
        "anl_work_life_balance_score_evidence": None,
        "anl_work_life_balance_score_source": None,
        "anl_growth_opportunities_score": None,
        "anl_growth_opportunities_score_confidence": None,
        "anl_growth_opportunities_score_evidence": None,
        "anl_growth_opportunities_score_source": None,
        "anl_tech_culture_score": None,
        "anl_tech_culture_score_confidence": None,
        "anl_tech_culture_score_evidence": None,
        "anl_tech_culture_score_source": None,
        # Tech Culture Assessment (v3.3)
        "anl_tech_culture_signals": None,
        "anl_tech_culture_signals_confidence": None,
        "anl_tech_culture_signals_evidence": None,
        "anl_tech_culture_signals_source": None,
        "anl_dev_practices_mentioned": None,
        "anl_dev_practices_mentioned_confidence": None,
        "anl_dev_practices_mentioned_evidence": None,
        "anl_dev_practices_mentioned_source": None,
        "anl_innovation_signals": None,
        "anl_innovation_signals_confidence": None,
        "anl_innovation_signals_evidence": None,
        "anl_innovation_signals_source": None,
        "anl_tech_debt_awareness": None,
        "anl_tech_debt_awareness_confidence": None,
        "anl_tech_debt_awareness_evidence": None,
        "anl_tech_debt_awareness_source": None,
        # AI/ML Integration
        "anl_ai_integration_level": None,
        "anl_ai_integration_level_confidence": None,
        "anl_ai_integration_level_evidence": None,
        "anl_ai_integration_level_source": None,
        "anl_ml_tools_expected": None,
        "anl_ml_tools_expected_confidence": None,
        "anl_ml_tools_expected_evidence": None,
        "anl_ml_tools_expected_source": None,
        # Competition and Timing
        "anl_hiring_urgency": None,
        "anl_hiring_urgency_confidence": None,
        "anl_hiring_urgency_evidence": None,
        "anl_hiring_urgency_source": None,
        "anl_competition_level": None,
        "anl_competition_level_confidence": None,
        "anl_competition_level_evidence": None,
        "anl_competition_level_source": None,
        # Company Context (v3.3)
        "anl_company_stage_inferred": None,
        "anl_company_stage_inferred_confidence": None,
        "anl_company_stage_inferred_evidence": None,
        "anl_company_stage_inferred_source": None,
        "anl_hiring_velocity": None,
        "anl_hiring_velocity_confidence": None,
        "anl_hiring_velocity_evidence": None,
        "anl_hiring_velocity_source": None,
        "anl_team_size_signals": None,
        "anl_team_size_signals_confidence": None,
        "anl_team_size_signals_evidence": None,
        "anl_team_size_signals_source": None,
        "anl_funding_stage_signals": None,
        "anl_funding_stage_signals_confidence": None,
        "anl_funding_stage_signals_evidence": None,
        "anl_funding_stage_signals_source": None,
        "anl_role_creation_type": None,
        "anl_role_creation_type_confidence": None,
        "anl_role_creation_type_evidence": None,
        "anl_role_creation_type_source": None,
        # Summary (no confidence/evidence)
        "anl_strengths": None,
        "anl_concerns": None,
        "anl_best_fit_for": None,
        "anl_red_flags_to_probe": None,
        "anl_negotiation_leverage": None,
        "anl_overall_assessment": None,
        "anl_recommendation_score": None,
        "anl_recommendation_confidence": None,
    }


def _add_confidence_field(result: Dict[str, Any], field_name: str, field_data: Optional[Dict[str, Any]]) -> None:
    """
    Add a field with confidence/evidence/source to result dict.

    Args:
        result: Result dict to update
        field_name: Base field name (e.g., "anl_tech_culture_signals")
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
