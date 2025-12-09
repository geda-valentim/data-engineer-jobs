"""
Lambda: Companies Backfill Scanner

Scans Silver layer Parquet files for unique companies and queues missing
companies to SQS FIFO for fetching by companies_fetcher Lambda.

Architecture:
- Reads from Silver layer (Parquet)
- Filters against DynamoDB cache (companies-status table)
- Sends missing companies to SQS FIFO queue
- Tracks processed partitions in DynamoDB (backfill-processing-state table)
"""

import os
import json
import boto3
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Set, Optional
from collections import defaultdict

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Clients
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sqs_client = boto3.client("sqs")

# Environment Variables
SILVER_BUCKET_NAME = os.environ["SILVER_BUCKET_NAME"]
COMPANIES_STATUS_TABLE = os.environ["COMPANIES_STATUS_TABLE"]
BACKFILL_STATE_TABLE = os.environ["BACKFILL_STATE_TABLE"]
COMPANIES_QUEUE_URL = os.environ["COMPANIES_QUEUE_URL"]
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "30"))
MAX_PARTITIONS_PER_RUN = int(os.environ.get("MAX_PARTITIONS_PER_RUN", "10"))

# DynamoDB Tables
companies_status_table = dynamodb.Table(COMPANIES_STATUS_TABLE)
backfill_state_table = dynamodb.Table(BACKFILL_STATE_TABLE)

# Metrics
metrics = defaultdict(int)


def handler(event, context):
    """
    Main Lambda handler for companies backfill scanner.

    Event payload (optional):
    {
        "partition": "year=2025/month=12/day=08/hour=10",  # Specific partition
        "lookback_days": 7,  # Override default lookback
        "max_partitions": 5,  # Override max partitions per run
        "force_mode": false,  # Re-fetch even if in cache
        "dry_run": false  # Log only, don't send to SQS
    }
    """
    logger.info("=" * 70)
    logger.info("Companies Backfill Scanner - Starting")
    logger.info("=" * 70)

    # Parse event parameters
    specific_partition = event.get("partition")
    lookback_days = event.get("lookback_days", LOOKBACK_DAYS)
    max_partitions = event.get("max_partitions", MAX_PARTITIONS_PER_RUN)
    force_mode = event.get("force_mode", False)
    dry_run = event.get("dry_run", False)

    logger.info(f"Configuration:")
    logger.info(f"  Specific partition: {specific_partition or 'None (scan range)'}")
    logger.info(f"  Lookback days: {lookback_days}")
    logger.info(f"  Max partitions per run: {max_partitions}")
    logger.info(f"  Force mode: {force_mode}")
    logger.info(f"  Dry run: {dry_run}")

    try:
        # Step 1: Discover partitions to process
        if specific_partition:
            partitions_to_process = [specific_partition]
            logger.info(f"Processing specific partition: {specific_partition}")
        else:
            partitions_to_process = discover_partitions(lookback_days, max_partitions)
            logger.info(f"Discovered {len(partitions_to_process)} partitions to process")

        if not partitions_to_process:
            logger.info("No partitions to process. Exiting.")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "No partitions to process",
                    "metrics": dict(metrics)
                })
            }

        # Step 2: Process each partition
        for partition in partitions_to_process:
            try:
                process_partition(
                    partition,
                    force_mode=force_mode,
                    dry_run=dry_run
                )
            except Exception as e:
                logger.error(f"Error processing partition {partition}: {e}", exc_info=True)
                metrics["partitions_failed"] += 1
                # Continue with next partition
                continue

        # Final report
        logger.info("=" * 70)
        logger.info("Companies Backfill Scanner - Final Report")
        logger.info("=" * 70)
        logger.info(f"  Partitions scanned: {metrics['partitions_scanned']}")
        logger.info(f"  Partitions failed: {metrics['partitions_failed']}")
        logger.info(f"  Companies found: {metrics['companies_found']}")
        logger.info(f"  Companies already cached: {metrics['companies_cached']}")
        logger.info(f"  Companies queued: {metrics['companies_queued']}")
        logger.info(f"  SQS messages sent: {metrics['sqs_messages_sent']}")
        logger.info("=" * 70)

        # Send custom CloudWatch metrics
        send_cloudwatch_metrics()

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Backfill scan completed successfully",
                "metrics": dict(metrics)
            })
        }

    except Exception as e:
        logger.error(f"Fatal error in backfill scanner: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e),
                "metrics": dict(metrics)
            })
        }


