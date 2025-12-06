"""
JSON Parser for LLM responses.
Handles malformed JSON, markdown code blocks, and partial responses.
"""

import json
import re
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger()


def parse_llm_json(response_text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Parse JSON from LLM response with fallback strategies.

    Handles:
    - Clean JSON
    - JSON wrapped in markdown code blocks (```json ... ```)
    - JSON with trailing text
    - Partial/malformed JSON

    Args:
        response_text: Raw LLM response text

    Returns:
        Tuple of (parsed_dict or None, error_message or None)
    """
    if not response_text or not response_text.strip():
        return None, "Empty response"

    text = response_text.strip()

    # Strategy 1: Try direct JSON parse
    result = _try_parse(text)
    if result is not None:
        return result, None

    # Strategy 2: Extract from markdown code blocks
    result = _extract_from_markdown(text)
    if result is not None:
        return result, None

    # Strategy 3: Find JSON object boundaries
    result = _extract_json_object(text)
    if result is not None:
        return result, None

    # Strategy 4: Try to fix common issues
    result = _try_fix_and_parse(text)
    if result is not None:
        return result, None

    return None, f"Failed to parse JSON from response: {text[:200]}..."


def _try_parse(text: str) -> Optional[Dict[str, Any]]:
    """Try direct JSON parse."""
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass
    return None


def _extract_from_markdown(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from markdown code blocks."""
    # Pattern: ```json ... ``` or ``` ... ```
    patterns = [
        r"```json\s*([\s\S]*?)\s*```",
        r"```\s*([\s\S]*?)\s*```",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            result = _try_parse(match.strip())
            if result is not None:
                return result

    return None


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Find and extract JSON object using brace matching."""
    # Find the first '{'
    start = text.find("{")
    if start == -1:
        return None

    # Find matching closing brace
    depth = 0
    in_string = False
    escape_next = False
    end = start

    for i, char in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if depth != 0:
        # Unbalanced braces, try anyway with what we have
        end = len(text)

    json_str = text[start:end]
    return _try_parse(json_str)


def _try_fix_and_parse(text: str) -> Optional[Dict[str, Any]]:
    """Try to fix common JSON issues and parse."""
    # Remove common prefixes LLMs add
    prefixes_to_remove = [
        "Here is the JSON:",
        "Here's the extracted data:",
        "Output:",
        "Result:",
        "JSON:",
    ]

    cleaned = text
    for prefix in prefixes_to_remove:
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip()

    # Try parsing cleaned text
    result = _try_parse(cleaned)
    if result is not None:
        return result

    # Try extracting from cleaned text
    result = _extract_json_object(cleaned)
    if result is not None:
        return result

    # Try fixing trailing commas
    fixed = re.sub(r",\s*([}\]])", r"\1", cleaned)
    result = _try_parse(fixed)
    if result is not None:
        return result

    return None


def safe_get(data: Dict, *keys, default=None) -> Any:
    """
    Safely get nested dictionary value.

    Args:
        data: Dictionary to traverse
        *keys: Keys to follow
        default: Default value if not found

    Returns:
        Value at path or default
    """
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return default
        else:
            return default
    return current if current is not None else default
