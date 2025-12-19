"""
Lambda: AI Enrichment ETL (Bronze AI -> Silver AI)

Consolidates AI enrichment results from Bronze (JSON per job/pass) into
Silver layer (Parquet partitioned by date).

State Control:
- Uses DynamoDB table to track processed jobs (O(1) lookup)
- Status table to find COMPLETED jobs ready for ETL
- ETL Processed table to track jobs already moved to Silver

Architecture:
- Reads from: s3://{bronze_bucket}/ai_enrichment/{job_id}/pass*.json
- Joins with: s3://{silver_bucket}/linkedin/ (to get partition info)
- Writes to:  s3://{silver_bucket}/ai_enrichment/year=.../month=.../day=.../
- Tracks in:  DynamoDB etl_processed table

Trigger: EventBridge schedule (e.g., every 30 minutes)
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple

import boto3
import awswrangler as wr
import pandas as pd
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
BRONZE_BUCKET = os.environ.get("BRONZE_BUCKET", "data-engineer-jobs-bronze")
SILVER_BUCKET = os.environ.get("SILVER_BUCKET", "data-engineer-jobs-silver")
BRONZE_AI_PREFIX = os.environ.get("BRONZE_AI_PREFIX", "ai_enrichment/")
SILVER_AI_PREFIX = os.environ.get("SILVER_AI_PREFIX", "ai_enrichment/")
SILVER_JOBS_PREFIX = os.environ.get("SILVER_JOBS_PREFIX", "linkedin/")
MAX_JOBS_PER_RUN = int(os.environ.get("MAX_JOBS_PER_RUN", "500"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "100"))
ETL_PROCESSED_TABLE = os.environ.get("ETL_PROCESSED_TABLE", "")
STATUS_TABLE = os.environ.get("STATUS_TABLE", "")

# TTL for processed records (90 days)
TTL_DAYS = 90

s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")


def get_pending_jobs_from_status(limit: int, already_processed: set) -> List[str]:
    """
    Get COMPLETED jobs that are not yet processed.
    Paginates through the GSI until we find enough unprocessed jobs.
    Uses ScanIndexForward=False to get most recent jobs first.
    """
    if not STATUS_TABLE:
        logger.warning("STATUS_TABLE not configured, falling back to Bronze scan")
        return []

    table = dynamodb.Table(STATUS_TABLE)
    pending_jobs = []
    total_scanned = 0
    max_scan = 10000  # Safety limit

    try:
        # Query GSI in descending order (most recent first)
        response = table.query(
            IndexName="status-index",
            KeyConditionExpression=Key("overallStatus").eq("COMPLETED"),
            ScanIndexForward=False,  # Descending order (most recent first)
            Limit=500,  # Fetch in larger batches for efficiency
            ProjectionExpression="job_posting_id"
        )

        for item in response.get("Items", []):
            job_id = item["job_posting_id"]
            total_scanned += 1
            if job_id not in already_processed:
                pending_jobs.append(job_id)
                if len(pending_jobs) >= limit:
                    break

        # Keep paginating until we have enough or exhaust the index
        while (
            "LastEvaluatedKey" in response
            and len(pending_jobs) < limit
            and total_scanned < max_scan
        ):
            response = table.query(
                IndexName="status-index",
                KeyConditionExpression=Key("overallStatus").eq("COMPLETED"),
                ExclusiveStartKey=response["LastEvaluatedKey"],
                ScanIndexForward=False,
                Limit=500,
                ProjectionExpression="job_posting_id"
            )
            for item in response.get("Items", []):
                job_id = item["job_posting_id"]
                total_scanned += 1
                if job_id not in already_processed:
                    pending_jobs.append(job_id)
                    if len(pending_jobs) >= limit:
                        break

        logger.info(f"Found {len(pending_jobs)} pending jobs (scanned {total_scanned} COMPLETED)")
        return pending_jobs[:limit]

    except Exception as e:
        logger.error(f"Error querying status table: {e}")
        return []


def get_already_processed_jobs(job_ids: List[str]) -> set:
    """
    Check which jobs have already been processed to Silver.
    Uses BatchGetItem for efficient lookup.
    """
    if not ETL_PROCESSED_TABLE or not job_ids:
        return set()

    table = dynamodb.Table(ETL_PROCESSED_TABLE)
    processed = set()

    # BatchGetItem supports max 100 items per request
    for i in range(0, len(job_ids), 100):
        batch = job_ids[i:i + 100]
        keys = [{"job_posting_id": job_id} for job_id in batch]

        try:
            response = dynamodb.batch_get_item(
                RequestItems={
                    ETL_PROCESSED_TABLE: {
                        "Keys": keys,
                        "ProjectionExpression": "job_posting_id"
                    }
                }
            )

            for item in response.get("Responses", {}).get(ETL_PROCESSED_TABLE, []):
                processed.add(item["job_posting_id"])

        except Exception as e:
            logger.error(f"Error batch getting processed jobs: {e}")

    logger.info(f"Found {len(processed)} already processed jobs")
    return processed


def mark_jobs_as_processed(job_ids: List[str], partition_date: str) -> int:
    """
    Mark jobs as processed in DynamoDB.
    Uses BatchWriteItem for efficiency.
    """
    if not ETL_PROCESSED_TABLE or not job_ids:
        return 0

    table = dynamodb.Table(ETL_PROCESSED_TABLE)
    now = datetime.now(timezone.utc)
    ttl = int((now + timedelta(days=TTL_DAYS)).timestamp())
    processed_at = now.isoformat()

    written = 0

    # BatchWriteItem supports max 25 items per request
    for i in range(0, len(job_ids), 25):
        batch = job_ids[i:i + 25]

        try:
            with table.batch_writer() as writer:
                for job_id in batch:
                    writer.put_item(Item={
                        "job_posting_id": job_id,
                        "processed_at": processed_at,
                        "partition_date": partition_date,
                        "ttl": ttl
                    })
                    written += 1

        except Exception as e:
            logger.error(f"Error batch writing processed jobs: {e}")

    return written


def list_bronze_ai_jobs() -> List[str]:
    """List all job IDs in Bronze AI enrichment (fallback method)."""
    paginator = s3_client.get_paginator("list_objects_v2")
    job_ids = set()

    for page in paginator.paginate(Bucket=BRONZE_BUCKET, Prefix=BRONZE_AI_PREFIX, Delimiter="/"):
        for prefix in page.get("CommonPrefixes", []):
            job_id = prefix["Prefix"].replace(BRONZE_AI_PREFIX, "").rstrip("/")
            if job_id:
                job_ids.add(job_id)

    return list(job_ids)


def get_all_processed_jobs() -> set:
    """
    Get all job IDs that have been processed to Silver.
    Scans the entire etl_processed table (efficient for tracking table).
    """
    if not ETL_PROCESSED_TABLE:
        return set()

    table = dynamodb.Table(ETL_PROCESSED_TABLE)
    processed = set()

    try:
        response = table.scan(
            ProjectionExpression="job_posting_id",
            Limit=10000
        )

        for item in response.get("Items", []):
            processed.add(item["job_posting_id"])

        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = table.scan(
                ProjectionExpression="job_posting_id",
                ExclusiveStartKey=response["LastEvaluatedKey"],
                Limit=10000
            )
            for item in response.get("Items", []):
                processed.add(item["job_posting_id"])

        logger.info(f"Loaded {len(processed)} processed job IDs from tracking table")
        return processed

    except Exception as e:
        logger.error(f"Error scanning processed table: {e}")
        return set()


def get_pending_jobs(limit: int) -> List[str]:
    """
    Get jobs that are COMPLETED but not yet processed to Silver.
    Efficiently finds pending jobs by:
    1. Loading all processed job IDs from tracking table (small set, O(1) lookup)
    2. Scanning status GSI for COMPLETED jobs, filtering as we go
    """
    # Load all processed job IDs first (for O(1) lookup)
    already_processed = get_all_processed_jobs()

    # Get pending jobs from status table, filtering against processed set
    pending = get_pending_jobs_from_status(limit, already_processed)

    if not pending and not STATUS_TABLE:
        # Fallback to Bronze scan if status table not available
        logger.info("Falling back to Bronze scan")
        completed_jobs = list_bronze_ai_jobs()
        pending = [j for j in completed_jobs if j not in already_processed][:limit]

    return pending


def read_pass_json(job_id: str, pass_name: str) -> Optional[Dict]:
    """Read a single pass JSON from Bronze."""
    prefix = f"{BRONZE_AI_PREFIX}{job_id}/{pass_name}-"

    try:
        response = s3_client.list_objects_v2(Bucket=BRONZE_BUCKET, Prefix=prefix)

        for obj in response.get("Contents", []):
            key = obj["Key"]
            if "-raw.txt" in key:
                continue
            if key.endswith(".json"):
                result = s3_client.get_object(Bucket=BRONZE_BUCKET, Key=key)
                return json.loads(result["Body"].read().decode("utf-8"))

        return None
    except Exception as e:
        logger.warning(f"Error reading {pass_name} for job {job_id}: {e}")
        return None


def read_job_enrichment(job_id: str) -> Optional[Dict]:
    """Read all 3 passes for a job and consolidate."""
    pass1 = read_pass_json(job_id, "pass1")
    pass2 = read_pass_json(job_id, "pass2")
    pass3 = read_pass_json(job_id, "pass3")

    if not pass1 or not pass3:
        logger.warning(f"Incomplete enrichment for job {job_id}: pass1={bool(pass1)}, pass3={bool(pass3)}")
        return None

    metadata = pass1.get("metadata", {})

    return {
        "job_posting_id": job_id,
        "model_id": metadata.get("model_id"),
        "enriched_at": metadata.get("timestamp"),
        "job_title": metadata.get("job_title"),
        "company_name": metadata.get("company_name"),
        "job_location": metadata.get("job_location"),
        "extraction": pass1.get("result", {}),
        "inference": pass2.get("result", {}) if pass2 else {},
        "analysis": pass3.get("result", {}).get("analysis", {}),
        "summary": pass3.get("result", {}).get("summary", {}),
    }


def get_job_partition_info(job_ids: List[str]) -> Dict[str, Dict]:
    """Get partition info (source_system) for jobs from Silver layer."""
    if not job_ids:
        return {}

    silver_path = f"s3://{SILVER_BUCKET}/{SILVER_JOBS_PREFIX}"

    try:
        df = wr.s3.read_parquet(
            path=silver_path,
            columns=["job_posting_id", "source_system"],
            dataset=True,
            partition_filter=lambda x: True,
        )

        df = df[df["job_posting_id"].astype(str).isin([str(j) for j in job_ids])]

        result = {}
        for _, row in df.iterrows():
            job_id = str(row["job_posting_id"])
            result[job_id] = {
                "source_system": row.get("source_system", "linkedin"),
            }

        return result
    except Exception as e:
        logger.warning(f"Error getting partition info: {e}")
        return {}


def process_batch(job_ids: List[str]) -> Tuple[pd.DataFrame, List[str], int]:
    """Process a batch of jobs and return DataFrame + successful job IDs."""
    records = []
    successful_jobs = []
    error_count = 0

    partition_info = get_job_partition_info(job_ids)

    for job_id in job_ids:
        try:
            enrichment = read_job_enrichment(job_id)
            if enrichment:
                info = partition_info.get(job_id, {})
                enrichment["source_system"] = info.get("source_system", "linkedin")

                enriched_at = enrichment.get("enriched_at")
                if enriched_at:
                    try:
                        dt = datetime.strptime(enriched_at, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        dt = datetime.now(timezone.utc)
                else:
                    dt = datetime.now(timezone.utc)

                enrichment["year"] = dt.year
                enrichment["month"] = dt.month
                enrichment["day"] = dt.day

                enrichment["extraction_json"] = json.dumps(enrichment.pop("extraction"))
                enrichment["inference_json"] = json.dumps(enrichment.pop("inference"))
                enrichment["analysis_json"] = json.dumps(enrichment.pop("analysis"))
                enrichment["summary_json"] = json.dumps(enrichment.pop("summary"))

                records.append(enrichment)
                successful_jobs.append(job_id)
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}")
            error_count += 1

    if records:
        df = pd.DataFrame(records)
        return df, successful_jobs, error_count
    else:
        return pd.DataFrame(), successful_jobs, error_count


def write_to_silver(df: pd.DataFrame) -> int:
    """Write DataFrame to Silver AI as partitioned Parquet."""
    if df.empty:
        return 0

    silver_path = f"s3://{SILVER_BUCKET}/{SILVER_AI_PREFIX}"

    dtype = {
        "job_posting_id": "string",
        "model_id": "string",
        "enriched_at": "string",
        "job_title": "string",
        "company_name": "string",
        "job_location": "string",
        "source_system": "string",
        "extraction_json": "string",
        "inference_json": "string",
        "analysis_json": "string",
        "summary_json": "string",
    }

    for col, t in dtype.items():
        if col in df.columns:
            df[col] = df[col].astype(t)

    result = wr.s3.to_parquet(
        df=df,
        path=silver_path,
        dataset=True,
        partition_cols=["year", "month", "day"],
        mode="append",
        compression="snappy",
    )

    written = len(result.get("paths", []))
    logger.info(f"Wrote {len(df)} records to {written} partition(s)")
    return len(df)


def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Main handler for Bronze AI -> Silver AI ETL.

    Event parameters (optional):
    - max_jobs: Override MAX_JOBS_PER_RUN
    - job_ids: Process specific job IDs only
    - force: Skip DynamoDB check and force reprocess
    """
    start_time = datetime.now(timezone.utc)

    max_jobs = event.get("max_jobs", MAX_JOBS_PER_RUN)
    specific_jobs = event.get("job_ids", [])
    force = event.get("force", False)

    logger.info(f"Starting AI Enrichment ETL: max_jobs={max_jobs}, specific_jobs={len(specific_jobs)}, force={force}")
    logger.info(f"Tables: ETL_PROCESSED={ETL_PROCESSED_TABLE}, STATUS={STATUS_TABLE}")

    # Get pending jobs
    if specific_jobs:
        pending_jobs = specific_jobs[:max_jobs]
        if not force:
            already_processed = get_already_processed_jobs(pending_jobs)
            pending_jobs = [j for j in pending_jobs if j not in already_processed]
    else:
        pending_jobs = get_pending_jobs(max_jobs)

    if not pending_jobs:
        logger.info("No pending jobs to process")
        return {
            "statusCode": 200,
            "message": "No pending jobs",
            "jobs_processed": 0,
        }

    logger.info(f"Processing {len(pending_jobs)} jobs")

    # Process in batches
    total_success = 0
    total_errors = 0
    total_written = 0
    all_successful_jobs = []

    for i in range(0, len(pending_jobs), BATCH_SIZE):
        batch = pending_jobs[i:i + BATCH_SIZE]
        logger.info(f"Processing batch {i // BATCH_SIZE + 1}: {len(batch)} jobs")

        df, successful_jobs, errors = process_batch(batch)
        total_success += len(successful_jobs)
        total_errors += errors
        all_successful_jobs.extend(successful_jobs)

        if not df.empty:
            written = write_to_silver(df)
            total_written += written

    # Mark successful jobs as processed in DynamoDB
    if all_successful_jobs:
        partition_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        marked = mark_jobs_as_processed(all_successful_jobs, partition_date)
        logger.info(f"Marked {marked} jobs as processed in DynamoDB")

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()

    result = {
        "statusCode": 200,
        "message": f"Processed {total_success} jobs, {total_errors} errors",
        "jobs_processed": total_success,
        "jobs_errors": total_errors,
        "records_written": total_written,
        "jobs_marked_processed": len(all_successful_jobs),
        "duration_seconds": round(duration, 2),
    }

    logger.info(f"ETL complete: {result}")
    return result


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    result = handler({"max_jobs": 10}, None)
    print(json.dumps(result, indent=2))