def discover_partitions(lookback_days: int, max_partitions: int) -> List[str]:
    """
    Discover Silver layer partitions that need processing.

    Returns list of partition paths like: year=2025/month=12/day=08/hour=10
    """
    logger.info(f"Discovering partitions (lookback: {lookback_days} days, max: {max_partitions})")

    # Calculate date range
    today = datetime.now(timezone.utc)
    start_date = today - timedelta(days=lookback_days)

    all_partitions = []

    # List partitions from S3
    prefix = "linkedin/"
    paginator = s3_client.get_paginator("list_objects_v2")

    try:
        for page in paginator.paginate(Bucket=SILVER_BUCKET_NAME, Prefix=prefix, Delimiter="/"):
            # Get common prefixes (year= directories)
            for year_prefix in page.get("CommonPrefixes", []):
                year_path = year_prefix["Prefix"]
                year = int(year_path.split("year=")[1].strip("/"))

                # Skip if year is out of range
                if year < start_date.year or year > today.year:
                    continue

                # List months
                for month_page in paginator.paginate(Bucket=SILVER_BUCKET_NAME, Prefix=year_path, Delimiter="/"):
                    for month_prefix in month_page.get("CommonPrefixes", []):
                        month_path = month_prefix["Prefix"]
                        month = int(month_path.split("month=")[1].split("/")[0])

                        # List days
                        for day_page in paginator.paginate(Bucket=SILVER_BUCKET_NAME, Prefix=month_path, Delimiter="/"):
                            for day_prefix in day_page.get("CommonPrefixes", []):
                                day_path = day_prefix["Prefix"]
                                day = int(day_path.split("day=")[1].split("/")[0])

                                # Check if date is within lookback window
                                partition_date = datetime(year, month, day, tzinfo=timezone.utc)
                                if partition_date < start_date or partition_date > today:
                                    continue

                                # List hours
                                for hour_page in paginator.paginate(Bucket=SILVER_BUCKET_NAME, Prefix=day_path, Delimiter="/"):
                                    for hour_prefix in hour_page.get("CommonPrefixes", []):
                                        hour_path = hour_prefix["Prefix"]
                                        hour = int(hour_path.split("hour=")[1].split("/")[0])

                                        # Extract partition key
                                        partition_key = hour_path.replace(prefix, "").rstrip("/")
                                        all_partitions.append({
                                            "partition_key": partition_key,
                                            "date": partition_date.replace(hour=hour)
                                        })

        logger.info(f"Found {len(all_partitions)} total partitions in S3")

        # Filter out already-processed partitions
        unprocessed_partitions = filter_processed_partitions([p["partition_key"] for p in all_partitions])

        # Sort by date descending (newest first)
        partitions_with_dates = [p for p in all_partitions if p["partition_key"] in unprocessed_partitions]
        partitions_with_dates.sort(key=lambda x: x["date"], reverse=True)

        # Limit to max_partitions
        selected_partitions = [p["partition_key"] for p in partitions_with_dates[:max_partitions]]

        logger.info(f"Selected {len(selected_partitions)} partitions for processing (unprocessed, newest first)")

        return selected_partitions

    except Exception as e:
        logger.error(f"Error discovering partitions: {e}", exc_info=True)
        return []


def filter_processed_partitions(partitions: List[str]) -> Set[str]:
    """
    Filter out partitions that have already been processed.

    Returns set of partition keys that need processing.
    """
    if not partitions:
        return set()

    unprocessed = set(partitions)

    try:
        # Batch get from DynamoDB (25 items at a time - DynamoDB limit)
        for i in range(0, len(partitions), 25):
            batch = partitions[i:i + 25]

            response = dynamodb.batch_get_item(
                RequestItems={
                    BACKFILL_STATE_TABLE: {
                        "Keys": [{"partition_key": partition} for partition in batch]
                    }
                }
            )

            # Remove processed partitions
            for item in response.get("Responses", {}).get(BACKFILL_STATE_TABLE, []):
                unprocessed.discard(item["partition_key"])

        logger.info(f"Filtered: {len(partitions)} total -> {len(unprocessed)} unprocessed")

    except Exception as e:
        logger.error(f"Error filtering processed partitions: {e}", exc_info=True)
        # On error, return all partitions (better to reprocess than skip)
        return set(partitions)

    return unprocessed


