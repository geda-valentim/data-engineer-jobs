"""
Lambda: DiscoverPartitions
Finds Silver partitions that haven't been processed to Silver-AI yet.
Optionally publishes jobs to SQS for distributed processing.
"""

import os
import json
import logging
from typing import Dict, Any, List, Set

import boto3
import awswrangler as wr
import pandas as pd

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SILVER_BUCKET = os.environ.get("SILVER_BUCKET")
SILVER_PREFIX = os.environ.get("SILVER_PREFIX", "linkedin/")
SILVER_AI_PREFIX = os.environ.get("SILVER_AI_PREFIX", "linkedin_ai/")
MAX_PARTITIONS = int(os.environ.get("MAX_PARTITIONS", "10"))
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL")
PUBLISH_TO_SQS = os.environ.get("PUBLISH_TO_SQS", "false").lower() == "true"
MAX_JOBS_PER_PARTITION = int(os.environ.get("MAX_JOBS_PER_PARTITION", "100"))

# SQS client singleton
_sqs_client = None


def _get_sqs_client():
    """Get or create SQS client singleton."""
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client("sqs")
    return _sqs_client


def list_partitions(bucket: str, prefix: str) -> Set[str]:
    """
    List all partitions under a prefix.

    Returns set of partition keys like "year=2024/month=01/day=15/hour=12"
    """
    path = f"s3://{bucket}/{prefix}"

    try:
        directories = wr.s3.list_directories(path)
        partitions = set()

        for dir_path in directories:
            # Extract partition key from path
            parts = dir_path.replace(path, "").strip("/")
            if parts and "year=" in parts:
                partitions.add(parts)

        return partitions

    except Exception as e:
        logger.error(f"Error listing partitions at {path}: {e}")
        return set()


def parse_partition_key(partition_key: str) -> Dict[str, str]:
    """
    Parse partition key string into dict.

    Args:
        partition_key: "year=2024/month=01/day=15/hour=12"

    Returns:
        {"year": "2024", "month": "01", "day": "15", "hour": "12"}
    """
    result = {}
    for part in partition_key.split("/"):
        if "=" in part:
            key, value = part.split("=", 1)
            result[key] = value
    return result


def get_silver_path(partition: Dict[str, str]) -> str:
    """Build Silver S3 path for a partition."""
    return f"s3://{SILVER_BUCKET}/{SILVER_PREFIX}year={partition['year']}/month={partition['month']}/day={partition['day']}/hour={partition['hour']}/"


