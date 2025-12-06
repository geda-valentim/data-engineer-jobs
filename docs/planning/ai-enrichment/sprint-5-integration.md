# Sprint 5: Orchestration & Integration

> **Sprint:** 5 of 5
> **Duration:** 3-4 days
> **Predecessor:** Sprint 4 (Pass 3 - Analysis)
> **Goal:** Complete Step Functions, EventBridge, S3 I/O, deploy, and test with real partition

---

## Overview

Sprint 5 brings everything together:

1. **DiscoverPartitions Lambda** - Find unprocessed Silver partitions
2. **EnrichPartition Lambda** - Complete with S3 I/O and CloudWatch metrics
3. **Step Functions** - Orchestrate discovery → map → enrich flow
4. **EventBridge** - Daily trigger for automatic processing
5. **Deployment** - Terraform apply and live testing

---

## Tasks

### 5.1 Complete DiscoverPartitions Lambda

**File:** `src/lambdas/ai_enrichment/discover_partitions/handler.py`

```python
"""
DiscoverPartitions Lambda Handler

Finds Silver partitions that haven't been processed to Silver-AI yet.
Uses S3 partition listing to compute the diff.
"""

import json
import logging
import os
from typing import Any

import awswrangler as wr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SILVER_BUCKET = os.environ.get("SILVER_BUCKET", "data-engineer-jobs-silver-dev")
SILVER_PREFIX = os.environ.get("SILVER_PREFIX", "linkedin/")
SILVER_AI_PREFIX = os.environ.get("SILVER_AI_PREFIX", "linkedin_ai/")
MAX_PARTITIONS = int(os.environ.get("MAX_PARTITIONS", "10"))


def list_partitions(bucket: str, prefix: str) -> set[str]:
    """
    List all partitions under a prefix.

    Returns set of partition keys like "year=2024/month=01/day=15/hour=12"
    """
    path = f"s3://{bucket}/{prefix}"

    try:
        # List directories at partition level
        directories = wr.s3.list_directories(path)

        partitions = set()
        for dir_path in directories:
            # Extract partition key from path
            # e.g., "s3://bucket/prefix/year=2024/month=01/day=15/hour=12/"
            # → "year=2024/month=01/day=15/hour=12"
            parts = dir_path.replace(path, "").strip("/")
            if parts and "year=" in parts:
                partitions.add(parts)

        return partitions

    except Exception as e:
        logger.error(f"Error listing partitions at {path}: {e}")
        return set()


def parse_partition_key(partition_key: str) -> dict:
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


def handler(event: dict, context: Any) -> dict:
    """
    Lambda handler to discover unprocessed partitions.

    Returns:
        {
            "has_work": bool,
            "partitions": [
                {"year": "2024", "month": "01", "day": "15", "hour": "12"},
                ...
            ],
            "total_pending": int,
            "processing_count": int
        }
    """
    logger.info(f"Discovering partitions - Silver: {SILVER_PREFIX}, Silver-AI: {SILVER_AI_PREFIX}")

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
        "processing_count": len(partitions)
    }

    logger.info(f"Returning {len(partitions)} partitions for processing")
    return result
```

---

### 5.2 Complete EnrichPartition Lambda with S3 I/O

> ⚠️ **CRITICAL - FAULT TOLERANCE:** O handler DEVE processar todos os registros mesmo que alguns falhem.
> Não há verba para reprocessamento massivo. Cada registro é envolvido em try/catch individual.

**File:** `src/lambdas/ai_enrichment/enrich_partition/handler.py` (update)