def process_partition(partition_key: str, force_mode: bool = False, dry_run: bool = False):
    """
    Process a single Silver layer partition.

    Steps:
    1. Read Parquet file(s) from S3
    2. Extract unique companies
    3. Filter against DynamoDB cache
    4. Send missing companies to SQS
    5. Update processing state
    """
    logger.info(f"Processing partition: {partition_key}")

    # Step 1: Extract companies from Parquet
    unique_companies = extract_companies_from_partition(partition_key)

    if not unique_companies:
        logger.info(f"  No companies found in partition {partition_key}")
        metrics["partitions_scanned"] += 1
        # Mark as processed even if empty
        if not dry_run:
            mark_partition_processed(partition_key, companies_found=0, companies_queued=0)
        return

    logger.info(f"  Found {len(unique_companies)} unique companies in partition")
    metrics["companies_found"] += len(unique_companies)

    # Step 2: Filter against DynamoDB cache
    if force_mode:
        logger.info(f"  Force mode enabled: queuing all {len(unique_companies)} companies")
        companies_to_queue = unique_companies
    else:
        companies_to_queue = filter_cached_companies(unique_companies)
        cached_count = len(unique_companies) - len(companies_to_queue)
        logger.info(f"  After cache filter: {len(companies_to_queue)} to queue, {cached_count} cached")
        metrics["companies_cached"] += cached_count

    if not companies_to_queue:
        logger.info(f"  All companies already cached for partition {partition_key}")
        metrics["partitions_scanned"] += 1
        if not dry_run:
            mark_partition_processed(partition_key, len(unique_companies), 0)
        return

    # Step 3: Send to SQS
    if dry_run:
        logger.info(f"  DRY RUN: Would queue {len(companies_to_queue)} companies")
        metrics["companies_queued"] += len(companies_to_queue)
    else:
        sent_count = send_companies_to_sqs(companies_to_queue)
        logger.info(f"  Sent {sent_count} companies to SQS")
        metrics["companies_queued"] += sent_count

    # Step 4: Mark partition as processed
    if not dry_run:
        mark_partition_processed(partition_key, len(unique_companies), len(companies_to_queue))

    metrics["partitions_scanned"] += 1


def extract_companies_from_partition(partition_key: str) -> List[Dict]:
    """
    Extract unique companies from a Silver layer partition.

    Uses awswrangler to read only needed columns from Parquet files.

    Returns list of dicts: [{"company_id": "...", "company_url": "...", "company_name": "..."}]
    """
    import awswrangler as wr

    try:
        # S3 path
        s3_path = f"s3://{SILVER_BUCKET_NAME}/linkedin/{partition_key}/"

        # Read Parquet with only needed columns using awswrangler
        try:
            df = wr.s3.read_parquet(
                path=s3_path,
                columns=["company_id", "company_url", "company_name"]
            )
        except Exception as e:
            # Handle NoFilesFound or empty partitions gracefully
            if "No files Found" in str(e) or "NoFilesFound" in str(type(e).__name__):
                logger.info(f"No Parquet files found in partition {partition_key} - partition may be empty")
                return []
            # Re-raise other errors
            raise

        # Filter out rows where both company_id and company_url are null
        df = df[df["company_id"].notna() | df["company_url"].notna()]

        # Deduplicate by company_id (primary) or company_url (fallback)
        df = df.drop_duplicates(subset=["company_id"], keep="first")

        # Convert to list of dicts
        companies = []
        for _, row in df.iterrows():
            company = {
                "company_id": str(row["company_id"]) if row["company_id"] else None,
                "company_url": str(row["company_url"]) if row["company_url"] else None,
                "company_name": str(row["company_name"]) if row["company_name"] else None
            }

            # Skip if both ID and URL are None
            if company["company_id"] or company["company_url"]:
                companies.append(company)

        return companies

    except Exception as e:
        logger.error(f"Error extracting companies from partition {partition_key}: {e}", exc_info=True)
        return []


