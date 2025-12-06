"""
Lambda: EnrichPartition
Enriches a single partition with AI-derived metadata using 3-pass architecture.
Fault-tolerant: processes all records, marking failures individually.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import pandas as pd

from .bedrock_client import BedrockClient
from .prompts import build_pass1_prompt
from .parsers import parse_llm_json, validate_extraction_response
from .flatteners import flatten_extraction

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SILVER_BUCKET = os.environ.get("SILVER_BUCKET")
SILVER_PREFIX = os.environ.get("SILVER_PREFIX", "linkedin/")
SILVER_AI_PREFIX = os.environ.get("SILVER_AI_PREFIX", "linkedin_ai/")
BEDROCK_MODEL_PASS1 = os.environ.get("BEDROCK_MODEL_PASS1", "openai.gpt-oss-120b-1:0")
BEDROCK_MODEL_PASS2 = os.environ.get("BEDROCK_MODEL_PASS2", "openai.gpt-oss-120b-1:0")
BEDROCK_MODEL_PASS3 = os.environ.get("BEDROCK_MODEL_PASS3", "openai.gpt-oss-120b-1:0")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

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


def create_empty_enrichment() -> Dict[str, Any]:
    """Create empty enrichment columns for failed records."""
    return {
        # Metadata
        "enriched_at": datetime.now(timezone.utc).isoformat(),
        "enrichment_version": ENRICHMENT_VERSION,
        "enrichment_model_pass1": BEDROCK_MODEL_PASS1,
        "enrichment_model_pass2": BEDROCK_MODEL_PASS2,
        "enrichment_model_pass3": BEDROCK_MODEL_PASS3,

        # Status flags
        "pass1_success": False,
        "pass2_success": False,
        "pass3_success": False,

        # Metrics (null for failures)
        "total_tokens_used": None,
        "enrichment_cost_usd": None,
        "avg_confidence_pass2": None,
        "avg_confidence_pass3": None,

        # Error tracking
        "enrichment_errors": None,
        "low_confidence_fields": None,
    }


def enrich_single_job(job: Dict[str, Any], bedrock_client: Optional[BedrockClient] = None) -> Dict[str, Any]:
    """
    Run 3-pass enrichment on a single job.

    Returns dict with all enrichment columns.
    Handles errors gracefully - returns partial results on failure.

    Args:
        job: Job dict with title, company_name, job_location, job_description_text
        bedrock_client: Optional Bedrock client (uses singleton if not provided)
    """
    result = create_empty_enrichment()
    errors = []
    total_tokens = 0
    total_cost = 0.0

    job_id = job.get("job_posting_id", "unknown")
    client = bedrock_client or get_bedrock_client()

    # Extract job fields
    title = job.get("job_title", "") or job.get("title", "")
    company = job.get("company_name", "")
    location = job.get("job_location", "") or job.get("location", "")
    description = job.get("job_description_text", "") or job.get("description", "")

    # Store raw extraction result for cascading to Pass 2/3
    pass1_extraction = None

    # ═══════════════════════════════════════════════════════════════
    # PASS 1: Extraction
    # ═══════════════════════════════════════════════════════════════
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

        total_tokens += input_tokens + output_tokens
        total_cost += cost

        # Parse JSON response
        parsed, parse_error = parse_llm_json(response_text)
        if parse_error:
            raise ValueError(f"JSON parse error: {parse_error}")

        # Validate schema
        is_valid, validation_errors = validate_extraction_response(parsed)
        if not is_valid:
            raise ValueError(f"Validation errors: {validation_errors}")

        # Extract and flatten
        pass1_extraction = parsed.get("extraction", {})
        result.update(flatten_extraction(pass1_extraction))
        result["pass1_success"] = True

        logger.info(f"Pass 1 success for {job_id}: {input_tokens}+{output_tokens} tokens, ${cost:.6f}")

    except Exception as e:
        logger.warning(f"Pass 1 failed for job {job_id}: {e}")
        errors.append(f"Pass1: {str(e)}")
        result["pass1_success"] = False

    # TODO: Implement in Sprint 3
    # Pass 2: Inference (only if Pass 1 succeeded)
    if result.get("pass1_success", False):
        try:
            # pass2_result = run_pass2(job, pass1_extraction)
            # result.update(flatten_inference(pass2_result))
            # result["pass2_success"] = True
            pass  # Skeleton - Sprint 3
        except Exception as e:
            logger.warning(f"Pass 2 failed for job {job_id}: {e}")
            errors.append(f"Pass2: {str(e)}")
            result["pass2_success"] = False

    # TODO: Implement in Sprint 4
    # Pass 3: Analysis (only if Pass 1 and 2 succeeded)
    if result.get("pass1_success", False) and result.get("pass2_success", False):
        try:
            # pass3_result = run_pass3(job, pass1_extraction, pass2_inference)
            # result.update(flatten_analysis(pass3_result))
            # result["pass3_success"] = True
            pass  # Skeleton - Sprint 4
        except Exception as e:
            logger.warning(f"Pass 3 failed for job {job_id}: {e}")
            errors.append(f"Pass3: {str(e)}")
            result["pass3_success"] = False

    # Aggregate metrics
    result["total_tokens_used"] = total_tokens if total_tokens > 0 else None
    result["enrichment_cost_usd"] = round(total_cost, 6) if total_cost > 0 else None
    result["enrichment_errors"] = "; ".join(errors) if errors else None

    return result


def process_partition(df: pd.DataFrame) -> pd.DataFrame:
    """
    Process all jobs in a partition.

    Fault-tolerant: continues processing even if individual jobs fail.
    Returns DataFrame with original columns + enrichment columns.
    """
    enriched_rows = []

    total_jobs = len(df)
    success_count = 0
    partial_count = 0
    failure_count = 0

    for idx, row in df.iterrows():
        job_dict = row.to_dict()
        job_id = job_dict.get("job_posting_id", f"row_{idx}")

        logger.info(f"Processing job {idx + 1}/{total_jobs}: {job_id}")

        try:
            # Run enrichment
            enrichment = enrich_single_job(job_dict)

            # Merge original + enrichment
            merged = {**job_dict, **enrichment}
            enriched_rows.append(merged)

            # Track success rate
            if enrichment.get("pass3_success"):
                success_count += 1
            elif enrichment.get("pass1_success"):
                partial_count += 1
            else:
                failure_count += 1

        except Exception as e:
            # Catastrophic failure - still keep the record
            logger.error(f"Catastrophic failure for job {job_id}: {e}")

            empty_enrichment = create_empty_enrichment()
            empty_enrichment["enrichment_errors"] = f"Catastrophic: {str(e)}"

            merged = {**job_dict, **empty_enrichment}
            enriched_rows.append(merged)
            failure_count += 1

    logger.info(f"Partition complete: {success_count} success, {partial_count} partial, {failure_count} failed")

    return pd.DataFrame(enriched_rows)


def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Process a single partition for AI enrichment.

    Fault-tolerant: processes all records, marking failures individually.
    The partition is written even if some records fail.

    Event:
    {
        "partition": {
            "year": "2025",
            "month": "12",
            "day": "05",
            "hour": "10"
        }
    }
    """
    partition = event.get("partition", {})
    year = partition.get("year")
    month = partition.get("month")
    day = partition.get("day")
    hour = partition.get("hour")

    if not all([year, month, day, hour]):
        return {"statusCode": 400, "error": "Missing partition keys"}

    partition_path = f"year={year}/month={month}/day={day}/hour={hour}"
    logger.info(f"EnrichPartition started: {partition_path}")
    logger.info(f"Models: Pass1={BEDROCK_MODEL_PASS1}, Pass2={BEDROCK_MODEL_PASS2}, Pass3={BEDROCK_MODEL_PASS3}")

    # TODO: Implement S3 I/O in Sprint 5
    # from shared.s3_utils import read_partition, write_partition
    #
    # # 1. Read Silver Parquet
    # df = read_partition(year, month, day, hour)
    # if df is None or df.empty:
    #     return {"statusCode": 200, "message": "Empty partition", "jobs_processed": 0}
    #
    # # 2. Process all jobs (fault-tolerant)
    # enriched_df = process_partition(df)
    #
    # # 3. Write to Silver-AI (always writes, even with failures)
    # write_partition(enriched_df, year, month, day, hour)
    #
    # # 4. Calculate stats
    # success_rate = enriched_df["pass3_success"].sum() / len(enriched_df)

    return {
        "statusCode": 200,
        "status": "skeleton",
        "partition": partition_path,
        "enrichment_version": ENRICHMENT_VERSION,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
        "message": "Handler skeleton - implement passes in Sprints 2-4, S3 I/O in Sprint 5"
    }


if __name__ == "__main__":
    # Local testing
    from dotenv import load_dotenv
    load_dotenv()

    test_event = {
        "partition": {
            "year": "2025",
            "month": "12",
            "day": "05",
            "hour": "10"
        }
    }
    result = handler(test_event, None)
    print(result)