```python
"""
EnrichPartition Lambda Handler - Complete Implementation with S3 I/O
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import awswrangler as wr
import boto3
import pandas as pd

from .bedrock_client import BedrockClient
from .prompts.pass1_extraction import build_pass1_prompt
from .prompts.pass2_inference import build_pass2_prompt
from .prompts.pass3_analysis import build_pass3_prompt
from .parsers.json_parser import parse_llm_json
from .parsers.validators import (
    validate_extraction_response,
    validate_inference_response,
    validate_analysis_response
)
from .flatteners.extraction import flatten_extraction
from .flatteners.inference import flatten_inference
from .flatteners.analysis import flatten_analysis

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SILVER_BUCKET = os.environ.get("SILVER_BUCKET", "data-engineer-jobs-silver-dev")
SILVER_PREFIX = os.environ.get("SILVER_PREFIX", "linkedin/")
SILVER_AI_PREFIX = os.environ.get("SILVER_AI_PREFIX", "linkedin_ai/")
BEDROCK_MODEL_PASS1 = os.environ.get("BEDROCK_MODEL_PASS1", "openai.gpt-oss-120b-1:0")
BEDROCK_MODEL_PASS2 = os.environ.get("BEDROCK_MODEL_PASS2", "openai.gpt-oss-120b-1:0")
BEDROCK_MODEL_PASS3 = os.environ.get("BEDROCK_MODEL_PASS3", "openai.gpt-oss-120b-1:0")

# CloudWatch metrics
cloudwatch = boto3.client("cloudwatch")
METRIC_NAMESPACE = "DataEngineerJobs/AIEnrichment"

ENRICHMENT_VERSION = "1.0"


class EnrichmentResult:
    """Container for enrichment results and metadata."""

    def __init__(self):
        self.pass1_result: Optional[dict] = None
        self.pass2_result: Optional[dict] = None
        self.pass3_result: Optional[dict] = None

        self.pass1_success: bool = False
        self.pass2_success: bool = False
        self.pass3_success: bool = False

        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cost_usd: float = 0.0

        self.pass1_model: Optional[str] = None
        self.pass2_model: Optional[str] = None
        self.pass3_model: Optional[str] = None

        self.errors: list[str] = []

    def add_pass_result(
        self,
        pass_num: int,
        result: Optional[dict],
        success: bool,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        model_id: str,
        error: Optional[str] = None
    ):
        """Record result for a pass."""
        if pass_num == 1:
            self.pass1_result = result
            self.pass1_success = success
            self.pass1_model = model_id
        elif pass_num == 2:
            self.pass2_result = result
            self.pass2_success = success
            self.pass2_model = model_id
        elif pass_num == 3:
            self.pass3_result = result
            self.pass3_success = success
            self.pass3_model = model_id

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost

        if error:
            self.errors.append(f"Pass {pass_num}: {error}")

    def get_avg_confidence_pass2(self) -> Optional[float]:
        """Calculate average confidence from Pass 2 results."""
        if not self.pass2_result:
            return None

        confidences = []
        for field in ["seniority", "cloud_provider", "geo_restriction", "contract_type",
                      "team_size_category", "data_scale"]:
            conf = self.pass2_result.get(field, {}).get("confidence")
            if conf is not None:
                confidences.append(conf)

        return sum(confidences) / len(confidences) if confidences else None

    def get_avg_confidence_pass3(self) -> Optional[float]:
        """Calculate average confidence from Pass 3 results."""
        if not self.pass3_result:
            return None

        confidences = []
        dm_conf = self.pass3_result.get("data_maturity", {}).get("confidence")
        if dm_conf is not None:
            confidences.append(dm_conf)
        culture_conf = self.pass3_result.get("culture_signals", {}).get("confidence")
        if culture_conf is not None:
            confidences.append(culture_conf)
        analysis_conf = self.pass3_result.get("metadata", {}).get("analysis_confidence")
        if analysis_conf is not None:
            confidences.append(analysis_conf)

        return sum(confidences) / len(confidences) if confidences else None

    def get_low_confidence_fields(self) -> list[str]:
        """Get list of low confidence fields from Pass 3."""
        if not self.pass3_result:
            return []
        return self.pass3_result.get("metadata", {}).get("low_confidence_fields", [])


def emit_metrics(
    partition: dict,
    jobs_processed: int,
    jobs_succeeded: int,
    total_tokens: int,
    total_cost: float,
    pass1_success_rate: float,
    pass2_success_rate: float,
    pass3_success_rate: float
):
    """Emit CloudWatch metrics for the partition."""
    partition_str = f"{partition['year']}/{partition['month']}/{partition['day']}/{partition['hour']}"

    try:
        cloudwatch.put_metric_data(
            Namespace=METRIC_NAMESPACE,
            MetricData=[
                {
                    "MetricName": "JobsProcessed",
                    "Value": jobs_processed,
                    "Unit": "Count",
                    "Dimensions": [{"Name": "Partition", "Value": partition_str}]
                },
                {
                    "MetricName": "JobsSucceeded",
                    "Value": jobs_succeeded,
                    "Unit": "Count",
                    "Dimensions": [{"Name": "Partition", "Value": partition_str}]
                },
                {
                    "MetricName": "TokensUsed",
                    "Value": total_tokens,
                    "Unit": "Count",
                    "Dimensions": [{"Name": "Partition", "Value": partition_str}]
                },
                {
                    "MetricName": "CostUSD",
                    "Value": total_cost,
                    "Unit": "None",
                    "Dimensions": [{"Name": "Partition", "Value": partition_str}]
                },
                {
                    "MetricName": "Pass1SuccessRate",
                    "Value": pass1_success_rate * 100,
                    "Unit": "Percent",
                    "Dimensions": [{"Name": "Partition", "Value": partition_str}]
                },
                {
                    "MetricName": "Pass2SuccessRate",
                    "Value": pass2_success_rate * 100,
                    "Unit": "Percent",
                    "Dimensions": [{"Name": "Partition", "Value": partition_str}]
                },
                {
                    "MetricName": "Pass3SuccessRate",
                    "Value": pass3_success_rate * 100,
                    "Unit": "Percent",
                    "Dimensions": [{"Name": "Partition", "Value": partition_str}]
                },
            ]
        )
        logger.info(f"Emitted metrics for partition {partition_str}")
    except Exception as e:
        logger.error(f"Failed to emit metrics: {e}")


def enrich_job(job: dict, bedrock_client: BedrockClient) -> tuple[dict, EnrichmentResult]:
    """Run full 3-pass enrichment on a single job."""
    result = EnrichmentResult()

    title = job.get("title", "")
    company = job.get("company_name", "")
    location = job.get("location", "")
    description = job.get("description", "")

    # Pass 1
    try:
        system_prompt, user_prompt = build_pass1_prompt(title, company, location, description)
        response, input_tokens, output_tokens, cost = bedrock_client.invoke(
            prompt=user_prompt, system=system_prompt, pass_name="pass1"
        )
        pass1_data, parse_error = parse_llm_json(response)
        if parse_error:
            raise ValueError(f"JSON parse error: {parse_error}")
        is_valid, errors = validate_extraction_response(pass1_data)
        if not is_valid:
            raise ValueError(f"Validation errors: {errors}")
        result.add_pass_result(1, pass1_data, True, input_tokens, output_tokens, cost,
                               bedrock_client.get_model_id("pass1"))
    except Exception as e:
        logger.error(f"Pass 1 failed: {e}")
        result.add_pass_result(1, None, False, 0, 0, 0,
                               bedrock_client.get_model_id("pass1"), str(e))

    # Pass 2
    if result.pass1_success:
        try:
            system_prompt, user_prompt = build_pass2_prompt(
                title, company, location, description, result.pass1_result
            )
            response, input_tokens, output_tokens, cost = bedrock_client.invoke(
                prompt=user_prompt, system=system_prompt, pass_name="pass2"
            )
            pass2_data, parse_error = parse_llm_json(response)
            if parse_error:
                raise ValueError(f"JSON parse error: {parse_error}")
            is_valid, errors = validate_inference_response(pass2_data)
            if not is_valid:
                raise ValueError(f"Validation errors: {errors}")
            result.add_pass_result(2, pass2_data, True, input_tokens, output_tokens, cost,
                                   bedrock_client.get_model_id("pass2"))
        except Exception as e:
            logger.error(f"Pass 2 failed: {e}")
            result.add_pass_result(2, None, False, 0, 0, 0,
                                   bedrock_client.get_model_id("pass2"), str(e))

    # Pass 3
    if result.pass1_success and result.pass2_success:
        try:
            system_prompt, user_prompt = build_pass3_prompt(
                title, company, location, description,
                result.pass1_result, result.pass2_result
            )
            response, input_tokens, output_tokens, cost = bedrock_client.invoke(
                prompt=user_prompt, system=system_prompt, pass_name="pass3"
            )
            pass3_data, parse_error = parse_llm_json(response)
            if parse_error:
                raise ValueError(f"JSON parse error: {parse_error}")
            is_valid, errors = validate_analysis_response(pass3_data)
            if not is_valid:
                raise ValueError(f"Validation errors: {errors}")
            result.add_pass_result(3, pass3_data, True, input_tokens, output_tokens, cost,
                                   bedrock_client.get_model_id("pass3"))
        except Exception as e:
            logger.error(f"Pass 3 failed: {e}")
            result.add_pass_result(3, None, False, 0, 0, 0,
                                   bedrock_client.get_model_id("pass3"), str(e))

    # Flatten results
    flat = {}
    if result.pass1_result:
        flat.update(flatten_extraction(result.pass1_result))
    if result.pass2_result:
        flat.update(flatten_inference(result.pass2_result))
    if result.pass3_result:
        flat.update(flatten_analysis(result.pass3_result))

    # Add metadata
    flat["enriched_at"] = datetime.now(timezone.utc).isoformat()
    flat["enrichment_version"] = ENRICHMENT_VERSION
    flat["enrichment_model_pass1"] = result.pass1_model
    flat["enrichment_model_pass2"] = result.pass2_model
    flat["enrichment_model_pass3"] = result.pass3_model
    flat["total_tokens_used"] = result.total_input_tokens + result.total_output_tokens
    flat["enrichment_cost_usd"] = round(result.total_cost_usd, 6)
    flat["pass1_success"] = result.pass1_success
    flat["pass2_success"] = result.pass2_success
    flat["pass3_success"] = result.pass3_success
    flat["avg_confidence_pass2"] = result.get_avg_confidence_pass2()
    flat["avg_confidence_pass3"] = result.get_avg_confidence_pass3()
    flat["low_confidence_fields"] = "; ".join(result.get_low_confidence_fields()) or None
    flat["enrichment_errors"] = "; ".join(result.errors) or None

    return flat, result


def handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for partition enrichment.

    Event structure:
    {
        "partition": {
            "year": "2024",
            "month": "01",
            "day": "15",
            "hour": "12"
        }
    }
    """
    logger.info(f"Received event: {json.dumps(event)}")

    partition = event.get("partition", {})
    year = partition.get("year")
    month = partition.get("month")
    day = partition.get("day")
    hour = partition.get("hour")

    if not all([year, month, day, hour]):
        return {"statusCode": 400, "error": "Missing partition keys"}

    partition_path = f"year={year}/month={month}/day={day}/hour={hour}"
    silver_path = f"s3://{SILVER_BUCKET}/{SILVER_PREFIX}{partition_path}/"
    silver_ai_path = f"s3://{SILVER_BUCKET}/{SILVER_AI_PREFIX}{partition_path}/"

    logger.info(f"Processing partition: {partition_path}")
    logger.info(f"Reading from: {silver_path}")
    logger.info(f"Writing to: {silver_ai_path}")

    # Read Silver Parquet
    try:
        df = wr.s3.read_parquet(silver_path)
        logger.info(f"Read {len(df)} jobs from Silver")
    except Exception as e:
        logger.error(f"Failed to read Silver partition: {e}")
        return {"statusCode": 500, "error": f"Failed to read: {e}"}

    if df.empty:
        logger.info("Empty partition, nothing to process")
        return {"statusCode": 200, "jobs_processed": 0}

    # Initialize Bedrock client
    bedrock_client = BedrockClient(
        model_ids={
            "pass1": BEDROCK_MODEL_PASS1,
            "pass2": BEDROCK_MODEL_PASS2,
            "pass3": BEDROCK_MODEL_PASS3,
        }
    )

    # Process each job
    enriched_rows = []
    total_tokens = 0
    total_cost = 0.0
    pass1_successes = 0
    pass2_successes = 0
    pass3_successes = 0

    for idx, row in df.iterrows():
        job_id = row.get("job_posting_id", f"row_{idx}")
        logger.info(f"Processing job {idx + 1}/{len(df)}: {job_id}")

        try:
            job_dict = row.to_dict()
            flat_result, enrichment_result = enrich_job(job_dict, bedrock_client)

            # Merge original row with enrichment
            merged = {**job_dict, **flat_result}
            enriched_rows.append(merged)

            # Aggregate stats
            total_tokens += enrichment_result.total_input_tokens + enrichment_result.total_output_tokens
            total_cost += enrichment_result.total_cost_usd
            if enrichment_result.pass1_success:
                pass1_successes += 1
            if enrichment_result.pass2_success:
                pass2_successes += 1
            if enrichment_result.pass3_success:
                pass3_successes += 1

        except Exception as e:
            # ⚠️ CRITICAL: Falha catastrófica - ainda mantém o registro!
            # Nunca pular um registro - sempre incluir com marcação de erro
            logger.error(f"Catastrophic failure for job {job_id}: {e}")

            # Cria enrichment vazio com flags de falha
            empty_enrichment = {
                "enriched_at": datetime.now(timezone.utc).isoformat(),
                "enrichment_version": ENRICHMENT_VERSION,
                "pass1_success": False,
                "pass2_success": False,
                "pass3_success": False,
                "enrichment_errors": f"Catastrophic: {str(e)}",
            }
            merged = {**row.to_dict(), **empty_enrichment}
            enriched_rows.append(merged)
            # NÃO incrementa success counters - registro falhou

    # Create enriched DataFrame
    enriched_df = pd.DataFrame(enriched_rows)

    # Write to Silver-AI
    try:
        wr.s3.to_parquet(
            df=enriched_df,
            path=silver_ai_path,
            index=False,
            dataset=False,  # Single file per partition
            mode="overwrite"
        )
        logger.info(f"Wrote {len(enriched_df)} rows to {silver_ai_path}")
    except Exception as e:
        logger.error(f"Failed to write Silver-AI partition: {e}")
        return {"statusCode": 500, "error": f"Failed to write: {e}"}

    # Emit metrics
    jobs_processed = len(df)
    jobs_succeeded = pass3_successes  # Full success = all 3 passes
    emit_metrics(
        partition=partition,
        jobs_processed=jobs_processed,
        jobs_succeeded=jobs_succeeded,
        total_tokens=total_tokens,
        total_cost=total_cost,
        pass1_success_rate=pass1_successes / jobs_processed if jobs_processed > 0 else 0,
        pass2_success_rate=pass2_successes / jobs_processed if jobs_processed > 0 else 0,
        pass3_success_rate=pass3_successes / jobs_processed if jobs_processed > 0 else 0
    )

    return {
        "statusCode": 200,
        "partition": partition_path,
        "jobs_processed": jobs_processed,
        "jobs_succeeded": jobs_succeeded,
        "pass1_success_rate": pass1_successes / jobs_processed if jobs_processed > 0 else 0,
        "pass2_success_rate": pass2_successes / jobs_processed if jobs_processed > 0 else 0,
        "pass3_success_rate": pass3_successes / jobs_processed if jobs_processed > 0 else 0,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 4)
    }
```

