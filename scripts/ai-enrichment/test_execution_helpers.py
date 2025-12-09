"""
Execution and display helpers for AI Enrichment tests.
Contains functions for executing Pass 2/3 and displaying results.
"""

import json
import traceback
from typing import Dict, Any

from enrich_partition.bedrock_client import BedrockClient
from enrich_partition.prompts.pass2_inference import build_pass2_prompt
from enrich_partition.prompts.pass3_complex import build_pass3_prompt
from enrich_partition.parsers.json_parser import parse_llm_json
from enrich_partition.parsers.validators import validate_inference_response, validate_analysis_response


# Model configuration with pricing (per 1M tokens)
AVAILABLE_MODELS = {
    "gpt-oss": {
        "id": "openai.gpt-oss-120b-1:0",
        "name": "OpenAI GPT-OSS 120B",
        "input_cost_per_1m": 0.15,
        "output_cost_per_1m": 0.60,
    },
    "minimax-m2": {
        "id": "minimax.minimax-m2",
        "name": "MiniMax M2",
        "input_cost_per_1m": 0.30,
        "output_cost_per_1m": 1.20,
    },
    "qwen3-235b": {
        "id": "qwen.qwen3-vl-235b-a22b",
        "name": "Qwen3 235B",
        "input_cost_per_1m": 0.22,
        "output_cost_per_1m": 0.88,
    },
    "mistral-large": {
        "id": "mistral.mistral-large-3-675b-instruct",
        "name": "Mistral Large 675B",
        "input_cost_per_1m": 2.00,
        "output_cost_per_1m": 6.00,
    },
    "gemma-27b": {
        "id": "google.gemma-3-27b-it",
        "name": "Gemma 3 27B",
        "input_cost_per_1m": 0.23,
        "output_cost_per_1m": 0.38,
    },
}


def execute_pass2(client: BedrockClient, job: Dict[str, Any], pass1_result: Dict[str, Any]) -> tuple:
    """Execute Pass 2 inference and return results.

    Returns:
        Tuple of (inference_result, total_tokens, input_tokens, output_tokens, cost, raw_response)
    """
    try:
        # Extract Pass 1 results
        pass1_extraction = {k: v for k, v in pass1_result.items() if k.startswith('ext_')}

        # Build Pass 2 prompt
        system_prompt, user_prompt = build_pass2_prompt(
            job_title=job.get('job_title', 'Unknown'),
            company_name=job.get('company_name', 'Unknown'),
            job_location=job.get('job_location', 'Unknown'),
            job_description_text=job.get('job_description_text', ''),
            pass1_extraction=pass1_extraction
        )

        # Call Bedrock
        raw_response, input_tokens, output_tokens, cost = client.invoke(
            prompt=user_prompt,
            system=system_prompt,
            pass_name="pass2",
            max_tokens=4096,
            temperature=0.1
        )
        total_tokens = input_tokens + output_tokens

        # Parse and validate response
        parsed, parse_error = parse_llm_json(raw_response)
        if not parsed:
            print(f"\n  Error parsing Pass 2 response: {parse_error}")
            return None, 0, 0, 0, 0.0, raw_response

        # Validate Pass 2 structure
        is_valid, validation_errors = validate_inference_response(parsed)
        if not is_valid:
            print(f"\n  Warning: Validation errors in Pass 2 response: {validation_errors}")

            # Try to fix flat responses (fields at root instead of under "inference")
            if "Missing or invalid 'inference' key" in str(validation_errors):
                # Check if response has Pass 2 fields at root level
                known_pass2_fields = ['seniority_level', 'job_family', 'sub_specialty', 'primary_cloud']
                has_pass2_fields = any(field in parsed for field in known_pass2_fields)

                if has_pass2_fields:
                    print(f"  → Attempting to fix flat response (wrapping in 'inference' key)")
                    parsed = {'inference': parsed}
                    is_valid = True  # Mark as valid after fix

        # Extract inference section
        inference_result = parsed.get('inference', {})

        return inference_result, total_tokens, input_tokens, output_tokens, cost, raw_response

    except Exception as e:
        print(f"\n  Error in Pass 2: {e}")
        traceback.print_exc()
        return None, 0, 0, 0, 0.0, None


