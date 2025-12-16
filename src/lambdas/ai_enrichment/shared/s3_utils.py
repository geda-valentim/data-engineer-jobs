"""
S3 utilities for reading/writing Parquet files and Bronze JSON results.
Uses AWS SDK for Pandas (awswrangler) and boto3.
"""

import os
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
import awswrangler as wr
import pandas as pd

logger = logging.getLogger()

SILVER_BUCKET = os.environ.get("SILVER_BUCKET")
SILVER_PREFIX = os.environ.get("SILVER_PREFIX", "linkedin/")
SILVER_AI_PREFIX = os.environ.get("SILVER_AI_PREFIX", "linkedin_ai/")
BRONZE_BUCKET = os.environ.get("BRONZE_BUCKET")
BRONZE_AI_PREFIX = os.environ.get("BRONZE_AI_PREFIX", "ai_enrichment/")

# S3 client singleton
_s3_client = None


def _get_s3_client():
    """Get or create S3 client singleton."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def get_silver_path(year: str, month: str, day: str, hour: str) -> str:
    """Build Silver partition path."""
    return f"s3://{SILVER_BUCKET}/{SILVER_PREFIX}year={year}/month={month}/day={day}/hour={hour}/"


def get_silver_ai_path(year: str = None, month: str = None, day: str = None, hour: str = None) -> str:
    """Build Silver-AI path (base or partition-specific)."""
    base = f"s3://{SILVER_BUCKET}/{SILVER_AI_PREFIX}"
    if all([year, month, day, hour]):
        return f"{base}year={year}/month={month}/day={day}/hour={hour}/"
    return base


def read_partition(year: str, month: str, day: str, hour: str) -> Optional[pd.DataFrame]:
    """
    Read a Silver partition as DataFrame.
    Returns None if partition doesn't exist or is empty.
    """
    path = get_silver_path(year, month, day, hour)
    logger.info(f"Reading partition: {path}")

    try:
        df = wr.s3.read_parquet(path=path)
        logger.info(f"Loaded {len(df)} records from {path}")
        return df
    except Exception as e:
        logger.warning(f"Could not read partition {path}: {e}")
        return None


def write_partition(
    df: pd.DataFrame,
    year: str,
    month: str,
    day: str,
    hour: str,
    mode: str = "overwrite"
) -> str:
    """
    Write enriched DataFrame to Silver-AI.

    Args:
        df: DataFrame to write
        year, month, day, hour: Partition values
        mode: 'overwrite' or 'append'

    Returns:
        Written path
    """
    path = get_silver_ai_path(year, month, day, hour)
    logger.info(f"Writing {len(df)} records to {path}")

    wr.s3.to_parquet(
        df=df,
        path=path,
        index=False,
        dataset=False,  # Single file per partition
        mode=mode
    )

    return path


def list_silver_partitions() -> List[Dict[str, str]]:
    """List all Silver partitions as dicts."""
    base_path = f"s3://{SILVER_BUCKET}/{SILVER_PREFIX}"

    try:
        # List year directories first
        year_dirs = wr.s3.list_directories(path=base_path)
        partitions = []

        for year_dir in year_dirs:
            if "year=" not in year_dir:
                continue

            # List recursively to get all partitions
            try:
                month_dirs = wr.s3.list_directories(path=year_dir)
                for month_dir in month_dirs:
                    day_dirs = wr.s3.list_directories(path=month_dir)
                    for day_dir in day_dirs:
                        hour_dirs = wr.s3.list_directories(path=day_dir)
                        for hour_dir in hour_dirs:
                            partition = _parse_partition_path(hour_dir, base_path)
                            if partition:
                                partitions.append(partition)
            except Exception as e:
                logger.warning(f"Error listing under {year_dir}: {e}")

        return partitions

    except Exception as e:
        logger.error(f"Error listing Silver partitions: {e}")
        return []


def list_silver_ai_partitions() -> List[Dict[str, str]]:
    """List all Silver-AI partitions as dicts."""
    base_path = get_silver_ai_path()

    try:
        year_dirs = wr.s3.list_directories(path=base_path)
        partitions = []

        for year_dir in year_dirs:
            if "year=" not in year_dir:
                continue

            try:
                month_dirs = wr.s3.list_directories(path=year_dir)
                for month_dir in month_dirs:
                    day_dirs = wr.s3.list_directories(path=month_dir)
                    for day_dir in day_dirs:
                        hour_dirs = wr.s3.list_directories(path=day_dir)
                        for hour_dir in hour_dirs:
                            partition = _parse_partition_path(hour_dir, base_path)
                            if partition:
                                partitions.append(partition)
            except Exception as e:
                logger.warning(f"Error listing under {year_dir}: {e}")

        return partitions

    except Exception as e:
        logger.warning(f"Error listing Silver-AI partitions (may not exist yet): {e}")
        return []


def _parse_partition_path(path: str, base_path: str) -> Optional[Dict[str, str]]:
    """Parse partition path into dict."""
    relative = path.replace(base_path, "").strip("/")
    parts = relative.split("/")

    partition = {}
    for part in parts:
        if "=" in part:
            key, value = part.split("=", 1)
            partition[key] = value

    if all(k in partition for k in ["year", "month", "day", "hour"]):
        return partition
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Bronze AI Enrichment Functions
# ═══════════════════════════════════════════════════════════════════════════


def get_model_short_name(model_id: str) -> str:
    """
    Extract short model name from full model ID.

    Examples:
        'mistral.mistral-large-2407-v1:0' -> 'mistral-mistral-large-2407-v1'
        'anthropic.claude-3-sonnet-20240229-v1:0' -> 'anthropic-claude-3-sonnet'
        'google.gemma-3-27b-it' -> 'google-gemma-3-27b-it'

    Args:
        model_id: Full Bedrock model ID

    Returns:
        Shortened model name safe for filenames
    """
    # Remove version suffix (:0, :1, etc.)
    name = model_id.split(":")[0]
    # Replace dots with dashes for filename safety
    name = name.replace(".", "-")
    return name


def get_bronze_path(job_id: str, pass_name: str, model_short_name: str, file_type: str = "json") -> str:
    """
    Build Bronze path for AI enrichment result.

    Args:
        job_id: Job posting ID
        pass_name: 'pass1', 'pass2', or 'pass3'
        model_short_name: Short model name (from get_model_short_name)
        file_type: 'json' or 'txt' (for raw response)

    Returns:
        S3 path like 's3://bucket/ai_enrichment/123456/pass1-mistral-large.json'
    """
    suffix = "-raw.txt" if file_type == "txt" else ".json"
    filename = f"{pass_name}-{model_short_name}{suffix}"
    return f"s3://{BRONZE_BUCKET}/{BRONZE_AI_PREFIX}{job_id}/{filename}"


def write_bronze_result(
    job_id: str,
    pass_name: str,
    model_id: str,
    result: Dict[str, Any],
    raw_response: str,
    job_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Write AI enrichment result to Bronze layer.

    Writes two files:
    - {pass_name}-{model}-raw.txt: Raw LLM response
    - {pass_name}-{model}.json: Structured result with metadata

    Args:
        job_id: Job posting ID
        pass_name: 'pass1', 'pass2', or 'pass3'
        model_id: Full Bedrock model ID
        result: Parsed and flattened result dict
        raw_response: Raw LLM response text
        job_metadata: Optional job metadata (title, company, location)

    Returns:
        Dict with 'raw_path' and 'json_path' of written files
    """
    s3 = _get_s3_client()
    model_short = get_model_short_name(model_id)

    # Build paths
    raw_key = f"{BRONZE_AI_PREFIX}{job_id}/{pass_name}-{model_short}-raw.txt"
    json_key = f"{BRONZE_AI_PREFIX}{job_id}/{pass_name}-{model_short}.json"

    # Write raw response
    s3.put_object(
        Bucket=BRONZE_BUCKET,
        Key=raw_key,
        Body=raw_response.encode("utf-8"),
        ContentType="text/plain",
    )
    logger.info(f"Wrote raw response to s3://{BRONZE_BUCKET}/{raw_key}")

    # Build JSON with metadata
    output = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "job_posting_id": job_id,
            "pass_name": pass_name,
            "model_id": model_id,
        },
        "result": result,
    }

    # Add job metadata if provided
    if job_metadata:
        output["metadata"]["job_title"] = job_metadata.get("job_title")
        output["metadata"]["company_name"] = job_metadata.get("company_name")
        output["metadata"]["job_location"] = job_metadata.get("job_location")

    # Write JSON
    s3.put_object(
        Bucket=BRONZE_BUCKET,
        Key=json_key,
        Body=json.dumps(output, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )
    logger.info(f"Wrote JSON result to s3://{BRONZE_BUCKET}/{json_key}")

    return {
        "raw_path": f"s3://{BRONZE_BUCKET}/{raw_key}",
        "json_path": f"s3://{BRONZE_BUCKET}/{json_key}",
    }


def check_job_processed(job_id: str, model_id: str, pass_name: str = "pass3") -> bool:
    """
    Check if a job has already been processed (pass3 exists in Bronze).

    Args:
        job_id: Job posting ID
        model_id: Full Bedrock model ID
        pass_name: Pass to check (default: 'pass3' for complete processing)

    Returns:
        True if the job has been processed with this model
    """
    s3 = _get_s3_client()
    model_short = get_model_short_name(model_id)
    key = f"{BRONZE_AI_PREFIX}{job_id}/{pass_name}-{model_short}.json"

    try:
        s3.head_object(Bucket=BRONZE_BUCKET, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise


def read_bronze_result(job_id: str, model_id: str, pass_name: str) -> Optional[Dict[str, Any]]:
    """
    Read existing Bronze result for a job/pass/model.

    Args:
        job_id: Job posting ID
        model_id: Full Bedrock model ID
        pass_name: 'pass1', 'pass2', or 'pass3'

    Returns:
        Dict with result data if exists, None otherwise
    """
    s3 = _get_s3_client()
    model_short = get_model_short_name(model_id)
    key = f"{BRONZE_AI_PREFIX}{job_id}/{pass_name}-{model_short}.json"

    try:
        response = s3.get_object(Bucket=BRONZE_BUCKET, Key=key)
        content = response["Body"].read().decode("utf-8")
        data = json.loads(content)
        logger.info(f"Read cached Bronze result from s3://{BRONZE_BUCKET}/{key}")
        return data.get("result")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return None
        raise
    except Exception as e:
        logger.warning(f"Error reading Bronze result: {e}")
        return None


def list_bronze_jobs(prefix: str = None) -> List[str]:
    """
    List all job IDs in Bronze AI enrichment layer.

    Args:
        prefix: Optional prefix to filter job IDs

    Returns:
        List of job posting IDs
    """
    s3 = _get_s3_client()
    base_prefix = BRONZE_AI_PREFIX
    if prefix:
        base_prefix = f"{BRONZE_AI_PREFIX}{prefix}"

    job_ids = set()
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=BRONZE_BUCKET, Prefix=base_prefix, Delimiter="/"):
        for common_prefix in page.get("CommonPrefixes", []):
            # Extract job_id from path like 'ai_enrichment/123456/'
            path = common_prefix["Prefix"]
            job_id = path.replace(BRONZE_AI_PREFIX, "").rstrip("/")
            if job_id:
                job_ids.add(job_id)

    return sorted(list(job_ids))