---

### 5.3 Create Step Functions Definition

**File:** `infra/modules/ai_enrichment/step_functions.tf`

```hcl
# Step Functions State Machine for AI Enrichment Pipeline

resource "aws_sfn_state_machine" "ai_enrichment" {
  name     = "${var.project_name}-ai-enrichment-${var.environment}"
  role_arn = aws_iam_role.step_functions.arn

  definition = jsonencode({
    Comment = "AI Enrichment Pipeline - Discovers and processes Silver partitions"
    StartAt = "DiscoverPartitions"

    States = {
      DiscoverPartitions = {
        Type     = "Task"
        Resource = aws_lambda_function.discover_partitions.arn
        Next     = "CheckHasWork"
        Retry = [
          {
            ErrorEquals     = ["States.TaskFailed"]
            IntervalSeconds = 5
            MaxAttempts     = 2
            BackoffRate     = 2
          }
        ]
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "DiscoveryFailed"
          }
        ]
      }

      CheckHasWork = {
        Type = "Choice"
        Choices = [
          {
            Variable      = "$.has_work"
            BooleanEquals = true
            Next          = "MapPartitions"
          }
        ]
        Default = "NoWorkToProcess"
      }

      NoWorkToProcess = {
        Type = "Succeed"
        Comment = "No pending partitions to process"
      }

      MapPartitions = {
        Type           = "Map"
        ItemsPath      = "$.partitions"
        MaxConcurrency = 5
        Iterator = {
          StartAt = "EnrichPartition"
          States = {
            EnrichPartition = {
              Type     = "Task"
              Resource = aws_lambda_function.enrich_partition.arn
              Parameters = {
                "partition.$" = "$"
              }
              End = true
              Retry = [
                {
                  ErrorEquals     = ["States.TaskFailed", "Lambda.ServiceException"]
                  IntervalSeconds = 30
                  MaxAttempts     = 2
                  BackoffRate     = 2
                }
              ]
              Catch = [
                {
                  ErrorEquals = ["States.ALL"]
                  ResultPath  = "$.error"
                  Next        = "PartitionFailed"
                }
              ]
            }
            PartitionFailed = {
              Type    = "Pass"
              Comment = "Partition processing failed, continue with others"
              End     = true
            }
          }
        }
        Next = "ProcessingComplete"
      }

      ProcessingComplete = {
        Type = "Succeed"
        Comment = "All partitions processed"
      }

      DiscoveryFailed = {
        Type  = "Fail"
        Error = "DiscoveryError"
        Cause = "Failed to discover partitions"
      }
    }
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.step_functions.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Component   = "ai-enrichment"
  }
}

# CloudWatch Log Group for Step Functions
resource "aws_cloudwatch_log_group" "step_functions" {
  name              = "/aws/stepfunctions/${var.project_name}-ai-enrichment-${var.environment}"
  retention_in_days = 30

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Component   = "ai-enrichment"
  }
}
```

