"""
Normalization and edge case handling for model outputs.
"""

from typing import Any, Dict, List, Optional


# Semantic equivalences for categorical values
VALUE_EQUIVALENCES: Dict[str, str] = {
    # Cloud providers
    "amazon web services": "aws",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
    "microsoft azure": "azure",
    # Work models
    "work from home": "remote",
    "wfh": "remote",
    "in-office": "onsite",
    "on-site": "onsite",
    "in office": "onsite",
    # Employment types
    "full time": "full_time",
    "full-time": "full_time",
    "part time": "part_time",
    "part-time": "part_time",
}

# Skill synonyms for normalization
SKILL_SYNONYMS: Dict[str, str] = {
    "apache spark": "spark",
    "apache kafka": "kafka",
    "apache airflow": "airflow",
    "amazon s3": "s3",
    "amazon redshift": "redshift",
    "google bigquery": "bigquery",
    "postgresql": "postgres",
    "javascript": "js",
    "typescript": "ts",
    "etl/elt": "etl",
    "infrastructure-as-code": "iac",
    "infrastructure-as-code tools": "iac",
    "datalake technologies": "data lake",
    "data orchestration tools": "orchestration",
    "data streaming platforms": "streaming",
}


def normalize_value(value: Optional[str]) -> Optional[str]:
    """Normalize a categorical value using equivalence mappings."""
    if value is None:
        return None
    lower = value.lower().strip()
    return VALUE_EQUIVALENCES.get(lower, lower)


def normalize_skill(skill: str) -> str:
    """Normalize a skill name using synonym mappings."""
    lower = skill.lower().strip()
    return SKILL_SYNONYMS.get(lower, lower)


def normalize_skill_list(skills: Optional[List[str]]) -> List[str]:
    """Normalize a list of skills."""
    if not skills:
        return []
    return sorted(set(normalize_skill(s) for s in skills if s))


def coerce_to_boolean(value: Any) -> Optional[bool]:
    """Attempt to coerce a value to boolean."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "yes", "1")
    return bool(value)


def coerce_to_numeric(value: Any) -> Optional[float]:
    """Attempt to coerce a value to float.

    Handles edge case where LLM returns inference object instead of raw number:
    e.g., {"value": 0.55, "confidence": 0.8} -> 0.55
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            cleaned = value.replace(",", "").replace("$", "").strip()
            return float(cleaned)
        except ValueError:
            return None
    # Handle inference object returned where plain number expected
    if isinstance(value, dict) and "value" in value:
        return coerce_to_numeric(value["value"])
    return None


def coerce_to_array(value: Any) -> List[str]:
    """Attempt to coerce a value to array.

    Handles edge case where LLM returns inference object instead of raw array:
    e.g., {"value": ["a", "b"], "confidence": 0.8} -> ["a", "b"]
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if isinstance(value, str):
        return [s.strip() for s in value.split(",") if s.strip()]
    # Handle inference object returned where plain array expected
    if isinstance(value, dict) and "value" in value:
        return coerce_to_array(value["value"])
    return [str(value)]


def handle_null_values(
    values: Dict[str, Any],
    field_type: str
) -> Dict[str, Any]:
    """
    Handle null values according to field type.

    Returns dict with:
        - consensus: value if majority null
        - values: filtered non-null values
        - null_models: list of models with null values
        - reason: why consensus is null (if applicable)
    """
    non_null = {k: v for k, v in values.items() if v is not None}
    null_models = [k for k in values if values[k] is None]
    null_count = len(null_models)

    # All null - consensus is null
    if not non_null:
        return {
            "consensus": None,
            "reason": "all_null",
            "values": {},
            "null_models": null_models,
            "valid": True
        }

    # Majority null - consensus is null
    if null_count > len(non_null):
        return {
            "consensus": None,
            "reason": "majority_null",
            "values": non_null,
            "null_models": null_models,
            "valid": True
        }

    # Minority null - proceed with non-null
    return {
        "consensus": None,
        "reason": None,
        "values": non_null,
        "null_models": null_models,
        "valid": False  # Needs further processing
    }


def normalize_model_values(
    values: Dict[str, Any],
    field_type: str
) -> Dict[str, Any]:
    """
    Normalize values based on field type.
    """
    result = {}

    for model, value in values.items():
        if value is None:
            result[model] = None
            continue

        if field_type == "boolean":
            result[model] = coerce_to_boolean(value)
        elif field_type == "numeric":
            result[model] = coerce_to_numeric(value)
        elif field_type == "enum":
            result[model] = normalize_value(value) if isinstance(value, str) else value
        elif field_type == "array":
            if isinstance(value, list):
                result[model] = normalize_skill_list(value)
            else:
                result[model] = coerce_to_array(value)
        else:
            result[model] = value

    return result
