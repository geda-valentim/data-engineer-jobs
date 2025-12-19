"""
Lambda handler for LinkedIn Companies Bronze to Silver transformation.

This handler processes company JSON files from the Bronze layer and
writes consolidated Parquet files to the Silver layer.

Modes:
- discover: Find companies in Bronze, send batches to SQS
- batch: Process specific company_ids (from SQS or direct invocation)
- sqs: Process SQS event records (automatic mode detection)
- full: Process all companies directly (for testing/manual runs)
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import boto3
import pyarrow as pa

# Handle imports for both Lambda (flat structure) and local execution (package structure)
try:
    # Lambda execution - flat structure
    from schema import get_schema, get_partition_columns
    from transformer import transform_company
    from shared.s3_utils import (
        list_company_partitions,
        list_company_snapshots,
        read_company_json,
        iter_companies_from_s3,
        write_silver_parquet,
    )
except ImportError:
    # Local execution - package structure
    from .schema import get_schema, get_partition_columns
    from .transformer import transform_company
    from ..shared.s3_utils import (
        list_company_partitions,
        list_company_snapshots,
        read_company_json,
        iter_companies_from_s3,
        write_silver_parquet,
    )


# Environment variables
BRONZE_BUCKET = os.environ.get("BRONZE_BUCKET", "data-engineer-jobs-bronze")
SILVER_BUCKET = os.environ.get("SILVER_BUCKET", "data-engineer-jobs-silver")
BRONZE_PREFIX = os.environ.get("BRONZE_PREFIX", "linkedin_companies/")
SILVER_PREFIX = os.environ.get("SILVER_PREFIX", "linkedin_companies/")
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "")
MAX_COMPANIES_PER_BATCH = int(os.environ.get("MAX_COMPANIES_PER_BATCH", "200"))

# SQS client (lazy initialization)
_sqs_client = None


def get_sqs_client():
    """Get or create SQS client."""
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client("sqs")
    return _sqs_client


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for Bronze to Silver transformation.

    Automatically detects mode based on event structure:
    - SQS trigger: event contains "Records" with SQS messages
    - Direct invocation: event contains "mode" field

    Args:
        event: Lambda event (SQS or direct)
        context: Lambda context

    Returns:
        Result dictionary with status and stats
    """
    processed_at = datetime.now(timezone.utc)

    # Detect SQS trigger
    if "Records" in event:
        return handle_sqs_event(event, processed_at)

    # Direct invocation - check mode
    mode = event.get("mode", os.environ.get("MODE", "full"))
    print(f"Starting Bronze to Silver transformation - mode: {mode}")

    try:
        if mode == "discover":
            return discover_companies(event)
        elif mode == "batch":
            return process_batch(event, processed_at)
        else:  # full
            return process_full(event, processed_at)

    except Exception as e:
        print(f"Error in handler: {e}")
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "error": str(e),
            "mode": mode,
        }


def handle_sqs_event(event: dict[str, Any], processed_at: datetime) -> dict[str, Any]:
    """
    Handle SQS trigger event with batch item failure reporting.

    Args:
        event: SQS event with Records
        processed_at: Processing timestamp

    Returns:
        Response with batchItemFailures for partial batch response
    """
    records = event.get("Records", [])
    print(f"Processing {len(records)} SQS messages")

    batch_item_failures = []

    for record in records:
        message_id = record.get("messageId", "unknown")

        try:
            # Parse message body
            body = json.loads(record.get("body", "{}"))
            company_ids = body.get("company_ids", [])

            if not company_ids:
                print(f"Message {message_id}: No company_ids, skipping")
                continue

            print(f"Message {message_id}: Processing {len(company_ids)} companies")

            # Process batch
            result = process_batch({"company_ids": company_ids}, processed_at)

            if result.get("statusCode") != 200:
                raise Exception(f"Batch processing failed: {result.get('error')}")

            print(f"Message {message_id}: Success - {result.get('processed')} processed")

        except Exception as e:
            print(f"Message {message_id}: Error - {e}")
            batch_item_failures.append({"itemIdentifier": message_id})

    # Return partial batch response
    return {"batchItemFailures": batch_item_failures}


def discover_companies(event: dict[str, Any]) -> dict[str, Any]:
    """
    Discover company partitions and send batches to SQS.

    Args:
        event: Event with optional max_partitions

    Returns:
        Result with discovery stats
    """
    max_partitions = event.get("max_partitions")

    # List all company partitions
    company_ids = list_company_partitions(
        bucket=BRONZE_BUCKET,
        prefix=BRONZE_PREFIX,
        max_partitions=max_partitions,
    )

    print(f"Discovered {len(company_ids)} company partitions")

    # If no SQS queue configured, just return the list
    if not SQS_QUEUE_URL:
        return {
            "statusCode": 200,
            "mode": "discover",
            "company_count": len(company_ids),
            "company_ids": company_ids,
            "message": "No SQS queue configured, returning company_ids directly",
        }

    # Split into batches and send to SQS
    batches_sent = 0
    total_companies = 0
    sqs = get_sqs_client()

    for i in range(0, len(company_ids), MAX_COMPANIES_PER_BATCH):
        batch = company_ids[i:i + MAX_COMPANIES_PER_BATCH]

        message_body = json.dumps({
            "company_ids": batch,
            "batch_index": i // MAX_COMPANIES_PER_BATCH,
            "total_batches": (len(company_ids) + MAX_COMPANIES_PER_BATCH - 1) // MAX_COMPANIES_PER_BATCH,
        })

        # Send to FIFO queue
        sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=message_body,
            MessageGroupId="companies-batch",
            MessageDeduplicationId=f"batch-{uuid4()}",
        )

        batches_sent += 1
        total_companies += len(batch)

    print(f"Sent {batches_sent} batches ({total_companies} companies) to SQS")

    return {
        "statusCode": 200,
        "mode": "discover",
        "company_count": len(company_ids),
        "batches_sent": batches_sent,
        "batch_size": MAX_COMPANIES_PER_BATCH,
        "queue_url": SQS_QUEUE_URL,
    }


