"""Shared utilities for AI Enrichment Lambdas"""

from .s3_utils import (
    get_silver_path,
    get_silver_ai_path,
    read_partition,
    write_partition,
    list_silver_partitions,
    list_silver_ai_partitions,
    # Bronze output functions
    get_model_short_name,
    get_bronze_path,
    write_bronze_result,
    check_job_processed,
    read_bronze_result,
    list_bronze_jobs,
)

from .dynamo_utils import (
    # Semaphore functions
    acquire_lock,
    release_lock,
    get_lock_status,
    cleanup_orphaned_locks,
    # Job status tracking
    get_job_status,
    create_job_status,
    update_pass_status,
    mark_pass_started,
    mark_pass_completed,
    mark_pass_failed,
    get_pending_jobs,
    should_run_pass,
    # Status constants
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_FAILED,
)

__all__ = [
    # S3 utils - Silver
    "get_silver_path",
    "get_silver_ai_path",
    "read_partition",
    "write_partition",
    "list_silver_partitions",
    "list_silver_ai_partitions",
    # S3 utils - Bronze
    "get_model_short_name",
    "get_bronze_path",
    "write_bronze_result",
    "check_job_processed",
    "read_bronze_result",
    "list_bronze_jobs",
    # DynamoDB - Semaphore
    "acquire_lock",
    "release_lock",
    "get_lock_status",
    "cleanup_orphaned_locks",
    # DynamoDB - Job status
    "get_job_status",
    "create_job_status",
    "update_pass_status",
    "mark_pass_started",
    "mark_pass_completed",
    "mark_pass_failed",
    "get_pending_jobs",
    "should_run_pass",
    # Status constants
    "STATUS_PENDING",
    "STATUS_IN_PROGRESS",
    "STATUS_COMPLETED",
    "STATUS_FAILED",
]
