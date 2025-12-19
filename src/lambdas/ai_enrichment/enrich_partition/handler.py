"""
Lambda: EnrichPartition
Enriches a single job with AI-derived metadata using 3-pass architecture.
Invoked by Step Function for each pass (pass1, pass2, pass3).

Event format from Step Function:
{
    "pass_name": "pass1",  // or "pass2", "pass3"
    "job_data": {
        "job_posting_id": "123",
        "job_title": "Data Engineer",
        "company_name": "Acme Corp",
        "job_location": "Remote",
        "job_description": "..."
    },
    "pass1_result": {...},  // For pass2/pass3 - extraction from pass1
    "pass2_result": {...},  // For pass3 - inference from pass2
    "execution_id": "job-123-abc123"
}

Returns format for Step Function:
- Pass1: {statusCode, extraction, raw_response, model_id, success}
- Pass2: {statusCode, inference, raw_response, model_id, success}
- Pass3: {statusCode, analysis, raw_response, model_id, success}
"""

import os
import logging
from typing import Dict, Any

# Use absolute imports for Lambda deployment (flat structure in zip)
from bedrock_client import BedrockClient
from prompts import build_pass1_prompt, build_pass2_prompt, build_pass3_prompt
from parsers import parse_llm_json, validate_extraction_response, validate_inference_response, validate_analysis_response
from shared.s3_utils import write_bronze_result, check_job_processed, read_bronze_result

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
BRONZE_BUCKET = os.environ.get("BRONZE_BUCKET")
BRONZE_AI_PREFIX = os.environ.get("BRONZE_AI_PREFIX", "ai_enrichment/")
BEDROCK_MODEL_PASS1 = os.environ.get("BEDROCK_MODEL_PASS1", "openai.gpt-oss-120b-1:0")
BEDROCK_MODEL_PASS2 = os.environ.get("BEDROCK_MODEL_PASS2", "openai.gpt-oss-120b-1:0")
BEDROCK_MODEL_PASS3 = os.environ.get("BEDROCK_MODEL_PASS3", "openai.gpt-oss-120b-1:0")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
WRITE_TO_BRONZE = os.environ.get("WRITE_TO_BRONZE", "true").lower() == "true"

# Enrichment version - increment on schema changes
ENRICHMENT_VERSION = "1.0"

# Initialize Bedrock client (reused across invocations)
_bedrock_client = None


def get_bedrock_client() -> BedrockClient:
    """Get or create Bedrock client singleton."""
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = BedrockClient(
            model_ids={
                "pass1": BEDROCK_MODEL_PASS1,
                "pass2": BEDROCK_MODEL_PASS2,
                "pass3": BEDROCK_MODEL_PASS3,
            },
            region=AWS_REGION,
        )
    return _bedrock_client


def get_model_for_pass(pass_name: str) -> str:
    """Get the model ID for a specific pass."""
    models = {
        "pass1": BEDROCK_MODEL_PASS1,
        "pass2": BEDROCK_MODEL_PASS2,
        "pass3": BEDROCK_MODEL_PASS3,
    }
    return models.get(pass_name, BEDROCK_MODEL_PASS1)


# ═══════════════════════════════════════════════════════════════════════════════
# Pass Execution Functions
# ═══════════════════════════════════════════════════════════════════════════════