---

### 5.4 Create Step Functions IAM

**File:** `infra/modules/ai_enrichment/step_functions.iam.tf`

```hcl
# IAM Role for Step Functions

resource "aws_iam_role" "step_functions" {
  name = "${var.project_name}-ai-enrichment-sfn-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Component   = "ai-enrichment"
  }
}

# Policy to invoke Lambda functions
resource "aws_iam_role_policy" "step_functions_lambda" {
  name = "lambda-invoke"
  role = aws_iam_role.step_functions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          aws_lambda_function.discover_partitions.arn,
          aws_lambda_function.enrich_partition.arn
        ]
      }
    ]
  })
}

# Policy for CloudWatch Logs
resource "aws_iam_role_policy" "step_functions_logs" {
  name = "cloudwatch-logs"
  role = aws_iam_role.step_functions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutLogEvents",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      }
    ]
  })
}

# Policy for X-Ray tracing (optional)
resource "aws_iam_role_policy" "step_functions_xray" {
  name = "xray-tracing"
  role = aws_iam_role.step_functions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets"
        ]
        Resource = "*"
      }
    ]
  })
}
```

---

### 5.5 Create EventBridge Trigger

**File:** `infra/modules/ai_enrichment/eventbridge.tf`

```hcl
# EventBridge Rule for Daily Trigger

resource "aws_cloudwatch_event_rule" "daily_enrichment" {
  name                = "${var.project_name}-ai-enrichment-daily-${var.environment}"
  description         = "Trigger AI enrichment pipeline daily at 6 AM UTC"
  schedule_expression = "cron(0 6 * * ? *)"

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Component   = "ai-enrichment"
  }
}

resource "aws_cloudwatch_event_target" "step_functions" {
  rule      = aws_cloudwatch_event_rule.daily_enrichment.name
  target_id = "ai-enrichment-sfn"
  arn       = aws_sfn_state_machine.ai_enrichment.arn
  role_arn  = aws_iam_role.eventbridge.arn

  input = jsonencode({
    source = "scheduled"
    time   = "daily-6am-utc"
  })
}

# IAM Role for EventBridge
resource "aws_iam_role" "eventbridge" {
  name = "${var.project_name}-ai-enrichment-eb-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Component   = "ai-enrichment"
  }
}

resource "aws_iam_role_policy" "eventbridge_sfn" {
  name = "start-step-functions"
  role = aws_iam_role.eventbridge.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "states:StartExecution"
        Resource = aws_sfn_state_machine.ai_enrichment.arn
      }
    ]
  })
}
```

