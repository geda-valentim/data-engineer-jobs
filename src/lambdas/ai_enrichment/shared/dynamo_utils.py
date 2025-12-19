"""
DynamoDB utilities for AI Enrichment pipeline.
Handles semaphore-based concurrency control and job status tracking.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()

# Environment variables
DYNAMO_SEMAPHORE_TABLE = os.environ.get("DYNAMO_SEMAPHORE_TABLE", "AIEnrichmentSemaphore")
DYNAMO_STATUS_TABLE = os.environ.get("DYNAMO_STATUS_TABLE", "AIEnrichmentStatus")
MAX_CONCURRENT_EXECUTIONS = int(os.environ.get("MAX_CONCURRENT_EXECUTIONS", "5"))
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# DynamoDB client singleton
_dynamodb_client = None
_dynamodb_resource = None


def _get_dynamodb_client():
    """Get or create DynamoDB client singleton."""
    global _dynamodb_client
    if _dynamodb_client is None:
        _dynamodb_client = boto3.client("dynamodb", region_name=AWS_REGION)
    return _dynamodb_client


def _get_dynamodb_resource():
    """Get or create DynamoDB resource singleton."""
    global _dynamodb_resource
    if _dynamodb_resource is None:
        _dynamodb_resource = boto3.resource("dynamodb", region_name=AWS_REGION)
    return _dynamodb_resource


# ═══════════════════════════════════════════════════════════════════════════
# Semaphore Functions (Concurrency Control)
# ═══════════════════════════════════════════════════════════════════════════


def acquire_lock(execution_id: str, lock_name: str = "ProcessingLock") -> bool:
    """
    Acquire a semaphore lock for concurrent execution control.

    Uses DynamoDB conditional update to atomically increment counter
    only if below max limit.

    Args:
        execution_id: Unique execution ID (e.g., Step Function execution ARN)
        lock_name: Name of the lock (default: "ProcessingLock")

    Returns:
        True if lock acquired, False if at capacity

    Raises:
        ClientError: For DynamoDB errors other than condition failures
    """
    client = _get_dynamodb_client()
    now = datetime.now(timezone.utc).isoformat()

    try:
        # Atomic conditional update: increment only if under limit
        client.update_item(
            TableName=DYNAMO_SEMAPHORE_TABLE,
            Key={"LockName": {"S": lock_name}},
            UpdateExpression="SET currentlockcount = if_not_exists(currentlockcount, :zero) + :one, #execId = :timestamp",
            ConditionExpression="attribute_not_exists(currentlockcount) OR currentlockcount < :maxcount",
            ExpressionAttributeNames={
                "#execId": execution_id,  # Store execution ID as attribute
            },
            ExpressionAttributeValues={
                ":zero": {"N": "0"},
                ":one": {"N": "1"},
                ":maxcount": {"N": str(MAX_CONCURRENT_EXECUTIONS)},
                ":timestamp": {"S": now},
            },
        )
        logger.info(f"Lock acquired for {execution_id}")
        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.warning(f"Lock at capacity ({MAX_CONCURRENT_EXECUTIONS}), cannot acquire for {execution_id}")
            return False
        raise


def release_lock(execution_id: str, lock_name: str = "ProcessingLock") -> bool:
    """
    Release a semaphore lock.

    Atomically decrements counter and removes execution ID attribute.

    Args:
        execution_id: Unique execution ID that holds the lock
        lock_name: Name of the lock (default: "ProcessingLock")

    Returns:
        True if lock released successfully, False if execution wasn't holding lock
    """
    client = _get_dynamodb_client()

    try:
        # Atomic update: decrement counter and remove execution ID
        client.update_item(
            TableName=DYNAMO_SEMAPHORE_TABLE,
            Key={"LockName": {"S": lock_name}},
            UpdateExpression="SET currentlockcount = currentlockcount - :one REMOVE #execId",
            ConditionExpression="attribute_exists(#execId) AND currentlockcount > :zero",
            ExpressionAttributeNames={
                "#execId": execution_id,
            },
            ExpressionAttributeValues={
                ":one": {"N": "1"},
                ":zero": {"N": "0"},
            },
        )
        logger.info(f"Lock released for {execution_id}")
        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.warning(f"Lock not held by {execution_id}, nothing to release")
            return False
        raise


def get_lock_status(lock_name: str = "ProcessingLock") -> Dict[str, Any]:
    """
    Get current lock status.

    Args:
        lock_name: Name of the lock

    Returns:
        Dict with current_count, max_count, and active_executions
    """
    client = _get_dynamodb_client()

    try:
        response = client.get_item(
            TableName=DYNAMO_SEMAPHORE_TABLE,
            Key={"LockName": {"S": lock_name}},
        )

        if "Item" not in response:
            return {
                "current_count": 0,
                "max_count": MAX_CONCURRENT_EXECUTIONS,
                "active_executions": [],
            }

        item = response["Item"]
        current_count = int(item.get("currentlockcount", {}).get("N", "0"))

        # Extract active execution IDs (all string attributes except LockName and counts)
        active_executions = []
        for key, value in item.items():
            if key not in ["LockName", "currentlockcount", "maxlockcount"] and "S" in value:
                active_executions.append({"execution_id": key, "acquired_at": value["S"]})

        return {
            "current_count": current_count,
            "max_count": MAX_CONCURRENT_EXECUTIONS,
            "active_executions": active_executions,
        }

    except ClientError as e:
        logger.error(f"Error getting lock status: {e}")
        raise


def cleanup_orphaned_locks(lock_name: str = "ProcessingLock", execution_ids: List[str] = None) -> int:
    """
    Clean up orphaned locks from failed executions.

    Args:
        lock_name: Name of the lock
        execution_ids: List of execution IDs to remove (if None, removes all)

    Returns:
        Number of locks cleaned up
    """
    if not execution_ids:
        return 0

    client = _get_dynamodb_client()
    cleaned = 0

    for exec_id in execution_ids:
        if release_lock(exec_id, lock_name):
            cleaned += 1
            logger.info(f"Cleaned up orphaned lock for {exec_id}")

    return cleaned


# ═══════════════════════════════════════════════════════════════════════════
# Job Status Tracking Functions
# ═══════════════════════════════════════════════════════════════════════════

# Valid status values
STATUS_PENDING = "PENDING"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"


def get_job_status(job_posting_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the current status of a job's enrichment processing.

    Args:
        job_posting_id: The job posting ID

    Returns:
        Dict with pass1, pass2, pass3 status and metadata, or None if not found
    """
    table = _get_dynamodb_resource().Table(DYNAMO_STATUS_TABLE)

    try:
        response = table.get_item(Key={"job_posting_id": job_posting_id})

        if "Item" not in response:
            return None

        return response["Item"]

    except ClientError as e:
        logger.error(f"Error getting job status for {job_posting_id}: {e}")
        raise