def filter_cached_companies(companies: List[Dict]) -> List[Dict]:
    """
    Filter out companies that are already in DynamoDB cache.

    Returns list of companies that need to be fetched.
    """
    if not companies:
        return []

    companies_to_fetch = []

    try:
        # Batch get from DynamoDB (100 items at a time - batch_get_item limit)
        for i in range(0, len(companies), 100):
            batch = companies[i:i + 100]

            # Build request (only for companies with company_id)
            keys = []
            for company in batch:
                if company.get("company_id"):
                    keys.append({"company_id": company["company_id"]})

            if not keys:
                # No company_ids in this batch, fetch all
                companies_to_fetch.extend(batch)
                continue

            # Query DynamoDB
            response = dynamodb.batch_get_item(
                RequestItems={
                    COMPANIES_STATUS_TABLE: {"Keys": keys}
                }
            )

            # Build set of cached company IDs
            cached_ids = {
                item["company_id"]
                for item in response.get("Responses", {}).get(COMPANIES_STATUS_TABLE, [])
            }

            # Filter batch
            for company in batch:
                company_id = company.get("company_id")
                if not company_id or company_id not in cached_ids:
                    companies_to_fetch.append(company)

        return companies_to_fetch

    except Exception as e:
        logger.error(f"Error filtering cached companies: {e}", exc_info=True)
        # On error, return all companies (better to duplicate than skip)
        return companies


def send_companies_to_sqs(companies: List[Dict]) -> int:
    """
    Send companies to SQS FIFO queue in batches.

    Returns count of successfully sent companies.
    """
    sent_count = 0

    try:
        # Send in batches of 10 (SQS FIFO limit)
        for i in range(0, len(companies), 10):
            batch = companies[i:i + 10]

            entries = []
            for idx, company in enumerate(batch):
                # Generate deduplication ID
                dedup_id = company.get("company_id") or str(hash(company.get("company_url", "")))

                message_body = {
                    "company_id": company.get("company_id"),
                    "company_url": company.get("company_url"),
                    "company_name": company.get("company_name"),
                    "source": "backfill_scanner",
                    "first_seen_at": datetime.now(timezone.utc).isoformat()
                }

                entries.append({
                    "Id": str(idx),
                    "MessageBody": json.dumps(message_body),
                    "MessageGroupId": "companies-fetch-group",
                    "MessageDeduplicationId": dedup_id
                })

            # Send batch to SQS
            response = sqs_client.send_message_batch(
                QueueUrl=COMPANIES_QUEUE_URL,
                Entries=entries
            )

            # Count successful sends
            successful = len(response.get("Successful", []))
            failed = len(response.get("Failed", []))

            sent_count += successful
            metrics["sqs_messages_sent"] += 1  # One batch sent

            if failed > 0:
                logger.warning(f"Failed to send {failed} messages in batch: {response.get('Failed')}")

        return sent_count

    except Exception as e:
        logger.error(f"Error sending companies to SQS: {e}", exc_info=True)
        return sent_count


def mark_partition_processed(partition_key: str, companies_found: int, companies_queued: int):
    """
    Mark a partition as processed in DynamoDB state table.
    """
    try:
        import time

        ttl = int(time.time()) + (90 * 24 * 60 * 60)  # 90 days

        backfill_state_table.put_item(
            Item={
                "partition_key": partition_key,
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "companies_found": companies_found,
                "companies_queued": companies_queued,
                "ttl": ttl
            }
        )

        logger.info(f"  Marked partition as processed: {partition_key}")

    except Exception as e:
        logger.error(f"Error marking partition as processed: {e}", exc_info=True)


def send_cloudwatch_metrics():
    """
    Send custom metrics to CloudWatch.
    """
    try:
        cloudwatch = boto3.client("cloudwatch")

        metric_data = [
            {
                "MetricName": "PartitionsScanned",
                "Value": metrics["partitions_scanned"],
                "Unit": "Count"
            },
            {
                "MetricName": "CompaniesFound",
                "Value": metrics["companies_found"],
                "Unit": "Count"
            },
            {
                "MetricName": "CompaniesAlreadyCached",
                "Value": metrics["companies_cached"],
                "Unit": "Count"
            },
            {
                "MetricName": "CompaniesQueued",
                "Value": metrics["companies_queued"],
                "Unit": "Count"
            }
        ]

        cloudwatch.put_metric_data(
            Namespace="CompaniesBackfill",
            MetricData=metric_data
        )

        logger.info("Sent custom metrics to CloudWatch")

    except Exception as e:
        logger.error(f"Error sending CloudWatch metrics: {e}", exc_info=True)