---

### 5.6 Create Lambda Terraform Resources

**File:** `infra/modules/ai_enrichment/lambda_discover.tf`

```hcl
# DiscoverPartitions Lambda

resource "aws_lambda_function" "discover_partitions" {
  function_name = "${var.project_name}-ai-discover-${var.environment}"
  role          = aws_iam_role.lambda.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  timeout       = 60
  memory_size   = 256

  filename         = data.archive_file.discover_partitions.output_path
  source_code_hash = data.archive_file.discover_partitions.output_base64sha256

  layers = [
    var.python_deps_layer_arn,
    var.awswrangler_layer_arn
  ]

  environment {
    variables = {
      SILVER_BUCKET    = var.silver_bucket
      SILVER_PREFIX    = var.silver_prefix
      SILVER_AI_PREFIX = var.silver_ai_prefix
      MAX_PARTITIONS   = var.max_partitions_per_run
    }
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Component   = "ai-enrichment"
  }
}

resource "aws_cloudwatch_log_group" "discover_partitions" {
  name              = "/aws/lambda/${aws_lambda_function.discover_partitions.function_name}"
  retention_in_days = 30

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Component   = "ai-enrichment"
  }
}
```

**File:** `infra/modules/ai_enrichment/lambda_enrich.tf`

```hcl
# EnrichPartition Lambda

resource "aws_lambda_function" "enrich_partition" {
  function_name = "${var.project_name}-ai-enrich-${var.environment}"
  role          = aws_iam_role.lambda.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  timeout       = 900  # 15 minutes max
  memory_size   = 1024

  filename         = data.archive_file.enrich_partition.output_path
  source_code_hash = data.archive_file.enrich_partition.output_base64sha256

  layers = [
    var.python_deps_layer_arn,
    var.awswrangler_layer_arn
  ]

  reserved_concurrent_executions = 5  # Match Step Functions MaxConcurrency

  environment {
    variables = {
      SILVER_BUCKET       = var.silver_bucket
      SILVER_PREFIX       = var.silver_prefix
      SILVER_AI_PREFIX    = var.silver_ai_prefix
      BEDROCK_MODEL_PASS1 = var.bedrock_model_pass1
      BEDROCK_MODEL_PASS2 = var.bedrock_model_pass2
      BEDROCK_MODEL_PASS3 = var.bedrock_model_pass3
    }
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Component   = "ai-enrichment"
  }
}

resource "aws_cloudwatch_log_group" "enrich_partition" {
  name              = "/aws/lambda/${aws_lambda_function.enrich_partition.function_name}"
  retention_in_days = 30

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Component   = "ai-enrichment"
  }
}
```

