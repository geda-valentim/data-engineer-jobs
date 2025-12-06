# Sprint 1: Foundation & Infrastructure

> **Duration:** 2-3 days
> **Goal:** Set up infrastructure scaffolding, Lambda layers, and Bedrock connectivity

---

## Objectives

1. Create Terraform module for AI enrichment
2. Configure Lambda layers (existing + AWS SDK for Pandas)
3. Set up Bedrock IAM permissions
4. Create Lambda function skeletons
5. Validate Bedrock connectivity with local test

---

## Tasks

### 1.1 Create Terraform Module Structure

**Location:** `infra/modules/ai_enrichment/`

```bash
mkdir -p infra/modules/ai_enrichment
```

**Files to create:**

| File | Purpose |
|------|---------|
| `main.tf` | Module entry point |
| `variables.tf` | Input variables |
| `outputs.tf` | Output values |
| `lambda_code.tf` | ZIP packaging |
| `lambda.iam.tf` | Lambda + Bedrock IAM |

#### variables.tf

```hcl
variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "silver_bucket_name" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "bedrock_model_pass1" {
  type    = string
  default = "openai.gpt-oss-120b-1:0"  # $0.00015/1K input, $0.0003/1K output
}

variable "bedrock_model_pass2" {
  type    = string
  default = "openai.gpt-oss-120b-1:0"
}

variable "bedrock_model_pass3" {
  type    = string
  default = "openai.gpt-oss-120b-1:0"
}

variable "python_deps_layer_arn" {
  type        = string
  description = "ARN of existing bright-data-python-dependencies layer"
}

variable "aws_sdk_pandas_layer_arn" {
  type        = string
  description = "ARN of AWS managed SDK for Pandas layer"
}
```

---

### 1.2 Configure Lambda Layers

**Modify:** `infra/environments/dev/layers.tf`

Add reference to AWS managed layer:

```hcl
# Existing layer
resource "aws_lambda_layer_version" "python_dependencies" {
  # ... existing config ...
}

# AWS managed SDK for Pandas layer
data "aws_lambda_layer_version" "aws_sdk_pandas" {
  layer_name = "AWSSDKPandas-Python312"
}

output "aws_sdk_pandas_layer_arn" {
  value = data.aws_lambda_layer_version.aws_sdk_pandas.arn
}
```

---

### 1.3 Create Lambda IAM Role

**File:** `infra/modules/ai_enrichment/lambda.iam.tf`

```hcl
# Lambda execution role
resource "aws_iam_role" "ai_enrichment_lambda" {
  name = "${var.project_name}-ai-enrichment-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

# CloudWatch Logs
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.ai_enrichment_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# S3 access (Silver bucket read, Silver-AI write)
resource "aws_iam_role_policy" "s3_access" {
  name = "s3-access"
  role = aws_iam_role.ai_enrichment_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.silver_bucket_name}",
          "arn:aws:s3:::${var.silver_bucket_name}/linkedin/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.silver_bucket_name}",
          "arn:aws:s3:::${var.silver_bucket_name}/linkedin_ai/*"
        ]
      }
    ]
  })
}

# Bedrock access (all foundation models)
resource "aws_iam_role_policy" "bedrock_access" {
  name = "bedrock-access"
  role = aws_iam_role.ai_enrichment_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ]
      Resource = [
        "arn:aws:bedrock:${var.aws_region}::foundation-model/*"
      ]
    }]
  })
}

# CloudWatch metrics
resource "aws_iam_role_policy" "cloudwatch_metrics" {
  name = "cloudwatch-metrics"
  role = aws_iam_role.ai_enrichment_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "cloudwatch:PutMetricData"
      ]
      Resource = "*"
      Condition = {
        StringEquals = {
          "cloudwatch:namespace" = "AIEnrichment"
        }
      }
    }]
  })
}
```

---

### 1.4 Create Lambda Code Structure

**Location:** `src/lambdas/ai_enrichment/`

```bash
mkdir -p src/lambdas/ai_enrichment/{discover_partitions,enrich_partition,shared}
mkdir -p src/lambdas/ai_enrichment/enrich_partition/{prompts,parsers,flatteners}
```

#### `__init__.py`

```python
"""AI Enrichment Lambda Package"""
```

#### `discover_partitions/handler.py`