def execute_pass3(client: BedrockClient, job: Dict[str, Any], pass1_result: Dict[str, Any], pass2_result: Dict[str, Any]) -> tuple:
    """Execute Pass 3 analysis and return results.

    Returns:
        Tuple of (analysis_raw, summary_raw, total_tokens, input_tokens, output_tokens, cost, raw_response)
    """
    try:
        # Extract Pass 1 results
        pass1_extraction = {k: v for k, v in pass1_result.items() if k.startswith('ext_')}

        # Build Pass 3 prompt
        system_prompt, user_prompt = build_pass3_prompt(
            job_title=job.get('job_title', 'Unknown'),
            company_name=job.get('company_name', 'Unknown'),
            job_location=job.get('job_location', 'Unknown'),
            job_description_text=job.get('job_description_text', ''),
            pass1_extraction=pass1_extraction,
            pass2_inference=pass2_result
        )

        # Call Bedrock (uses DEFAULT_MAX_TOKENS from BedrockClient for pass3)
        raw_response, input_tokens, output_tokens, cost = client.invoke(
            prompt=user_prompt,
            system=system_prompt,
            pass_name="pass3",
            temperature=0.1
        )
        total_tokens = input_tokens + output_tokens

        # Parse and validate response
        parsed, parse_error = parse_llm_json(raw_response)
        if not parsed:
            print(f"\n  Error parsing Pass 3 response: {parse_error}")
            return None, None, 0, 0, 0, 0.0, raw_response

        # Validate Pass 3 structure
        is_valid, validation_errors = validate_analysis_response(parsed)
        if not is_valid:
            print(f"\n  Warning: Validation errors in Pass 3 response: {validation_errors}")
            # Debug: show what keys are in the parsed response
            print(f"  Debug: parsed keys = {list(parsed.keys()) if parsed else 'None'}")
            if "Missing or invalid 'analysis' key" in str(validation_errors):
                print(f"  Debug: raw_response first 500 chars = {raw_response[:500] if raw_response else 'None'}...")

        # Extract analysis and summary
        analysis_raw = parsed.get('analysis', {})
        summary_raw = parsed.get('summary', {})

        return analysis_raw, summary_raw, total_tokens, input_tokens, output_tokens, cost, raw_response

    except Exception as e:
        print(f"\n  Error in Pass 3: {e}")
        traceback.print_exc()
        return None, None, 0, 0, 0, 0.0, None


def display_pass2_results(pass2_result: Dict[str, Any]):
    """Display Pass 2 inference results in formatted view."""
    print(f"\n### PASS 2 INFERENCE ###\n")
    print(json.dumps(pass2_result, indent=2))


def display_pass3_results(analysis: Dict[str, Any], summary: Dict[str, Any]):
    """Display Pass 3 analysis and summary in formatted view."""
    print(f"\n### PASS 3 ANALYSIS ###\n")

    # Display Analysis
    print("=== ANALYSIS ===\n")
    print(json.dumps(analysis, indent=2))

    # Display Summary
    print(f"\n{'=' * 120}")
    print("=== EXECUTIVE SUMMARY ===")
    print(f"{'=' * 120}\n")

    if summary.get('strengths'):
        print("✓ Strengths:")
        for strength in summary['strengths']:
            print(f"  • {strength}")
        print()

    if summary.get('concerns'):
        print("⚠ Concerns:")
        for concern in summary['concerns']:
            print(f"  • {concern}")
        print()

    if summary.get('best_fit_for'):
        print("👤 Best Fit For:")
        for fit in summary['best_fit_for']:
            print(f"  • {fit}")
        print()

    if summary.get('red_flags_to_probe'):
        print("🚩 Red Flags to Probe:")
        for flag in summary['red_flags_to_probe']:
            print(f"  • {flag}")
        print()

    if summary.get('negotiation_leverage'):
        print("💼 Negotiation Leverage:")
        for leverage in summary['negotiation_leverage']:
            print(f"  • {leverage}")
        print()

    if summary.get('overall_assessment'):
        print("📋 Overall Assessment:")
        print(f"  {summary['overall_assessment']}\n")

    if summary.get('recommendation_score') is not None:
        rec_score = summary.get('recommendation_score', 0.0)
        rec_conf = summary.get('recommendation_confidence', 0.0)
        # Handle dict case (nested value key)
        if isinstance(rec_score, dict):
            rec_score = rec_score.get('value', rec_score.get('score', 0.0))
        if isinstance(rec_conf, dict):
            rec_conf = rec_conf.get('value', rec_conf.get('confidence', 0.0))
        # Ensure numeric values
        try:
            rec_score = float(rec_score) if rec_score is not None else 0.0
            rec_conf = float(rec_conf) if rec_conf is not None else 0.0
            print(f"⭐ Recommendation Score: {rec_score:.2f} (confidence: {rec_conf:.2f})")
        except (TypeError, ValueError):
            print(f"⭐ Recommendation Score: {rec_score} (confidence: {rec_conf})")