---

### 5.7 Update Variables and Outputs

**File:** `infra/modules/ai_enrichment/variables.tf` (update)

```hcl
# Add these variables to existing file

variable "max_partitions_per_run" {
  description = "Maximum number of partitions to process per Step Functions execution"
  type        = number
  default     = 10
}

variable "silver_prefix" {
  description = "S3 prefix for Silver layer data"
  type        = string
  default     = "linkedin/"
}

variable "silver_ai_prefix" {
  description = "S3 prefix for Silver-AI layer data"
  type        = string
  default     = "linkedin_ai/"
}

variable "bedrock_model_pass1" {
  description = "Bedrock model ID for Pass 1 extraction"
  type        = string
  default     = "openai.gpt-oss-120b-1:0"  # $0.00015/1K input, $0.0003/1K output
}

variable "bedrock_model_pass2" {
  description = "Bedrock model ID for Pass 2 inference"
  type        = string
  default     = "openai.gpt-oss-120b-1:0"
}

variable "bedrock_model_pass3" {
  description = "Bedrock model ID for Pass 3 analysis"
  type        = string
  default     = "openai.gpt-oss-120b-1:0"
}

variable "python_deps_layer_arn" {
  description = "ARN of the existing Python dependencies Lambda layer"
  type        = string
}

variable "awswrangler_layer_arn" {
  description = "ARN of the AWS SDK for Pandas (awswrangler) Lambda layer"
  type        = string
}
```

**File:** `infra/modules/ai_enrichment/outputs.tf` (update)