def create_job_status(job_posting_id: str, execution_id: str = None) -> Dict[str, Any]:
    """
    Create initial job status record.

    Args:
        job_posting_id: The job posting ID
        execution_id: Optional execution ID processing this job

    Returns:
        The created status record
    """
    table = _get_dynamodb_resource().Table(DYNAMO_STATUS_TABLE)
    now = datetime.now(timezone.utc).isoformat()

    item = {
        "job_posting_id": job_posting_id,
        "pass1": {"status": STATUS_PENDING},
        "pass2": {"status": STATUS_PENDING},
        "pass3": {"status": STATUS_PENDING},
        "overallStatus": STATUS_PENDING,
        "createdAt": now,
        "updatedAt": now,
    }

    if execution_id:
        item["currentExecutionId"] = execution_id

    try:
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(job_posting_id)",
        )
        logger.info(f"Created job status for {job_posting_id}")
        return item

    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            # Already exists, return existing
            return get_job_status(job_posting_id)
        raise


def update_pass_status(
    job_posting_id: str,
    pass_name: str,
    status: str,
    execution_id: str = None,
    model: str = None,
    cost_usd: float = None,
    error: str = None,
) -> Dict[str, Any]:
    """
    Update the status of a specific pass.

    Args:
        job_posting_id: The job posting ID
        pass_name: 'pass1', 'pass2', or 'pass3'
        status: STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_COMPLETED, or STATUS_FAILED
        execution_id: Optional execution ID
        model: Optional model ID used
        cost_usd: Optional cost in USD
        error: Optional error message (for FAILED status)

    Returns:
        Updated status record
    """
    table = _get_dynamodb_resource().Table(DYNAMO_STATUS_TABLE)
    now = datetime.now(timezone.utc).isoformat()

    # Build the pass status object
    pass_status = {"status": status}

    if status == STATUS_IN_PROGRESS:
        pass_status["startedAt"] = now
    elif status == STATUS_COMPLETED:
        pass_status["completedAt"] = now
    elif status == STATUS_FAILED:
        pass_status["failedAt"] = now
        if error:
            pass_status["error"] = error

    if execution_id:
        pass_status["executionId"] = execution_id
    if model:
        pass_status["model"] = model
    if cost_usd is not None:
        pass_status["cost_usd"] = str(cost_usd)

    # Build update expression
    update_expr = f"SET #{pass_name} = :passStatus, updatedAt = :now"
    expr_names = {f"#{pass_name}": pass_name}
    expr_values = {
        ":passStatus": pass_status,
        ":now": now,
    }

    # Update overall status based on pass status
    if pass_name == "pass3" and status == STATUS_COMPLETED:
        update_expr += ", overallStatus = :completed"
        expr_values[":completed"] = STATUS_COMPLETED
    elif status == STATUS_IN_PROGRESS:
        update_expr += ", overallStatus = :inProgress"
        expr_values[":inProgress"] = STATUS_IN_PROGRESS
    elif status == STATUS_FAILED:
        update_expr += ", overallStatus = :failed"
        expr_values[":failed"] = STATUS_FAILED

    try:
        response = table.update_item(
            Key={"job_posting_id": job_posting_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW",
        )
        logger.info(f"Updated {pass_name} status to {status} for {job_posting_id}")
        return response.get("Attributes", {})

    except ClientError as e:
        logger.error(f"Error updating pass status: {e}")
        raise


def mark_pass_started(
    job_posting_id: str,
    pass_name: str,
    execution_id: str = None,
    model: str = None,
) -> Dict[str, Any]:
    """
    Mark a pass as started (IN_PROGRESS).

    Args:
        job_posting_id: The job posting ID
        pass_name: 'pass1', 'pass2', or 'pass3'
        execution_id: Optional execution ID
        model: Optional model ID

    Returns:
        Updated status record
    """
    return update_pass_status(
        job_posting_id=job_posting_id,
        pass_name=pass_name,
        status=STATUS_IN_PROGRESS,
        execution_id=execution_id,
        model=model,
    )


def mark_pass_completed(
    job_posting_id: str,
    pass_name: str,
    execution_id: str = None,
    model: str = None,
    cost_usd: float = None,
) -> Dict[str, Any]:
    """
    Mark a pass as completed.

    Args:
        job_posting_id: The job posting ID
        pass_name: 'pass1', 'pass2', or 'pass3'
        execution_id: Optional execution ID
        model: Optional model ID
        cost_usd: Optional cost in USD

    Returns:
        Updated status record
    """
    return update_pass_status(
        job_posting_id=job_posting_id,
        pass_name=pass_name,
        status=STATUS_COMPLETED,
        execution_id=execution_id,
        model=model,
        cost_usd=cost_usd,
    )


def mark_pass_failed(
    job_posting_id: str,
    pass_name: str,
    error: str,
    execution_id: str = None,
) -> Dict[str, Any]:
    """
    Mark a pass as failed.

    Args:
        job_posting_id: The job posting ID
        pass_name: 'pass1', 'pass2', or 'pass3'
        error: Error message
        execution_id: Optional execution ID

    Returns:
        Updated status record
    """
    return update_pass_status(
        job_posting_id=job_posting_id,
        pass_name=pass_name,
        status=STATUS_FAILED,
        execution_id=execution_id,
        error=error,
    )


def get_pending_jobs(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get jobs that are pending or partially processed.

    Uses GSI 'status-index' on overallStatus to avoid expensive table scans.
    Queries for PENDING, IN_PROGRESS, and FAILED statuses.

    Args:
        limit: Maximum number of jobs to return

    Returns:
        List of job status records
    """
    table = _get_dynamodb_resource().Table(DYNAMO_STATUS_TABLE)
    pending_jobs = []

    # Query each non-completed status using GSI
    non_completed_statuses = [STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_FAILED]

    try:
        for status in non_completed_statuses:
            if len(pending_jobs) >= limit:
                break

            remaining = limit - len(pending_jobs)
            response = table.query(
                IndexName="status-index",
                KeyConditionExpression="overallStatus = :status",
                ExpressionAttributeValues={":status": status},
                Limit=remaining,
            )
            pending_jobs.extend(response.get("Items", []))

        return pending_jobs[:limit]

    except ClientError as e:
        logger.error(f"Error getting pending jobs: {e}")
        raise


def should_run_pass(job_status: Dict[str, Any], pass_name: str) -> bool:
    """
    Determine if a pass should be run based on current status.

    Args:
        job_status: Job status record
        pass_name: 'pass1', 'pass2', or 'pass3'

    Returns:
        True if the pass should be run
    """
    if not job_status:
        return pass_name == "pass1"

    pass_info = job_status.get(pass_name, {})
    status = pass_info.get("status", STATUS_PENDING)

    # Don't re-run completed passes
    if status == STATUS_COMPLETED:
        return False

    # For pass2 and pass3, check dependencies
    if pass_name == "pass2":
        pass1_status = job_status.get("pass1", {}).get("status")
        return pass1_status == STATUS_COMPLETED

    if pass_name == "pass3":
        pass1_status = job_status.get("pass1", {}).get("status")
        pass2_status = job_status.get("pass2", {}).get("status")
        return pass1_status == STATUS_COMPLETED and pass2_status == STATUS_COMPLETED

    return True
