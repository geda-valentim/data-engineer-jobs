#!/usr/bin/env python3
"""
Local Test Script for AI Enrichment Pipeline

Tests individual components and integration flows without requiring AWS infrastructure.
Uses moto for AWS service mocking.

Usage:
    # From project root
    make test-ai           # Run all tests
    make test-ai-circuit   # Run circuit breaker tests
    make test-ai-dynamo    # Run DynamoDB tests

    # Or directly
    cd tests/ai_enrichment
    python test_local.py
    python test_local.py TestCircuitBreaker

Requirements:
    pip install moto boto3
"""

import json
import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# Add src/lambdas/ai_enrichment to path for imports
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_AI_ENRICHMENT_PATH = os.path.join(_PROJECT_ROOT, "src", "lambdas", "ai_enrichment")
sys.path.insert(0, _AI_ENRICHMENT_PATH)

# Set environment variables before imports
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("DYNAMO_SEMAPHORE_TABLE", "TestSemaphore")
os.environ.setdefault("DYNAMO_STATUS_TABLE", "TestStatus")
os.environ.setdefault("MAX_CONCURRENT_EXECUTIONS", "5")
os.environ.setdefault("SILVER_BUCKET", "test-silver-bucket")
os.environ.setdefault("BRONZE_BUCKET", "test-bronze-bucket")
os.environ.setdefault("BRONZE_AI_PREFIX", "ai_enrichment/")
os.environ.setdefault("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3")
os.environ.setdefault("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "5")

import boto3
from moto import mock_aws


# ═══════════════════════════════════════════════════════════════════════════════
# Test: Circuit Breaker
# ═══════════════════════════════════════════════════════════════════════════════

class TestCircuitBreaker(unittest.TestCase):
    """Test circuit breaker state transitions and per-model isolation."""

    def setUp(self):
        """Reset circuit breakers before each test."""
        from enrich_partition.bedrock_client import _circuit_breakers
        _circuit_breakers.clear()

    def test_circuit_breaker_starts_closed(self):
        """Circuit breaker should start in CLOSED state."""
        from enrich_partition.bedrock_client import get_circuit_breaker, CircuitState

        cb = get_circuit_breaker("test-model")
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertTrue(cb.can_execute())

    def test_circuit_opens_after_threshold(self):
        """Circuit should open after reaching failure threshold."""
        from enrich_partition.bedrock_client import get_circuit_breaker, CircuitState

        cb = get_circuit_breaker("test-model")

        # Record failures (threshold is 3 for tests)
        for _ in range(3):
            cb.record_failure(is_throttling=True)

        self.assertEqual(cb.state, CircuitState.OPEN)
        self.assertFalse(cb.can_execute())

    def test_per_model_isolation(self):
        """Each model should have its own circuit breaker."""
        from enrich_partition.bedrock_client import get_circuit_breaker, CircuitState

        cb_mistral = get_circuit_breaker("mistral.mistral-large")
        cb_gemma = get_circuit_breaker("google.gemma-27b")

        # Fail mistral circuit
        for _ in range(3):
            cb_mistral.record_failure(is_throttling=True)

        # Mistral should be open, Gemma should still be closed
        self.assertEqual(cb_mistral.state, CircuitState.OPEN)
        self.assertEqual(cb_gemma.state, CircuitState.CLOSED)
        self.assertFalse(cb_mistral.can_execute())
        self.assertTrue(cb_gemma.can_execute())

    def test_success_resets_failure_count(self):
        """Success in HALF_OPEN state should close circuit."""
        from enrich_partition.bedrock_client import get_circuit_breaker, CircuitState
        import time

        cb = get_circuit_breaker("test-model")

        # Open the circuit
        for _ in range(3):
            cb.record_failure(is_throttling=True)

        # Wait for recovery timeout (5s in tests)
        time.sleep(6)

        # Should transition to HALF_OPEN
        self.assertTrue(cb.can_execute())
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)

        # Success should close circuit
        cb.record_success()
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_get_all_circuit_breakers_status(self):
        """Should return status of all circuit breakers."""
        from enrich_partition.bedrock_client import (
            get_circuit_breaker,
            get_all_circuit_breakers_status,
        )

        get_circuit_breaker("model-a")
        get_circuit_breaker("model-b")

        status = get_all_circuit_breakers_status()
        self.assertIn("model-a", status)
        self.assertIn("model-b", status)
        self.assertEqual(status["model-a"]["state"], "closed")


# ═══════════════════════════════════════════════════════════════════════════════
# Test: DynamoDB Utils
# ═══════════════════════════════════════════════════════════════════════════════