```hcl
# Add these outputs to existing file

output "step_functions_arn" {
  description = "ARN of the AI enrichment Step Functions state machine"
  value       = aws_sfn_state_machine.ai_enrichment.arn
}

output "step_functions_name" {
  description = "Name of the AI enrichment Step Functions state machine"
  value       = aws_sfn_state_machine.ai_enrichment.name
}

output "eventbridge_rule_arn" {
  description = "ARN of the EventBridge daily trigger rule"
  value       = aws_cloudwatch_event_rule.daily_enrichment.arn
}

output "discover_lambda_arn" {
  description = "ARN of the DiscoverPartitions Lambda"
  value       = aws_lambda_function.discover_partitions.arn
}

output "enrich_lambda_arn" {
  description = "ARN of the EnrichPartition Lambda"
  value       = aws_lambda_function.enrich_partition.arn
}
```

---

### 5.8 Update Module Reference in Dev Environment

**File:** `infra/environments/dev/main.tf` (append)

```hcl
# AI Enrichment Module
module "ai_enrichment" {
  source = "../../modules/ai_enrichment"

  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region

  silver_bucket    = module.storage.silver_bucket_name
  silver_prefix    = "linkedin/"
  silver_ai_prefix = "linkedin_ai/"

  max_partitions_per_run = 10

  # openai.gpt-oss-120b-1:0: $0.00015/1K input, $0.0003/1K output (extremely cheap!)
  bedrock_model_pass1 = "openai.gpt-oss-120b-1:0"
  bedrock_model_pass2 = "openai.gpt-oss-120b-1:0"
  bedrock_model_pass3 = "openai.gpt-oss-120b-1:0"

  python_deps_layer_arn = aws_lambda_layer_version.python_dependencies.arn
  awswrangler_layer_arn = "arn:aws:lambda:${var.aws_region}:336392948345:layer:AWSSDKPandas-Python312:14"
}

# Outputs
output "ai_enrichment_step_functions_arn" {
  value = module.ai_enrichment.step_functions_arn
}

output "ai_enrichment_step_functions_name" {
  value = module.ai_enrichment.step_functions_name
}
```

---

## Validation Checklist

### Infrastructure

- [ ] `terraform plan` shows all resources
- [ ] Lambda IAM role has Bedrock, S3, CloudWatch permissions
- [ ] Step Functions IAM role has Lambda invoke permissions
- [ ] EventBridge IAM role has Step Functions start permissions
- [ ] Lambda layers are correctly referenced
- [ ] Reserved concurrency set on EnrichPartition Lambda

### DiscoverPartitions Lambda

- [ ] Lists Silver partitions correctly with awswrangler
- [ ] Lists Silver-AI partitions correctly
- [ ] Computes diff (Silver - Silver-AI)
- [ ] Sorts by date (oldest first)
- [ ] Respects MAX_PARTITIONS limit
- [ ] Returns proper structure for Step Functions

### EnrichPartition Lambda

- [ ] Reads Parquet from Silver partition
- [ ] Processes all jobs in partition
- [ ] **CRITICAL: Per-record try/catch - never skip a record**
- [ ] **CRITICAL: Failed records get `pass{1,2,3}_success=False` + `enrichment_errors`**
- [ ] Merges original + enriched columns
- [ ] **CRITICAL: Always writes partition even with failures**
- [ ] Emits CloudWatch metrics
- [ ] Returns proper status for Step Functions

### Step Functions

- [ ] Discovery → Check → Map flow works
- [ ] Empty partitions handled (NoWorkToProcess)
- [ ] MaxConcurrency=5 for Map state
- [ ] Retry logic configured for transient errors
- [ ] Failed partitions don't stop others (Catch → PartitionFailed)
- [ ] Logging enabled

### EventBridge

- [ ] Schedule is correct (6 AM UTC daily)
- [ ] Target is Step Functions state machine
- [ ] IAM permissions allow start execution

### CloudWatch Metrics

- [ ] JobsProcessed metric emitted
- [ ] JobsSucceeded metric emitted
- [ ] TokensUsed metric emitted
- [ ] CostUSD metric emitted
- [ ] Pass success rates emitted
- [ ] Partition dimension included

---

## Deployment Steps

```bash
# 1. Initialize (if not already done)
cd infra/environments/dev
terraform init

# 2. Plan
terraform plan -out=tfplan

# 3. Review the plan carefully
# Verify:
# - Lambda functions created
# - Step Functions state machine created
# - EventBridge rule created
# - IAM roles and policies correct

# 4. Apply
terraform apply tfplan

# 5. Verify deployment
aws stepfunctions list-state-machines --query "stateMachines[?contains(name, 'ai-enrichment')]"
aws lambda list-functions --query "Functions[?contains(FunctionName, 'ai-')].[FunctionName,Runtime,MemorySize]"
aws events list-rules --query "Rules[?contains(Name, 'ai-enrichment')]"
```

---

## Manual Testing

### Test DiscoverPartitions

```bash
# Invoke directly
aws lambda invoke \
  --function-name data-engineer-jobs-ai-discover-dev \
  --payload '{}' \
  response.json

cat response.json
# Expected: {"has_work": true/false, "partitions": [...], ...}
```