def read_partition_jobs(partition: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Read jobs from a Silver partition.

    Args:
        partition: Dict with year, month, day, hour

    Returns:
        List of job dicts with essential fields
    """
    path = get_silver_path(partition)
    logger.info(f"Reading partition: {path}")

    try:
        df = wr.s3.read_parquet(path=path)

        if df.empty:
            logger.warning(f"Empty partition: {path}")
            return []

        # Limit jobs per partition
        if len(df) > MAX_JOBS_PER_PARTITION:
            logger.info(f"Limiting from {len(df)} to {MAX_JOBS_PER_PARTITION} jobs")
            df = df.head(MAX_JOBS_PER_PARTITION)

        # Extract essential fields for each job
        jobs = []
        for _, row in df.iterrows():
            job = {
                "job_posting_id": str(row.get("job_posting_id", "")),
                "job_title": row.get("job_title", ""),
                "company_name": row.get("company_name", ""),
                "job_location": row.get("job_location", ""),
                "job_description": row.get("job_description", ""),
                "partition": partition,
            }
            if job["job_posting_id"]:
                jobs.append(job)

        logger.info(f"Found {len(jobs)} jobs in partition")
        return jobs

    except Exception as e:
        logger.error(f"Error reading partition {path}: {e}")
        return []


def publish_jobs_to_sqs(jobs: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Publish jobs to SQS queue in batches.

    Args:
        jobs: List of job dicts to publish

    Returns:
        Dict with 'published' and 'failed' counts
    """
    if not SQS_QUEUE_URL:
        logger.warning("SQS_QUEUE_URL not set, skipping publish")
        return {"published": 0, "failed": len(jobs)}

    sqs = _get_sqs_client()
    published = 0
    failed = 0

    # SQS allows max 10 messages per batch
    batch_size = 10

    for i in range(0, len(jobs), batch_size):
        batch = jobs[i : i + batch_size]

        entries = []
        for idx, job in enumerate(batch):
            # Build deduplication ID with full date to avoid collisions across days
            partition = job.get('partition', {})
            dedup_id = (
                f"{job['job_posting_id']}-"
                f"{partition.get('year', '0')}-"
                f"{partition.get('month', '0')}-"
                f"{partition.get('day', '0')}-"
                f"{partition.get('hour', '0')}"
            )
            entries.append({
                "Id": str(idx),
                "MessageBody": json.dumps(job),
                "MessageGroupId": "ai-enrichment",  # For FIFO queues
                "MessageDeduplicationId": dedup_id,
            })

        try:
            response = sqs.send_message_batch(
                QueueUrl=SQS_QUEUE_URL,
                Entries=entries,
            )

            published += len(response.get("Successful", []))
            failed += len(response.get("Failed", []))

            for fail in response.get("Failed", []):
                logger.error(f"Failed to publish message: {fail}")

        except Exception as e:
            logger.error(f"Error publishing batch to SQS: {e}")
            failed += len(batch)

    logger.info(f"Published {published} jobs, {failed} failed")
    return {"published": published, "failed": failed}


def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Discover partitions pending enrichment.

    If PUBLISH_TO_SQS=true, reads jobs from partitions and publishes to SQS.

    Returns:
    {
        "has_work": bool,
        "partitions": [
            {"year": "2025", "month": "12", "day": "05", "hour": "10"},
            ...
        ],
        "total_pending": int,
        "processing_count": int,
        "sqs_stats": {"published": int, "failed": int}  # if PUBLISH_TO_SQS
    }
    """
    logger.info(f"DiscoverPartitions started - bucket={SILVER_BUCKET}")
    logger.info(f"Silver prefix: {SILVER_PREFIX}, Silver-AI prefix: {SILVER_AI_PREFIX}")
    logger.info(f"PUBLISH_TO_SQS: {PUBLISH_TO_SQS}")

    if not SILVER_BUCKET:
        raise ValueError("SILVER_BUCKET environment variable not set")

    # List existing partitions
    silver_partitions = list_partitions(SILVER_BUCKET, SILVER_PREFIX)
    silver_ai_partitions = list_partitions(SILVER_BUCKET, SILVER_AI_PREFIX)

    logger.info(f"Found {len(silver_partitions)} Silver partitions")
    logger.info(f"Found {len(silver_ai_partitions)} Silver-AI partitions")

    # Compute pending (Silver - Silver-AI)
    pending_partitions = silver_partitions - silver_ai_partitions
    logger.info(f"Pending partitions: {len(pending_partitions)}")

    # Sort by partition key (oldest first) and limit
    sorted_pending = sorted(pending_partitions)[:MAX_PARTITIONS]

    # Parse into structured format
    partitions = [parse_partition_key(pk) for pk in sorted_pending]

    result = {
        "has_work": len(partitions) > 0,
        "partitions": partitions,
        "total_pending": len(pending_partitions),
        "processing_count": len(partitions),
    }

    # Optionally publish jobs to SQS
    if PUBLISH_TO_SQS and partitions:
        logger.info(f"Publishing jobs from {len(partitions)} partitions to SQS")

        all_jobs = []
        for partition in partitions:
            jobs = read_partition_jobs(partition)
            all_jobs.extend(jobs)

        logger.info(f"Total jobs to publish: {len(all_jobs)}")

        if all_jobs:
            sqs_stats = publish_jobs_to_sqs(all_jobs)
            result["sqs_stats"] = sqs_stats
            result["total_jobs"] = len(all_jobs)
        else:
            result["sqs_stats"] = {"published": 0, "failed": 0}
            result["total_jobs"] = 0

    logger.info(f"Returning {len(partitions)} partitions for processing")
    return result


if __name__ == "__main__":
    # Local testing
    from dotenv import load_dotenv
    load_dotenv()

    result = handler({}, None)
    print(result)