def process_batch(event: dict[str, Any], processed_at: datetime) -> dict[str, Any]:
    """
    Process a batch of specific company IDs.

    Args:
        event: Event with company_ids list
        processed_at: Processing timestamp

    Returns:
        Result with processing stats
    """
    company_ids = event.get("company_ids", [])
    if not company_ids:
        return {
            "statusCode": 400,
            "error": "No company_ids provided for batch mode",
        }

    print(f"Processing batch of {len(company_ids)} companies")

    # Collect transformed rows
    rows = []
    errors = []

    for company_id in company_ids:
        try:
            snapshots = list_company_snapshots(company_id, BRONZE_BUCKET, BRONZE_PREFIX)

            if not snapshots:
                errors.append({"company_id": company_id, "error": "No snapshots found"})
                continue

            # Process latest snapshot only
            latest_snapshot = sorted(snapshots)[-1]
            data, filename = read_company_json(
                company_id, latest_snapshot, BRONZE_BUCKET, BRONZE_PREFIX
            )
            row = transform_company(data, filename, processed_at)
            rows.append(row)

        except Exception as e:
            errors.append({"company_id": company_id, "error": str(e)})
            print(f"Error processing company {company_id}: {e}")

    if not rows:
        return {
            "statusCode": 200,
            "mode": "batch",
            "processed": 0,
            "errors": len(errors),
            "error_details": errors[:10] if errors else [],
        }

    # Convert to PyArrow table and write
    output_path = write_companies_to_silver(rows, processed_at)

    return {
        "statusCode": 200,
        "mode": "batch",
        "processed": len(rows),
        "errors": len(errors),
        "error_details": errors[:10] if errors else [],
        "output_path": output_path,
    }


def process_full(event: dict[str, Any], processed_at: datetime) -> dict[str, Any]:
    """
    Process all companies from Bronze to Silver (for testing/manual runs).

    Args:
        event: Event with optional max_companies
        processed_at: Processing timestamp

    Returns:
        Result with processing stats
    """
    max_companies = event.get("max_companies", MAX_COMPANIES_PER_BATCH)

    print(f"Processing up to {max_companies} companies (full mode)")

    # Collect transformed rows
    rows = []
    errors = []

    for data, filename in iter_companies_from_s3(
        bucket=BRONZE_BUCKET,
        prefix=BRONZE_PREFIX,
        max_companies=max_companies,
    ):
        try:
            row = transform_company(data, filename, processed_at)
            rows.append(row)

            if len(rows) % 100 == 0:
                print(f"Processed {len(rows)} companies...")

        except Exception as e:
            company_id = data.get("company_id", "unknown")
            errors.append({"company_id": company_id, "error": str(e)})
            print(f"Error transforming company {company_id}: {e}")

    if not rows:
        return {
            "statusCode": 200,
            "mode": "full",
            "processed": 0,
            "errors": len(errors),
            "error_details": errors[:10] if errors else [],
        }

    # Convert to PyArrow table and write
    output_path = write_companies_to_silver(rows, processed_at)

    return {
        "statusCode": 200,
        "mode": "full",
        "processed": len(rows),
        "errors": len(errors),
        "error_details": errors[:10] if errors else [],
        "output_path": output_path,
    }


def write_companies_to_silver(
    rows: list[dict[str, Any]],
    processed_at: datetime,
) -> str:
    """
    Convert rows to PyArrow table and write to Silver layer.

    Args:
        rows: List of transformed company dictionaries
        processed_at: Processing timestamp

    Returns:
        Output path string
    """
    schema = get_schema()
    partition_cols = get_partition_columns()

    # Build column arrays
    arrays = {}
    for field in schema:
        col_name = field.name
        values = [row.get(col_name) for row in rows]
        arrays[col_name] = values

    # Create PyArrow table
    table = pa.table(arrays, schema=schema)

    print(f"Writing {len(rows)} rows to Silver layer (partitioned by {partition_cols})")

    # Write to S3
    output_path = write_silver_parquet(
        table=table,
        output_path=SILVER_PREFIX,
        partition_cols=partition_cols,
        bucket=SILVER_BUCKET,
    )

    print(f"Wrote Parquet to {output_path}")
    return output_path


# For local testing
if __name__ == "__main__":
    import sys

    # Test with discover mode
    if len(sys.argv) > 1 and sys.argv[1] == "discover":
        result = handler({"mode": "discover", "max_partitions": 10}, None)
        print(json.dumps(result, indent=2, default=str))
    else:
        # Test with a small batch
        result = handler({"mode": "full", "max_companies": 5}, None)
        print(json.dumps(result, indent=2, default=str))