```python
"""
Lambda: DiscoverPartitions
Finds Silver partitions that haven't been processed to Silver-AI yet.
"""

import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SILVER_BUCKET = os.environ.get("SILVER_BUCKET")
SOURCE_SYSTEM = os.environ.get("SOURCE_SYSTEM", "linkedin")


def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Discover partitions pending enrichment.

    Returns:
    {
        "partitions_count": int,
        "partitions": [
            {"year": "2025", "month": "12", "day": "05", "hour": "10"},
            ...
        ]
    }
    """
    logger.info("DiscoverPartitions started")

    # TODO: Implement in Sprint 5
    # 1. List Silver partitions
    # 2. List Silver-AI partitions
    # 3. Return diff

    return {
        "partitions_count": 0,
        "partitions": []
    }


if __name__ == "__main__":
    # Local testing
    from dotenv import load_dotenv
    load_dotenv()

    result = handler({}, None)
    print(result)
```

#### `enrich_partition/handler.py`

```python
"""
Lambda: EnrichPartition
Enriches a single partition with AI-derived metadata using 3-pass architecture.
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SILVER_BUCKET = os.environ.get("SILVER_BUCKET")
SOURCE_SYSTEM = os.environ.get("SOURCE_SYSTEM", "linkedin")
BEDROCK_MODEL_PASS1 = os.environ.get("BEDROCK_MODEL_PASS1", "openai.gpt-oss-120b-1:0")
BEDROCK_MODEL_PASS2 = os.environ.get("BEDROCK_MODEL_PASS2", "openai.gpt-oss-120b-1:0")
BEDROCK_MODEL_PASS3 = os.environ.get("BEDROCK_MODEL_PASS3", "openai.gpt-oss-120b-1:0")


def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Process a single partition for AI enrichment.

    Event:
    {
        "partition": {
            "year": "2025",
            "month": "12",
            "day": "05",
            "hour": "10"
        }
    }
    """
    partition = event.get("partition", {})
    year = partition.get("year")
    month = partition.get("month")
    day = partition.get("day")
    hour = partition.get("hour")

    logger.info(f"EnrichPartition started: year={year}/month={month}/day={day}/hour={hour}")

    # TODO: Implement in Sprints 2-5
    # 1. Read Silver Parquet
    # 2. For each job: Pass 1 → Pass 2 → Pass 3
    # 3. Merge columns
    # 4. Write Silver-AI Parquet

    return {
        "status": "not_implemented",
        "partition": partition,
        "enriched_at": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    # Local testing
    from dotenv import load_dotenv
    load_dotenv()

    test_event = {
        "partition": {
            "year": "2025",
            "month": "12",
            "day": "05",
            "hour": "10"
        }
    }
    result = handler(test_event, None)
    print(result)
```

#### `shared/__init__.py`

```python
"""Shared utilities for AI Enrichment"""
```

#### `shared/s3_utils.py`