### Test EnrichPartition

```bash
# Pick a partition from discover output
aws lambda invoke \
  --function-name data-engineer-jobs-ai-enrich-dev \
  --payload '{"partition": {"year": "2024", "month": "12", "day": "01", "hour": "00"}}' \
  response.json

cat response.json
# Expected: {"statusCode": 200, "jobs_processed": N, ...}
```

### Test Full Pipeline

```bash
# Start Step Functions execution
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:ACCOUNT:stateMachine:data-engineer-jobs-ai-enrichment-dev \
  --input '{}'

# Monitor execution
aws stepfunctions describe-execution \
  --execution-arn arn:aws:states:us-east-1:ACCOUNT:execution:data-engineer-jobs-ai-enrichment-dev:EXECUTION_ID
```

### Verify Output

```bash
# List Silver-AI partitions
aws s3 ls s3://data-engineer-jobs-silver-dev/linkedin_ai/ --recursive

# Download and inspect a file
aws s3 cp s3://data-engineer-jobs-silver-dev/linkedin_ai/year=2024/month=12/day=01/hour=00/data.parquet ./
python -c "import pandas as pd; print(pd.read_parquet('data.parquet').columns.tolist())"
```

### Check CloudWatch Metrics

```bash
# Get metrics
aws cloudwatch get-metric-statistics \
  --namespace DataEngineerJobs/AIEnrichment \
  --metric-name JobsProcessed \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Sum
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/lambdas/ai_enrichment/discover_partitions/handler.py` | COMPLETE | Full S3 partition discovery |
| `src/lambdas/ai_enrichment/enrich_partition/handler.py` | COMPLETE | Full S3 I/O and metrics |
| `infra/modules/ai_enrichment/step_functions.tf` | CREATE | State machine definition |
| `infra/modules/ai_enrichment/step_functions.iam.tf` | CREATE | Step Functions IAM |
| `infra/modules/ai_enrichment/eventbridge.tf` | CREATE | Daily trigger |
| `infra/modules/ai_enrichment/lambda_discover.tf` | CREATE | Discover Lambda resource |
| `infra/modules/ai_enrichment/lambda_enrich.tf` | CREATE | Enrich Lambda resource |
| `infra/modules/ai_enrichment/variables.tf` | MODIFY | Add new variables |
| `infra/modules/ai_enrichment/outputs.tf` | MODIFY | Add new outputs |
| `infra/environments/dev/main.tf` | MODIFY | Add module reference |

---

## Success Criteria

| Metric | Target | How to Verify |
|--------|--------|---------------|
| Terraform apply | Success, no errors | `terraform apply` completes |
| Lambda deploy | Both functions deployed | `aws lambda list-functions` |
| Step Functions | State machine created | `aws stepfunctions list-state-machines` |
| EventBridge | Rule active | `aws events describe-rule` |
| Discovery | Finds pending partitions | Invoke Lambda directly |
| Single partition | Processes without timeout | Invoke Lambda with test partition |
| Full pipeline | Completes via Step Functions | Start execution, monitor |
| Output schema | All columns present | Inspect Silver-AI Parquet |
| Metrics | Appear in CloudWatch | Check CloudWatch console |
| Cost | < $0.01 per partition test | Check `enrichment_cost_usd` |

---

## Post-Deployment

### Enable/Disable Schedule

```bash
# Disable daily trigger
aws events disable-rule --name data-engineer-jobs-ai-enrichment-daily-dev

# Enable daily trigger
aws events enable-rule --name data-engineer-jobs-ai-enrichment-daily-dev
```

### Manual Backfill

```bash
# Process all pending partitions
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:REGION:ACCOUNT:stateMachine:NAME \
  --input '{"source": "manual-backfill"}'
```

### Monitor Costs

Check CloudWatch metrics dashboard or query:

```bash
aws cloudwatch get-metric-statistics \
  --namespace DataEngineerJobs/AIEnrichment \
  --metric-name CostUSD \
  --dimensions Name=Partition,Value=* \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 86400 \
  --statistics Sum
```

---

## Sprint Complete

With Sprint 5 complete, the AI Enrichment Pipeline is fully deployed and operational:

✅ **Sprint 1:** Foundation - Terraform module, Lambda skeletons, Bedrock IAM
✅ **Sprint 2:** Pass 1 - Factual extraction with anti-hallucination
✅ **Sprint 3:** Pass 2 - Inference with cascading context
✅ **Sprint 4:** Pass 3 - Complex analysis with full context
✅ **Sprint 5:** Integration - Step Functions, EventBridge, S3 I/O, deployed

The pipeline will now automatically:
1. Run daily at 6 AM UTC
2. Discover unprocessed Silver partitions
3. Process up to 10 partitions in parallel (MaxConcurrency=5)
4. Enrich each job with 3-pass AI analysis
5. Write results to Silver-AI layer
6. Emit CloudWatch metrics for monitoring
