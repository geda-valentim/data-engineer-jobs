"""
Lambda: InvokeEnrichment
Receives SQS messages with job data and starts Step Function executions.

NOTE: Lock acquisition and job status tracking are handled by the Step Function.
This Lambda only starts Step Function executions - all concurrency control
is managed via DynamoDB in the Step Function's AcquireLock state.
"""

import os
import json
import logging
from typing import Dict, Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
STEP_FUNCTION_ARN = os.environ.get("STEP_FUNCTION_ARN")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Step Functions client singleton
_sfn_client = None


def _get_sfn_client():
    """Get or create Step Functions client singleton."""
    global _sfn_client
    if _sfn_client is None:
        _sfn_client = boto3.client("stepfunctions", region_name=AWS_REGION)
    return _sfn_client


def process_sqs_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single SQS record containing job data.

    Starts a Step Function execution for the job. The Step Function handles:
    - Lock acquisition (semaphore-based concurrency control)
    - Job status tracking in DynamoDB
    - Pass execution (pass1, pass2, pass3)
    - Lock release

    Args:
        record: SQS record with job information in body

    Returns:
        Dict with processing result
    """
    try:
        # Parse SQS message body
        body = json.loads(record.get("body", "{}"))

        job_posting_id = body.get("job_posting_id")
        if not job_posting_id:
            logger.error("Missing job_posting_id in SQS message")
            return {"success": False, "error": "missing_job_posting_id"}

        # Extract job metadata
        job_data = {
            "job_posting_id": job_posting_id,
            "job_title": body.get("job_title"),
            "company_name": body.get("company_name"),
            "job_location": body.get("job_location"),
            "job_description": body.get("job_description"),
            "partition": body.get("partition", {}),
        }

        # Generate unique execution name (must be unique for Step Functions)
        message_id_suffix = record.get("messageId", "unknown")[:8]
        execution_name = f"job-{job_posting_id}-{message_id_suffix}"

        # Start Step Function execution
        # The Step Function handles lock acquisition, job status, and lock release
        sfn = _get_sfn_client()

        try:
            response = sfn.start_execution(
                stateMachineArn=STEP_FUNCTION_ARN,
                name=execution_name,
                input=json.dumps({
                    "job_data": job_data,
                    "execution_id": execution_name,
                }),
            )

            logger.info(f"Started Step Function for job {job_posting_id}: {response['executionArn']}")

            return {
                "success": True,
                "job_posting_id": job_posting_id,
                "execution_arn": response["executionArn"],
                "execution_name": execution_name,
            }

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")

            # Handle duplicate execution name (job already processing)
            if error_code == "ExecutionAlreadyExists":
                logger.warning(f"Execution already exists for job {job_posting_id}, skipping")
                return {
                    "success": True,  # Not a failure, just already processing
                    "job_posting_id": job_posting_id,
                    "error": "already_processing",
                    "execution_name": execution_name,
                }

            logger.error(f"Failed to start Step Function for {job_posting_id}: {e}")
            return {
                "success": False,
                "job_posting_id": job_posting_id,
                "error": str(e),
                "should_retry": True,
            }

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in SQS message: {e}")
        return {"success": False, "error": "invalid_json"}
    except Exception as e:
        logger.error(f"Unexpected error processing record: {e}")
        return {"success": False, "error": str(e)}


def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Process SQS batch of jobs to enrich.

    Starts Step Function executions for each job. The Step Function handles
    concurrency control via DynamoDB semaphore.

    Event format (SQS trigger):
    {
        "Records": [
            {
                "messageId": "...",
                "body": "{\"job_posting_id\": \"123\", ...}",
                ...
            }
        ]
    }

    Returns:
        Dict with batch processing results
    """
    logger.info(f"InvokeEnrichment started - {len(event.get('Records', []))} records")

    if not STEP_FUNCTION_ARN:
        raise ValueError("STEP_FUNCTION_ARN environment variable not set")

    records = event.get("Records", [])
    results = []
    successful = 0
    failed = 0

    for record in records:
        result = process_sqs_record(record)
        results.append(result)

        if result.get("success"):
            successful += 1
        else:
            failed += 1

    response = {
        "total_records": len(records),
        "successful": successful,
        "failed": failed,
        "results": results,
    }

    logger.info(f"Batch complete: {successful} started, {failed} failed")

    # Return batchItemFailures for SQS partial batch response
    # This allows SQS to retry failed messages
    if failed > 0:
        batch_failures = [
            {"itemIdentifier": records[i].get("messageId")}
            for i, r in enumerate(results)
            if r.get("should_retry")
        ]
        if batch_failures:
            response["batchItemFailures"] = batch_failures

    return response


if __name__ == "__main__":
    # Local testing
    from dotenv import load_dotenv
    load_dotenv()

    test_event = {
        "Records": [
            {
                "messageId": "test-123",
                "body": json.dumps({
                    "job_posting_id": "4325917532",
                    "job_title": "Data Engineer",
                    "company_name": "Test Company",
                    "job_location": "Remote",
                    "job_description": "Test description...",
                    "partition": {"year": "2025", "month": "12", "day": "05", "hour": "10"},
                }),
            }
        ]
    }

    result = handler(test_event, None)
    print(json.dumps(result, indent=2))