```python
"""
S3 utilities for reading/writing Parquet files.
Uses AWS SDK for Pandas (awswrangler).
"""

import os
import logging
from typing import List, Dict, Optional

import awswrangler as wr
import pandas as pd

logger = logging.getLogger()

SILVER_BUCKET = os.environ.get("SILVER_BUCKET")
SOURCE_SYSTEM = os.environ.get("SOURCE_SYSTEM", "linkedin")


def get_silver_path(year: str, month: str, day: str, hour: str) -> str:
    """Build Silver partition path."""
    return f"s3://{SILVER_BUCKET}/{SOURCE_SYSTEM}/year={year}/month={month}/day={day}/hour={hour}/"


def get_silver_ai_path() -> str:
    """Build Silver-AI base path."""
    return f"s3://{SILVER_BUCKET}/{SOURCE_SYSTEM}_ai/"


def read_partition(year: str, month: str, day: str, hour: str) -> Optional[pd.DataFrame]:
    """
    Read a Silver partition as DataFrame.
    Returns None if partition doesn't exist.
    """
    path = get_silver_path(year, month, day, hour)
    logger.info(f"Reading partition: {path}")

    try:
        df = wr.s3.read_parquet(path=path)
        logger.info(f"Loaded {len(df)} records from {path}")
        return df
    except Exception as e:
        logger.warning(f"Could not read partition {path}: {e}")
        return None


def write_partition(df: pd.DataFrame, year: str, month: str, day: str, hour: str) -> str:
    """
    Write enriched DataFrame to Silver-AI.
    Returns the written path.
    """
    # Ensure partition columns are present
    df["year"] = year
    df["month"] = month
    df["day"] = day
    df["hour"] = hour

    base_path = get_silver_ai_path()
    logger.info(f"Writing {len(df)} records to {base_path}")

    # Write with partition overwrite
    wr.s3.to_parquet(
        df=df,
        path=base_path,
        dataset=True,
        partition_cols=["year", "month", "day", "hour"],
        mode="overwrite_partitions"
    )

    return f"{base_path}year={year}/month={month}/day={day}/hour={hour}/"


def list_silver_partitions() -> List[Dict[str, str]]:
    """List all Silver partitions."""
    base_path = f"s3://{SILVER_BUCKET}/{SOURCE_SYSTEM}/"

    try:
        paths = wr.s3.list_directories(path=base_path)
        partitions = []

        for path in paths:
            # Parse year=/month=/day=/hour= structure
            parts = path.replace(base_path, "").strip("/").split("/")
            if len(parts) >= 4:
                partition = {}
                for part in parts:
                    if "=" in part:
                        key, value = part.split("=", 1)
                        partition[key] = value
                if all(k in partition for k in ["year", "month", "day", "hour"]):
                    partitions.append(partition)

        return partitions
    except Exception as e:
        logger.error(f"Error listing Silver partitions: {e}")
        return []


def list_silver_ai_partitions() -> List[Dict[str, str]]:
    """List all Silver-AI partitions."""
    base_path = get_silver_ai_path()

    try:
        paths = wr.s3.list_directories(path=base_path)
        partitions = []

        for path in paths:
            parts = path.replace(base_path, "").strip("/").split("/")
            if len(parts) >= 4:
                partition = {}
                for part in parts:
                    if "=" in part:
                        key, value = part.split("=", 1)
                        partition[key] = value
                if all(k in partition for k in ["year", "month", "day", "hour"]):
                    partitions.append(partition)

        return partitions
    except Exception as e:
        logger.warning(f"Error listing Silver-AI partitions: {e}")
        return []
```

---

### 1.5 Create Lambda ZIP Packaging

**File:** `infra/modules/ai_enrichment/lambda_code.tf`

```hcl
# DiscoverPartitions Lambda
data "archive_file" "discover_partitions_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../../src/lambdas/ai_enrichment/discover_partitions"
  output_path = "${path.module}/lambda_packages/discover_partitions.zip"
}

# EnrichPartition Lambda (includes prompts, parsers, flatteners, shared)
data "archive_file" "enrich_partition_zip" {
  type        = "zip"
  output_path = "${path.module}/lambda_packages/enrich_partition.zip"

  source {
    content  = file("${path.module}/../../../src/lambdas/ai_enrichment/enrich_partition/handler.py")
    filename = "handler.py"
  }

  # Shared utilities
  source {
    content  = file("${path.module}/../../../src/lambdas/ai_enrichment/shared/__init__.py")
    filename = "shared/__init__.py"
  }
  source {
    content  = file("${path.module}/../../../src/lambdas/ai_enrichment/shared/s3_utils.py")
    filename = "shared/s3_utils.py"
  }

  # Prompts (to be added in Sprint 2-4)
  # Parsers (to be added in Sprint 2)
  # Flatteners (to be added in Sprint 2-4)
}
```

---

### 1.6 Integrate Module

**Modify:** `infra/environments/dev/main.tf`

```hcl
module "ai_enrichment" {
  source = "../../modules/ai_enrichment"

  project_name   = var.project_name
  environment    = var.environment
  aws_region     = var.aws_region

  silver_bucket_name = module.storage.silver_bucket_name

  python_deps_layer_arn    = aws_lambda_layer_version.python_dependencies.arn
  aws_sdk_pandas_layer_arn = data.aws_lambda_layer_version.aws_sdk_pandas.arn

  # openai.gpt-oss-120b-1:0: $0.00015/1K input, $0.0003/1K output (extremely cheap!)
  bedrock_model_pass1 = "openai.gpt-oss-120b-1:0"
  bedrock_model_pass2 = "openai.gpt-oss-120b-1:0"
  bedrock_model_pass3 = "openai.gpt-oss-120b-1:0"
}
```

---

### 1.7 Create Local Test Script

**File:** `scripts/test_enrichment_local.py`