def execute_pass1(job_data: Dict[str, Any], skip_cache: bool = False) -> Dict[str, Any]:
    """
    Execute Pass 1: Extraction.

    Extracts structured data from job description.
    Returns cached result if already processed with same model.

    Args:
        job_data: Job information with job_posting_id, job_title, company_name, etc.
        skip_cache: If True, bypass cache and force reprocessing.

    Returns:
        Dict with statusCode, extraction, raw_response, model_id, success
    """
    job_id = job_data.get("job_posting_id", "unknown")
    model_id = get_model_for_pass("pass1")

    # Check for cached result in Bronze (skip if force reprocessing)
    if not skip_cache and BRONZE_BUCKET and check_job_processed(job_id, model_id, "pass1"):
        cached = read_bronze_result(job_id, model_id, "pass1")
        if cached:
            logger.info(f"Pass 1 cache hit for job {job_id}, returning cached result")
            return {
                "statusCode": 200,
                "success": True,
                "extraction": cached,
                "raw_response": None,  # Not stored in cache lookup
                "model_id": model_id,
                "cached": True,
            }

    client = get_bedrock_client()

    # Extract job fields
    title = job_data.get("job_title", "") or ""
    company = job_data.get("company_name", "") or ""
    location = job_data.get("job_location", "") or ""
    description = job_data.get("job_description", "") or job_data.get("job_description_text", "") or ""

    logger.info(f"Pass 1 (Extraction) starting for job {job_id}")

    try:
        system_prompt, user_prompt = build_pass1_prompt(
            job_title=title,
            company_name=company,
            job_location=location,
            job_description_text=description,
        )

        response_text, input_tokens, output_tokens, cost = client.invoke(
            prompt=user_prompt,
            system=system_prompt,
            pass_name="pass1",
        )

        # Parse JSON response
        parsed, parse_error = parse_llm_json(response_text)
        if parse_error:
            raise ValueError(f"JSON parse error: {parse_error}")

        # Validate schema
        is_valid, validation_errors = validate_extraction_response(parsed)
        if not is_valid:
            raise ValueError(f"Validation errors: {validation_errors}")

        extraction = parsed.get("extraction", {})

        logger.info(f"Pass 1 success for {job_id}: {input_tokens}+{output_tokens} tokens, ${cost:.6f}")

        # Write to Bronze
        if WRITE_TO_BRONZE and BRONZE_BUCKET:
            write_bronze_result(
                job_id=job_id,
                pass_name="pass1",
                model_id=model_id,
                result=extraction,
                raw_response=response_text,
                job_metadata={"job_title": title, "company_name": company, "job_location": location},
            )

        return {
            "statusCode": 200,
            "success": True,
            "extraction": extraction,
            "raw_response": response_text,
            "model_id": model_id,
            "tokens": {"input": input_tokens, "output": output_tokens},
            "cost_usd": cost,
        }

    except Exception as e:
        logger.error(f"Pass 1 failed for job {job_id}: {e}")
        return {
            "statusCode": 500,
            "success": False,
            "extraction": None,
            "raw_response": None,
            "model_id": model_id,
            "error": str(e),
        }


def execute_pass2(job_data: Dict[str, Any], pass1_result: Dict[str, Any], skip_cache: bool = False) -> Dict[str, Any]:
    """
    Execute Pass 2: Inference.

    Infers additional attributes from job description + pass1 extraction.
    Returns cached result if already processed with same model.

    Args:
        job_data: Job information
        pass1_result: Extraction result from Pass 1
        skip_cache: If True, bypass cache and force reprocessing.

    Returns:
        Dict with statusCode, inference, raw_response, model_id, success
    """
    job_id = job_data.get("job_posting_id", "unknown")
    model_id = get_model_for_pass("pass2")

    # Check for cached result in Bronze (skip if force reprocessing)
    if not skip_cache and BRONZE_BUCKET and check_job_processed(job_id, model_id, "pass2"):
        cached = read_bronze_result(job_id, model_id, "pass2")
        if cached:
            logger.info(f"Pass 2 cache hit for job {job_id}, returning cached result")
            return {
                "statusCode": 200,
                "success": True,
                "inference": cached,
                "raw_response": None,
                "model_id": model_id,
                "cached": True,
            }

    client = get_bedrock_client()

    # Extract job fields
    title = job_data.get("job_title", "") or ""
    company = job_data.get("company_name", "") or ""
    location = job_data.get("job_location", "") or ""
    description = job_data.get("job_description", "") or job_data.get("job_description_text", "") or ""

    logger.info(f"Pass 2 (Inference) starting for job {job_id}")

    try:
        system_prompt, user_prompt = build_pass2_prompt(
            job_title=title,
            company_name=company,
            job_location=location,
            job_description_text=description,
            pass1_extraction=pass1_result,
        )

        response_text, input_tokens, output_tokens, cost = client.invoke(
            prompt=user_prompt,
            system=system_prompt,
            pass_name="pass2",
        )

        # Parse JSON response
        parsed, parse_error = parse_llm_json(response_text)
        if parse_error:
            raise ValueError(f"JSON parse error: {parse_error}")

        # Validate schema
        is_valid, validation_errors = validate_inference_response(parsed)
        if not is_valid:
            raise ValueError(f"Validation errors: {validation_errors}")

        inference = parsed.get("inference", {})

        logger.info(f"Pass 2 success for {job_id}: {input_tokens}+{output_tokens} tokens, ${cost:.6f}")

        # Write to Bronze
        if WRITE_TO_BRONZE and BRONZE_BUCKET:
            write_bronze_result(
                job_id=job_id,
                pass_name="pass2",
                model_id=model_id,
                result=inference,
                raw_response=response_text,
                job_metadata={"job_title": title, "company_name": company, "job_location": location},
            )

        return {
            "statusCode": 200,
            "success": True,
            "inference": inference,
            "raw_response": response_text,
            "model_id": model_id,
            "tokens": {"input": input_tokens, "output": output_tokens},
            "cost_usd": cost,
        }

    except Exception as e:
        logger.error(f"Pass 2 failed for job {job_id}: {e}")
        return {
            "statusCode": 500,
            "success": False,
            "inference": None,
            "raw_response": None,
            "model_id": model_id,
            "error": str(e),
        }