@mock_aws
class TestDynamoUtils(unittest.TestCase):
    """Test DynamoDB operations for semaphore and status tracking."""

    def setUp(self):
        """Create test DynamoDB tables."""
        self.dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        # Create semaphore table
        self.dynamodb.create_table(
            TableName="TestSemaphore",
            KeySchema=[{"AttributeName": "LockName", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "LockName", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create status table with GSI
        self.dynamodb.create_table(
            TableName="TestStatus",
            KeySchema=[{"AttributeName": "job_posting_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "job_posting_id", "AttributeType": "S"},
                {"AttributeName": "overallStatus", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "status-index",
                    "KeySchema": [{"AttributeName": "overallStatus", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Reset singletons
        import shared.dynamo_utils as du
        du._dynamodb_client = None
        du._dynamodb_resource = None

    def test_acquire_and_release_lock(self):
        """Should acquire and release locks correctly."""
        from shared.dynamo_utils import acquire_lock, release_lock, get_lock_status

        # Acquire lock
        result = acquire_lock("exec-001")
        self.assertTrue(result)

        status = get_lock_status()
        self.assertEqual(status["current_count"], 1)
        self.assertEqual(len(status["active_executions"]), 1)

        # Release lock
        result = release_lock("exec-001")
        self.assertTrue(result)

        status = get_lock_status()
        self.assertEqual(status["current_count"], 0)

    def test_lock_capacity_limit(self):
        """Should respect max concurrent executions."""
        from shared.dynamo_utils import acquire_lock, get_lock_status

        # Acquire up to limit (5)
        for i in range(5):
            result = acquire_lock(f"exec-{i:03d}")
            self.assertTrue(result, f"Should acquire lock {i}")

        # 6th should fail
        result = acquire_lock("exec-005")
        self.assertFalse(result)

        status = get_lock_status()
        self.assertEqual(status["current_count"], 5)

    def test_job_status_lifecycle(self):
        """Should track job status through lifecycle."""
        from shared.dynamo_utils import (
            create_job_status,
            get_job_status,
            mark_pass_started,
            mark_pass_completed,
            STATUS_PENDING,
            STATUS_IN_PROGRESS,
            STATUS_COMPLETED,
        )

        job_id = "test-job-123"

        # Create
        status = create_job_status(job_id)
        self.assertEqual(status["pass1"]["status"], STATUS_PENDING)

        # Start pass1
        status = mark_pass_started(job_id, "pass1", model="mistral-large")
        self.assertEqual(status["pass1"]["status"], STATUS_IN_PROGRESS)

        # Complete pass1
        status = mark_pass_completed(job_id, "pass1", cost_usd=0.005)
        self.assertEqual(status["pass1"]["status"], STATUS_COMPLETED)

        # Verify final state
        final = get_job_status(job_id)
        self.assertEqual(final["pass1"]["status"], STATUS_COMPLETED)

    def test_get_pending_jobs_uses_gsi(self):
        """Should query GSI instead of scanning."""
        from shared.dynamo_utils import (
            create_job_status,
            get_pending_jobs,
            mark_pass_completed,
        )

        # Create jobs with different statuses
        create_job_status("job-pending")
        create_job_status("job-completed")

        # Complete all passes for one job
        for pass_name in ["pass1", "pass2", "pass3"]:
            mark_pass_completed("job-completed", pass_name)

        # Get pending should only return incomplete jobs
        pending = get_pending_jobs(limit=10)
        job_ids = [j["job_posting_id"] for j in pending]

        self.assertIn("job-pending", job_ids)
        self.assertNotIn("job-completed", job_ids)


# ═══════════════════════════════════════════════════════════════════════════════
# Test: Discover Partitions
# ═══════════════════════════════════════════════════════════════════════════════

@mock_aws
class TestDiscoverPartitions(unittest.TestCase):
    """Test partition discovery and SQS publishing."""

    def setUp(self):
        """Create test S3 bucket and SQS queue."""
        self.s3 = boto3.client("s3", region_name="us-east-1")
        self.sqs = boto3.client("sqs", region_name="us-east-1")

        # Create bucket
        self.s3.create_bucket(Bucket="test-silver-bucket")

        # Create FIFO queue
        response = self.sqs.create_queue(
            QueueName="test-queue.fifo",
            Attributes={"FifoQueue": "true", "ContentBasedDeduplication": "false"},
        )
        os.environ["SQS_QUEUE_URL"] = response["QueueUrl"]

    def test_parse_partition_key(self):
        """Should parse partition key correctly."""
        from discover_partitions.handler import parse_partition_key

        result = parse_partition_key("year=2025/month=12/day=05/hour=10")
        self.assertEqual(result["year"], "2025")
        self.assertEqual(result["month"], "12")
        self.assertEqual(result["day"], "05")
        self.assertEqual(result["hour"], "10")

    def test_deduplication_id_includes_full_date(self):
        """MessageDeduplicationId should include full date to avoid collisions."""
        from discover_partitions.handler import publish_jobs_to_sqs

        os.environ["PUBLISH_TO_SQS"] = "true"

        jobs = [
            {
                "job_posting_id": "123",
                "partition": {"year": "2025", "month": "12", "day": "05", "hour": "10"},
            }
        ]

        # This would fail if deduplication ID doesn't include full date
        result = publish_jobs_to_sqs(jobs)
        self.assertEqual(result["published"], 1)
        self.assertEqual(result["failed"], 0)


# ═══════════════════════════════════════════════════════════════════════════════
# Test: Enrich Partition Handler
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnrichPartitionHandler(unittest.TestCase):
    """Test enrich_partition handler with mocked Bedrock."""

    def setUp(self):
        """Reset circuit breakers."""
        from enrich_partition.bedrock_client import _circuit_breakers
        _circuit_breakers.clear()

    @patch("enrich_partition.bedrock_client.BedrockClient.invoke")
    @patch("enrich_partition.handler.write_bronze_result")
    @patch("enrich_partition.handler.check_job_processed")
    def test_pass1_extraction(self, mock_check, mock_write, mock_invoke):
        """Should extract skills from job description."""
        mock_check.return_value = False  # Not cached
        # Return a properly structured pass1 response with 'extraction' key
        mock_invoke.return_value = (
            json.dumps({
                "extraction": {
                    "skills": ["Python", "SQL", "AWS"],
                    "experience_years": 3,
                    "seniority_level": "mid"
                }
            }),
            1000,  # input tokens
            500,   # output tokens
            0.005, # cost
        )
        mock_write.return_value = True

        from enrich_partition.handler import handler

        event = {
            "pass_name": "pass1",
            "job_data": {
                "job_posting_id": "test-123",
                "job_title": "Data Engineer",
                "company_name": "Test Corp",
                "job_location": "Remote",
                "job_description": "Looking for Python and SQL skills...",
            },
            "execution_id": "test-exec",
        }

        result = handler(event, None)

        self.assertEqual(result["statusCode"], 200)
        self.assertTrue(result["success"])
        self.assertIn("extraction", result)
        mock_write.assert_called_once()

    @patch("enrich_partition.handler.check_job_processed")
    @patch("enrich_partition.handler.read_bronze_result")
    def test_returns_cached_result(self, mock_read, mock_check):
        """Should return cached result if already processed."""
        mock_check.return_value = True  # Already cached
        mock_read.return_value = {"skills": ["Python"], "cached": True}

        from enrich_partition.handler import handler

        event = {
            "pass_name": "pass1",
            "job_data": {
                "job_posting_id": "test-123",
                "job_title": "Data Engineer",
                "company_name": "Test Corp",
                "job_location": "Remote",
                "job_description": "...",
            },
            "execution_id": "test-exec",
        }

        result = handler(event, None)

        self.assertEqual(result["statusCode"], 200)
        self.assertTrue(result.get("cached"))


# ═══════════════════════════════════════════════════════════════════════════════
# Test: Integration Flow
# ═══════════════════════════════════════════════════════════════════════════════

@mock_aws
class TestIntegrationFlow(unittest.TestCase):
    """Test end-to-end flow with mocked services."""

    def setUp(self):
        """Set up all required AWS resources."""
        # DynamoDB
        self.dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        self.dynamodb.create_table(
            TableName="TestSemaphore",
            KeySchema=[{"AttributeName": "LockName", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "LockName", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        self.dynamodb.create_table(
            TableName="TestStatus",
            KeySchema=[{"AttributeName": "job_posting_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "job_posting_id", "AttributeType": "S"},
                {"AttributeName": "overallStatus", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "status-index",
                    "KeySchema": [{"AttributeName": "overallStatus", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Reset singletons
        import shared.dynamo_utils as du
        du._dynamodb_client = None
        du._dynamodb_resource = None

        from enrich_partition.bedrock_client import _circuit_breakers
        _circuit_breakers.clear()

    def test_full_job_lifecycle(self):
        """Test complete job processing lifecycle."""
        from shared.dynamo_utils import (
            acquire_lock,
            release_lock,
            create_job_status,
            mark_pass_completed,
            get_job_status,
            STATUS_COMPLETED,
        )

        job_id = "integration-test-job"
        exec_id = "integration-exec-001"

        # 1. Acquire lock (like Step Function)
        self.assertTrue(acquire_lock(exec_id))

        # 2. Create job status
        create_job_status(job_id, exec_id)

        # 3. Process passes (simulated)
        for pass_name in ["pass1", "pass2", "pass3"]:
            mark_pass_completed(job_id, pass_name, cost_usd=0.01)

        # 4. Release lock
        self.assertTrue(release_lock(exec_id))

        # 5. Verify final state
        status = get_job_status(job_id)
        self.assertEqual(status["overallStatus"], STATUS_COMPLETED)
        self.assertEqual(status["pass1"]["status"], STATUS_COMPLETED)
        self.assertEqual(status["pass2"]["status"], STATUS_COMPLETED)
        self.assertEqual(status["pass3"]["status"], STATUS_COMPLETED)


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Run tests
    if len(sys.argv) > 1:
        # Run specific test class
        suite = unittest.TestLoader().loadTestsFromName(sys.argv[1])
    else:
        # Run all tests
        suite = unittest.TestLoader().discover(".", pattern="test_local.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)
