"""
Data loading utilities for model outputs.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

# Model file mappings
MODEL_FILES = {
    "gpt-oss": "openai-gpt-oss-120b-1-0",
    "mistral": "mistral-mistral-large-3-675b-instruct",
    "gemma": "google-gemma-3-27b-it",
    "minimax": "minimax-minimax-m2",
    "qwen": "qwen-qwen3-vl-235b-a22b",
}

MODEL_NAMES = {
    "gpt-oss": "OpenAI GPT-OSS 120B",
    "mistral": "Mistral Large 675B",
    "gemma": "Google Gemma 3 27B",
    "minimax": "MiniMax M2",
    "qwen": "Qwen3 235B",
}


def load_model_outputs(
    job_id: str,
    pass_num: int,
    base_path: str = "data/local"
) -> Dict[str, Dict[str, Any]]:
    """
    Load outputs from all models for a specific pass.

    Args:
        job_id: Job posting ID
        pass_num: Pass number (1, 2, or 3)
        base_path: Base path for data files

    Returns:
        Dict mapping model_short_name -> parsed JSON
    """
    job_dir = Path(base_path) / job_id
    outputs = {}

    for model_name, file_suffix in MODEL_FILES.items():
        filename = f"pass{pass_num}-{file_suffix}.json"
        filepath = job_dir / filename

        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                outputs[model_name] = json.load(f)

    return outputs


def load_all_passes(
    job_id: str,
    base_path: str = "data/local"
) -> Dict[int, Dict[str, Dict[str, Any]]]:
    """
    Load outputs from all models for all passes.

    Returns:
        Dict mapping pass_num -> model_name -> parsed JSON
    """
    return {
        1: load_model_outputs(job_id, 1, base_path),
        2: load_model_outputs(job_id, 2, base_path),
        3: load_model_outputs(job_id, 3, base_path),
    }


def get_job_metadata(outputs: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """
    Extract job metadata from the first available output.
    """
    for model_data in outputs.values():
        metadata = model_data.get("metadata", {})
        if metadata:
            return {
                "job_id": metadata.get("job_posting_id", ""),
                "job_title": metadata.get("job_title", ""),
                "company_name": metadata.get("company_name", ""),
                "job_location": metadata.get("job_location", ""),
            }
    return {}


def extract_pass1_field(
    outputs: Dict[str, Dict[str, Any]],
    field_name: str
) -> Dict[str, Any]:
    """
    Extract a specific field from Pass 1 outputs.
    """
    values = {}
    for model, data in outputs.items():
        result = data.get("result", {})
        values[model] = result.get(field_name)
    return values


def extract_pass2_field(
    outputs: Dict[str, Dict[str, Any]],
    group: str,
    field: str
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Extract a specific inference field from Pass 2 outputs.

    Returns dict mapping model -> inference object (with value, confidence, etc.)
    """
    inference_objects = {}
    for model, data in outputs.items():
        result = data.get("result", {})
        inference = result.get("inference", {})
        group_data = inference.get(group, {})
        field_data = group_data.get(field)

        if field_data and isinstance(field_data, dict) and "value" in field_data:
            inference_objects[model] = field_data
        else:
            inference_objects[model] = None

    return inference_objects


def extract_pass3_field(
    outputs: Dict[str, Dict[str, Any]],
    group: str,
    field: str
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Extract a specific analysis field from Pass 3 outputs.
    """
    inference_objects = {}
    for model, data in outputs.items():
        result = data.get("result", {})
        analysis = result.get("analysis", {})
        group_data = analysis.get(group, {})
        field_data = group_data.get(field)

        if field_data and isinstance(field_data, dict) and "value" in field_data:
            inference_objects[model] = field_data
        else:
            inference_objects[model] = None

    return inference_objects


def extract_pass3_summary_field(
    outputs: Dict[str, Dict[str, Any]],
    field: str
) -> Dict[str, Any]:
    """
    Extract a specific summary field from Pass 3 outputs.
    """
    values = {}
    for model, data in outputs.items():
        result = data.get("result", {})
        summary = result.get("summary", {})
        values[model] = summary.get(field)
    return values