```python
#!/usr/bin/env python3
"""
Local test script for AI Enrichment pipeline.
Tests Bedrock connectivity and basic functionality.
"""

import os
import sys
import json
from pathlib import Path

# Add src to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "lambdas" / "ai_enrichment"))

from dotenv import load_dotenv
import boto3

load_dotenv()


def test_bedrock_connectivity():
    """Test that we can connect to Bedrock and invoke a model."""
    print("=" * 60)
    print("Testing Bedrock connectivity...")
    print("=" * 60)

    region = os.getenv("AWS_REGION", "us-east-1")
    model_id = os.getenv("BEDROCK_MODEL_PASS1", "openai.gpt-oss-120b-1:0")

    print(f"Region: {region}")
    print(f"Model: {model_id}")

    try:
        client = boto3.client("bedrock-runtime", region_name=region)

        # Simple test prompt
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100,
            "messages": [
                {
                    "role": "user",
                    "content": "Say 'Bedrock connection successful!' and nothing else."
                }
            ]
        })

        response = client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json"
        )

        response_body = json.loads(response["body"].read())
        output_text = response_body["content"][0]["text"]

        print(f"\nResponse: {output_text}")
        print(f"\nInput tokens: {response_body.get('usage', {}).get('input_tokens', 'N/A')}")
        print(f"Output tokens: {response_body.get('usage', {}).get('output_tokens', 'N/A')}")
        print("\n✓ Bedrock connectivity test PASSED")
        return True

    except Exception as e:
        print(f"\n✗ Bedrock connectivity test FAILED: {e}")
        return False


def test_s3_silver_access():
    """Test that we can read from Silver bucket."""
    print("\n" + "=" * 60)
    print("Testing S3 Silver access...")
    print("=" * 60)

    bucket = os.getenv("SILVER_BUCKET")
    if not bucket:
        print("✗ SILVER_BUCKET environment variable not set")
        return False

    print(f"Bucket: {bucket}")

    try:
        import awswrangler as wr

        # List partitions
        base_path = f"s3://{bucket}/linkedin/"
        print(f"Listing: {base_path}")

        dirs = wr.s3.list_directories(path=base_path)
        print(f"Found {len(dirs)} year partitions")

        if dirs:
            # Try to read first partition
            first_dir = dirs[0]
            print(f"Sample partition: {first_dir}")

        print("\n✓ S3 Silver access test PASSED")
        return True

    except Exception as e:
        print(f"\n✗ S3 Silver access test FAILED: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print("AI Enrichment Pipeline - Local Test")
    print("=" * 60)

    results = []

    # Test 1: Bedrock
    results.append(("Bedrock connectivity", test_bedrock_connectivity()))

    # Test 2: S3
    results.append(("S3 Silver access", test_s3_silver_access()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
```

---

## Validation Checklist

- [ ] `terraform plan` shows Lambda resources without errors
- [ ] Lambda IAM role has Bedrock permissions for all models
- [ ] AWS SDK for Pandas layer is referenced correctly
- [ ] Directory structure created: `src/lambdas/ai_enrichment/`
- [ ] Local test script runs successfully:
  - [ ] Bedrock connectivity test passes
  - [ ] S3 Silver access test passes

---

## Files Created/Modified

| Action | File |
|--------|------|
| CREATE | `infra/modules/ai_enrichment/main.tf` |
| CREATE | `infra/modules/ai_enrichment/variables.tf` |
| CREATE | `infra/modules/ai_enrichment/outputs.tf` |
| CREATE | `infra/modules/ai_enrichment/lambda_code.tf` |
| CREATE | `infra/modules/ai_enrichment/lambda.iam.tf` |
| CREATE | `src/lambdas/ai_enrichment/__init__.py` |
| CREATE | `src/lambdas/ai_enrichment/discover_partitions/handler.py` |
| CREATE | `src/lambdas/ai_enrichment/enrich_partition/handler.py` |
| CREATE | `src/lambdas/ai_enrichment/shared/__init__.py` |
| CREATE | `src/lambdas/ai_enrichment/shared/s3_utils.py` |
| CREATE | `scripts/test_enrichment_local.py` |
| MODIFY | `infra/environments/dev/main.tf` |
| MODIFY | `infra/environments/dev/layers.tf` |

---

## Next Sprint

[Sprint 2: Pass 1 - Factual Extraction](sprint-2-pass1.md)