def execute_pass3(job_data: Dict[str, Any], pass1_result: Dict[str, Any], pass2_result: Dict[str, Any], skip_cache: bool = False) -> Dict[str, Any]:
    """
    Execute Pass 3: Analysis.

    Performs complex analysis combining extraction and inference.
    Returns cached result if already processed with same model.

    Args:
        job_data: Job information
        pass1_result: Extraction result from Pass 1
        pass2_result: Inference result from Pass 2
        skip_cache: If True, bypass cache and force reprocessing.

    Returns:
        Dict with statusCode, analysis, raw_response, model_id, success
    """
    job_id = job_data.get("job_posting_id", "unknown")
    model_id = get_model_for_pass("pass3")

    # Check for cached result in Bronze (skip if force reprocessing)
    if not skip_cache and BRONZE_BUCKET and check_job_processed(job_id, model_id, "pass3"):
        cached = read_bronze_result(job_id, model_id, "pass3")
        if cached:
            logger.info(f"Pass 3 cache hit for job {job_id}, returning cached result")
            return {
                "statusCode": 200,
                "success": True,
                "analysis": cached,
                "raw_response": None,
                "model_id": model_id,
                "cached": True,
            }

    client = get_bedrock_client()

    # Extract job fields
    title = job_data.get("job_title", "") or ""
    company = job_data.get("company_name", "") or ""
    location = job_data.get("job_location", "") or ""
    description = job_data.get("job_description", "") or job_data.get("job_description_text", "") or ""

    logger.info(f"Pass 3 (Analysis) starting for job {job_id}")

    try:
        system_prompt, user_prompt = build_pass3_prompt(
            job_title=title,
            company_name=company,
            job_location=location,
            job_description_text=description,
            pass1_extraction=pass1_result,
            pass2_inference=pass2_result,
        )

        response_text, input_tokens, output_tokens, cost = client.invoke(
            prompt=user_prompt,
            system=system_prompt,
            pass_name="pass3",
        )

        # Parse JSON response
        parsed, parse_error = parse_llm_json(response_text)
        if parse_error:
            raise ValueError(f"JSON parse error: {parse_error}")

        # Validate schema
        is_valid, validation_errors = validate_analysis_response(parsed)
        if not is_valid:
            raise ValueError(f"Validation errors: {validation_errors}")

        analysis = parsed.get("analysis", {})
        summary = parsed.get("summary", {})

        # Combine analysis and summary for output
        combined_result = {"analysis": analysis, "summary": summary}

        logger.info(f"Pass 3 success for {job_id}: {input_tokens}+{output_tokens} tokens, ${cost:.6f}")

        # Write to Bronze
        if WRITE_TO_BRONZE and BRONZE_BUCKET:
            write_bronze_result(
                job_id=job_id,
                pass_name="pass3",
                model_id=model_id,
                result=combined_result,
                raw_response=response_text,
                job_metadata={"job_title": title, "company_name": company, "job_location": location},
            )

        return {
            "statusCode": 200,
            "success": True,
            "analysis": combined_result,
            "raw_response": response_text,
            "model_id": model_id,
            "tokens": {"input": input_tokens, "output": output_tokens},
            "cost_usd": cost,
        }

    except Exception as e:
        logger.error(f"Pass 3 failed for job {job_id}: {e}")
        return {
            "statusCode": 500,
            "success": False,
            "analysis": None,
            "raw_response": None,
            "model_id": model_id,
            "error": str(e),
        }


