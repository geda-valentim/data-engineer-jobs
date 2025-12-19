# Lambda Functions for Bronze to Silver ETL
# Two functions: discover (find new companies) and process (transform to Parquet)

# =============================================================================
# Discover Companies Lambda
# =============================================================================
# Triggered by EventBridge schedule
# Lists company partitions in Bronze, sends batches to SQS

resource "aws_lambda_function" "discover_companies" {
  function_name = "${local.name_prefix}-b2s-discover-companies"
  description   = "Discovers company partitions in Bronze bucket and queues for processing"

  filename         = data.archive_file.discover_companies.output_path
  source_code_hash = data.archive_file.discover_companies.output_base64sha256
  handler          = "handler.handler"
  runtime          = local.lambda_runtime

  role        = aws_iam_role.lambda_execution.arn
  timeout     = 60
  memory_size = 256

  layers = compact([
    var.python_deps_layer_arn,
    var.aws_sdk_pandas_layer_arn,
  ])

  environment {
    variables = {
      BRONZE_BUCKET           = var.bronze_bucket_name
      SILVER_BUCKET           = var.silver_bucket_name
      BRONZE_PREFIX           = var.bronze_companies_prefix
      SILVER_PREFIX           = var.silver_companies_prefix
      SQS_QUEUE_URL           = aws_sqs_queue.companies_queue.url
      MAX_COMPANIES_PER_BATCH = tostring(var.max_companies_per_batch)
      NUM_BUCKETS             = tostring(var.num_buckets)
      MODE                    = "discover"
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-b2s-discover-companies"
  })
}

resource "aws_cloudwatch_log_group" "discover_companies" {
  name              = "/aws/lambda/${aws_lambda_function.discover_companies.function_name}"
  retention_in_days = var.log_retention_days

  tags = local.common_tags
}

# =============================================================================
# Process Companies Lambda
# =============================================================================
# Triggered by SQS queue
# Reads company JSONs, transforms to Parquet, writes to Silver

resource "aws_lambda_function" "process_companies" {
  function_name = "${local.name_prefix}-b2s-process-companies"
  description   = "Transforms company JSON from Bronze to Parquet in Silver"

  filename         = data.archive_file.process_companies.output_path
  source_code_hash = data.archive_file.process_companies.output_base64sha256
  handler          = "handler.handler"
  runtime          = local.lambda_runtime

  role        = aws_iam_role.lambda_execution.arn
  timeout     = var.process_lambda_timeout
  memory_size = var.process_lambda_memory

  layers = compact([
    var.python_deps_layer_arn,
    var.aws_sdk_pandas_layer_arn,
  ])

  environment {
    variables = {
      BRONZE_BUCKET           = var.bronze_bucket_name
      SILVER_BUCKET           = var.silver_bucket_name
      BRONZE_PREFIX           = var.bronze_companies_prefix
      SILVER_PREFIX           = var.silver_companies_prefix
      MAX_COMPANIES_PER_BATCH = tostring(var.max_companies_per_batch)
      NUM_BUCKETS             = tostring(var.num_buckets)
      MODE                    = "batch"
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-b2s-process-companies"
  })
}

resource "aws_cloudwatch_log_group" "process_companies" {
  name              = "/aws/lambda/${aws_lambda_function.process_companies.function_name}"
  retention_in_days = var.log_retention_days

  tags = local.common_tags
}

# =============================================================================
# SQS Trigger for Process Lambda
# =============================================================================

resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.companies_queue.arn
  function_name    = aws_lambda_function.process_companies.arn
  batch_size       = var.sqs_batch_size
  enabled          = true

  # Report individual message failures (partial batch response)
  function_response_types = ["ReportBatchItemFailures"]

  # Scale based on queue depth
  scaling_config {
    maximum_concurrency = 10
  }
}
