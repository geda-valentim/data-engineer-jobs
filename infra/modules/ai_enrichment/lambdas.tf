# Lambda Functions for AI Enrichment Pipeline

# ═══════════════════════════════════════════════════════════════════════════════
# DiscoverPartitions Lambda
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_lambda_function" "discover_partitions" {
  function_name = "${var.project_name}-${var.environment}-ai-discover-partitions"
  description   = "Discovers Silver partitions pending AI enrichment and queues jobs to SQS"
  role          = aws_iam_role.ai_enrichment_lambda.arn
  handler       = "handler.handler"
  runtime       = local.lambda_runtime
  timeout       = 120
  memory_size   = 512

  filename         = data.archive_file.discover_partitions.output_path
  source_code_hash = data.archive_file.discover_partitions.output_base64sha256

  layers = [
    var.aws_sdk_pandas_layer_arn
  ]

  environment {
    variables = {
      SILVER_BUCKET          = var.silver_bucket_name
      SILVER_PREFIX          = var.silver_prefix
      SILVER_AI_PREFIX       = var.silver_ai_prefix
      MAX_PARTITIONS         = var.max_partitions_per_run
      PUBLISH_TO_SQS         = "true"
      SQS_QUEUE_URL          = aws_sqs_queue.jobs.url
      MAX_JOBS_PER_PARTITION = var.max_jobs_per_partition
      MIN_JOBS_TO_PUBLISH    = var.min_jobs_to_publish
      STATUS_TABLE           = aws_dynamodb_table.status.name
      LOOKBACK_DAYS          = var.lookback_days
    }
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-ai-discover-partitions"
  })
}

# ═══════════════════════════════════════════════════════════════════════════════
# InvokeEnrichment Lambda
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_lambda_function" "invoke_enrichment" {
  function_name = "${var.project_name}-${var.environment}-ai-invoke-enrichment"
  description   = "Consumes SQS jobs and starts Step Function executions for AI enrichment"
  role          = aws_iam_role.ai_enrichment_lambda.arn
  handler       = "handler.handler"
  runtime       = local.lambda_runtime
  timeout       = 30
  memory_size   = 256

  filename         = data.archive_file.invoke_enrichment.output_path
  source_code_hash = data.archive_file.invoke_enrichment.output_base64sha256

  # NOTE: Lock acquisition and job status tracking are handled by Step Function.
  # This Lambda only starts Step Function executions.
  environment {
    variables = {
      STEP_FUNCTION_ARN = aws_sfn_state_machine.ai_enrichment.arn
    }
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-invoke-enrichment"
  })
}

# SQS Trigger for InvokeEnrichment
resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.jobs.arn
  function_name    = aws_lambda_function.invoke_enrichment.arn
  batch_size       = var.sqs_batch_size
  enabled          = true

  # Enables partial batch failure reporting - only failed messages return to queue
  function_response_types = ["ReportBatchItemFailures"]
}

# ═══════════════════════════════════════════════════════════════════════════════
# CleanupLocks Lambda
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_lambda_function" "cleanup_locks" {
  function_name = "${var.project_name}-${var.environment}-ai-cleanup-locks"
  description   = "Releases orphaned locks from failed AI enrichment executions"
  role          = aws_iam_role.ai_enrichment_lambda.arn
  handler       = "handler.handler"
  runtime       = local.lambda_runtime
  timeout       = 30
  memory_size   = 128

  filename         = data.archive_file.cleanup_locks.output_path
  source_code_hash = data.archive_file.cleanup_locks.output_base64sha256

  environment {
    variables = {
      STEP_FUNCTION_ARN      = aws_sfn_state_machine.ai_enrichment.arn
      DYNAMO_SEMAPHORE_TABLE = aws_dynamodb_table.semaphore.name
      DYNAMO_STATUS_TABLE    = aws_dynamodb_table.status.name
      LOCK_TIMEOUT_MINUTES   = var.lock_timeout_minutes
    }
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-ai-cleanup-locks"
  })
}

# ═══════════════════════════════════════════════════════════════════════════════
# EnrichPartition Lambda
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_lambda_function" "enrich_partition" {
  function_name = "${var.project_name}-${var.environment}-ai-enrich-partition"
  description   = "Enriches job listings with AI-extracted skills using Amazon Bedrock"
  role          = aws_iam_role.ai_enrichment_lambda.arn
  handler       = "handler.handler"
  runtime       = local.lambda_runtime
  timeout       = var.enrich_partition_timeout
  memory_size   = 512

  # Reserved concurrency prevents throttling from other functions in the account
  # Set to max_concurrent + buffer for retry bursts
  reserved_concurrent_executions = var.max_concurrent_executions + 20

  filename         = data.archive_file.enrich_partition.output_path
  source_code_hash = data.archive_file.enrich_partition.output_base64sha256

  layers = [
    var.python_deps_layer_arn,
    var.aws_sdk_pandas_layer_arn
  ]

  environment {
    variables = {
      SILVER_BUCKET       = var.silver_bucket_name
      SILVER_PREFIX       = var.silver_prefix
      SILVER_AI_PREFIX    = var.silver_ai_prefix
      BRONZE_BUCKET       = var.bronze_bucket_name
      BRONZE_AI_PREFIX    = var.bronze_ai_prefix
      WRITE_TO_BRONZE     = "true"
      BEDROCK_MODEL_PASS1 = var.bedrock_model_pass1
      BEDROCK_MODEL_PASS2 = var.bedrock_model_pass2
      BEDROCK_MODEL_PASS3 = var.bedrock_model_pass3
      DYNAMO_STATUS_TABLE = aws_dynamodb_table.status.name
      # Circuit Breaker Configuration
      CIRCUIT_BREAKER_FAILURE_THRESHOLD = tostring(var.circuit_breaker_failure_threshold)
      CIRCUIT_BREAKER_RECOVERY_TIMEOUT  = tostring(var.circuit_breaker_recovery_timeout)
    }
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-enrich-partition"
  })
}

# ═══════════════════════════════════════════════════════════════════════════════
# CloudWatch Log Groups
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_cloudwatch_log_group" "discover_partitions" {
  name              = "/aws/lambda/${aws_lambda_function.discover_partitions.function_name}"
  retention_in_days = 30

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "invoke_enrichment" {
  name              = "/aws/lambda/${aws_lambda_function.invoke_enrichment.function_name}"
  retention_in_days = 30

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "cleanup_locks" {
  name              = "/aws/lambda/${aws_lambda_function.cleanup_locks.function_name}"
  retention_in_days = 30

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "enrich_partition" {
  name              = "/aws/lambda/${aws_lambda_function.enrich_partition.function_name}"
  retention_in_days = 30

  tags = local.common_tags
}