def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Process a single pass for AI enrichment.

    Invoked by Step Function for each pass (pass1, pass2, pass3).
    Routes to the appropriate pass execution function.

    Event format:
    {
        "pass_name": "pass1",  // or "pass2", "pass3"
        "job_data": {
            "job_posting_id": "123",
            "job_title": "Data Engineer",
            "company_name": "Acme Corp",
            "job_location": "Remote",
            "job_description": "..."
        },
        "pass1_result": {...},  // For pass2/pass3 - extraction from pass1
        "pass2_result": {...},  // For pass3 - inference from pass2
        "execution_id": "job-123-abc123"
    }

    Returns:
        For Pass1: {statusCode, extraction, raw_response, model_id, success}
        For Pass2: {statusCode, inference, raw_response, model_id, success}
        For Pass3: {statusCode, analysis, raw_response, model_id, success}
    """
    pass_name = event.get("pass_name")
    job_data = event.get("job_data", {})
    execution_id = event.get("execution_id", "unknown")
    force = event.get("force", False)

    job_id = job_data.get("job_posting_id", "unknown")

    logger.info(f"EnrichPartition invoked: pass={pass_name}, job={job_id}, execution={execution_id}, force={force}")
    logger.info(f"Models: Pass1={BEDROCK_MODEL_PASS1}, Pass2={BEDROCK_MODEL_PASS2}, Pass3={BEDROCK_MODEL_PASS3}")

    # Validate required fields
    if not pass_name:
        return {"statusCode": 400, "error": "Missing pass_name", "success": False}

    if not job_data or not job_id:
        return {"statusCode": 400, "error": "Missing job_data or job_posting_id", "success": False}

    # Route to appropriate pass
    if pass_name == "pass1":
        return execute_pass1(job_data, skip_cache=force)

    elif pass_name == "pass2":
        pass1_result = event.get("pass1_result")
        if not pass1_result:
            return {
                "statusCode": 400,
                "error": "Missing pass1_result for pass2",
                "success": False,
                "model_id": get_model_for_pass("pass2"),
            }
        return execute_pass2(job_data, pass1_result, skip_cache=force)

    elif pass_name == "pass3":
        pass1_result = event.get("pass1_result")
        pass2_result = event.get("pass2_result")
        if not pass1_result or not pass2_result:
            return {
                "statusCode": 400,
                "error": "Missing pass1_result or pass2_result for pass3",
                "success": False,
                "model_id": get_model_for_pass("pass3"),
            }
        return execute_pass3(job_data, pass1_result, pass2_result, skip_cache=force)

    else:
        return {
            "statusCode": 400,
            "error": f"Invalid pass_name: {pass_name}. Must be pass1, pass2, or pass3",
            "success": False,
        }


if __name__ == "__main__":
    # Local testing
    import json
    from dotenv import load_dotenv
    load_dotenv()

    # Test Pass 1
    test_event_pass1 = {
        "pass_name": "pass1",
        "job_data": {
            "job_posting_id": "test-123",
            "job_title": "Senior Data Engineer",
            "company_name": "Test Company",
            "job_location": "Remote",
            "job_description": "We are looking for a Senior Data Engineer with experience in Python, SQL, and AWS...",
        },
        "execution_id": "test-exec-001",
    }

    print("Testing Pass 1:")
    result = handler(test_event_pass1, None)
    print(json.dumps(result, indent=2, default=str))
