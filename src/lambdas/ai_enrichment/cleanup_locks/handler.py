"""
Lambda: CleanupLocks
EventBridge-triggered Lambda that cleans up orphaned semaphore locks
from failed or stuck Step Function executions.
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

import boto3
from botocore.exceptions import ClientError

# Handle both Lambda and local testing imports
try:
    from ..shared.dynamo_utils import (
        get_lock_status,
        release_lock,
        STATUS_IN_PROGRESS,
        STATUS_FAILED,
    )
except ImportError:
    from shared.dynamo_utils import (
        get_lock_status,
        release_lock,
        STATUS_IN_PROGRESS,
        STATUS_FAILED,
    )

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
STEP_FUNCTION_ARN = os.environ.get("STEP_FUNCTION_ARN")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
LOCK_TIMEOUT_MINUTES = int(os.environ.get("LOCK_TIMEOUT_MINUTES", "30"))

# Step Functions client singleton
_sfn_client = None


def _get_sfn_client():
    """Get or create Step Functions client singleton."""
    global _sfn_client
    if _sfn_client is None:
        _sfn_client = boto3.client("stepfunctions", region_name=AWS_REGION)
    return _sfn_client


def get_execution_status(execution_name: str) -> Dict[str, Any]:
    """
    Get the status of a Step Function execution.

    Args:
        execution_name: Name of the execution

    Returns:
        Dict with status info or None if not found
    """
    if not STEP_FUNCTION_ARN:
        return None

    sfn = _get_sfn_client()

    try:
        # Build execution ARN from state machine ARN and execution name
        # ARN format: arn:aws:states:region:account:stateMachine:name
        # Execution ARN: arn:aws:states:region:account:execution:stateMachine:executionName
        parts = STEP_FUNCTION_ARN.split(":")
        execution_arn = f"arn:aws:states:{parts[3]}:{parts[4]}:execution:{parts[6]}:{execution_name}"

        response = sfn.describe_execution(executionArn=execution_arn)

        return {
            "status": response["status"],
            "start_date": response.get("startDate"),
            "stop_date": response.get("stopDate"),
        }

    except ClientError as e:
        if e.response["Error"]["Code"] == "ExecutionDoesNotExist":
            return {"status": "NOT_FOUND"}
        logger.error(f"Error getting execution status for {execution_name}: {e}")
        return None


def is_lock_orphaned(execution_id: str, acquired_at: str) -> bool:
    """
    Determine if a lock is orphaned (execution finished or timed out).

    Args:
        execution_id: The execution ID holding the lock
        acquired_at: ISO timestamp when lock was acquired

    Returns:
        True if lock should be cleaned up
    """
    # Check if lock has timed out
    try:
        acquired_time = datetime.fromisoformat(acquired_at.replace("Z", "+00:00"))
        timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=LOCK_TIMEOUT_MINUTES)

        if acquired_time < timeout_threshold:
            logger.info(f"Lock {execution_id} timed out (acquired at {acquired_at})")
            return True
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not parse acquired_at timestamp: {acquired_at}, error: {e}")

    # Check Step Function execution status
    exec_status = get_execution_status(execution_id)

    if exec_status is None:
        # Could not determine status, don't clean up
        return False

    if exec_status["status"] == "NOT_FOUND":
        logger.info(f"Execution {execution_id} not found, lock is orphaned")
        return True

    if exec_status["status"] in ["FAILED", "TIMED_OUT", "ABORTED"]:
        logger.info(f"Execution {execution_id} has status {exec_status['status']}, lock is orphaned")
        return True

    if exec_status["status"] == "SUCCEEDED":
        # Successful execution should have released lock, but clean up just in case
        logger.info(f"Execution {execution_id} succeeded but lock still held, cleaning up")
        return True

    # Status is RUNNING or PENDING, lock is valid
    return False


def cleanup_orphaned_locks() -> Dict[str, Any]:
    """
    Find and clean up all orphaned locks.

    Returns:
        Dict with cleanup results
    """
    lock_status = get_lock_status()
    active_executions = lock_status.get("active_executions", [])

    logger.info(f"Checking {len(active_executions)} active locks for orphans")

    cleaned = 0
    errors = 0
    checked = 0

    for exec_info in active_executions:
        execution_id = exec_info.get("execution_id")
        acquired_at = exec_info.get("acquired_at")

        if not execution_id:
            continue

        checked += 1

        try:
            if is_lock_orphaned(execution_id, acquired_at):
                if release_lock(execution_id):
                    cleaned += 1
                    logger.info(f"Cleaned up orphaned lock for {execution_id}")
                else:
                    errors += 1
                    logger.warning(f"Failed to release lock for {execution_id}")
        except Exception as e:
            errors += 1
            logger.error(f"Error checking/cleaning lock for {execution_id}: {e}")

    return {
        "checked": checked,
        "cleaned": cleaned,
        "errors": errors,
        "remaining_locks": lock_status.get("current_count", 0) - cleaned,
    }


def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    EventBridge-triggered cleanup handler.

    Runs periodically to clean up orphaned locks from failed executions.

    Event format (EventBridge scheduled):
    {
        "source": "aws.events",
        "detail-type": "Scheduled Event",
        ...
    }

    Returns:
        Dict with cleanup results
    """
    logger.info("CleanupLocks started")
    logger.info(f"Lock timeout: {LOCK_TIMEOUT_MINUTES} minutes")

    # Get current lock status before cleanup
    initial_status = get_lock_status()
    logger.info(f"Initial lock status: {initial_status['current_count']}/{initial_status['max_count']} locks")

    # Perform cleanup
    results = cleanup_orphaned_locks()

    # Get status after cleanup
    final_status = get_lock_status()

    response = {
        "initial_locks": initial_status["current_count"],
        "final_locks": final_status["current_count"],
        "cleaned": results["cleaned"],
        "checked": results["checked"],
        "errors": results["errors"],
    }

    logger.info(f"Cleanup complete: {results['cleaned']} locks cleaned, {results['errors']} errors")

    return response


if __name__ == "__main__":
    # Local testing
    from dotenv import load_dotenv
    load_dotenv()

    result = handler({}, None)
    print(result)
