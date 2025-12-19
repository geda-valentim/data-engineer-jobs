#####################################
# Lambda - AI Enrichment ETL
#####################################
# Consolidates AI enrichment results from Bronze (JSON) to Silver (Parquet)
#
# Execution:
# - Scheduled via EventBridge (every 30 minutes)
# - Can be invoked manually with specific job_ids
#
# Architecture:
# - Reads from Bronze: ai_enrichment/{job_id}/pass*.json
# - Writes to Silver: ai_enrichment/year=.../month=.../day=.../

# Zip do código da Lambda
data "archive_file" "ai_enrichment_etl" {
  type        = "zip"
  source_dir  = "${path.module}/../../../src/lambdas/ai_enrichment_etl"
  output_path = "${path.module}/.lambda_packages/ai_enrichment_etl.zip"
}

# Lambda Function
resource "aws_lambda_function" "ai_enrichment_etl" {
  function_name = "${var.project_name}-${var.environment}-ai-enrichment-etl"
  description   = "Consolidates AI enrichment from Bronze JSON to Silver Parquet"
  role          = aws_iam_role.ai_enrichment_lambda.arn
  handler       = "handler.handler"
  runtime       = local.lambda_runtime
  timeout       = 300 # 5 minutes
  memory_size   = 1024

  filename         = data.archive_file.ai_enrichment_etl.output_path
  source_code_hash = data.archive_file.ai_enrichment_etl.output_base64sha256

  layers = [
    var.aws_sdk_pandas_layer_arn
  ]

  environment {
    variables = {
      BRONZE_BUCKET        = var.bronze_bucket_name
      SILVER_BUCKET        = var.silver_bucket_name
      BRONZE_AI_PREFIX     = "ai_enrichment/"
      SILVER_AI_PREFIX     = "ai_enrichment/"
      SILVER_JOBS_PREFIX   = var.silver_prefix
      MAX_JOBS_PER_RUN     = tostring(var.etl_max_jobs_per_run)
      BATCH_SIZE           = "100"
      ETL_PROCESSED_TABLE  = aws_dynamodb_table.etl_processed.name
      STATUS_TABLE         = aws_dynamodb_table.status.name
    }
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-ai-enrichment-etl"
  })
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "ai_enrichment_etl" {
  name              = "/aws/lambda/${aws_lambda_function.ai_enrichment_etl.function_name}"
  retention_in_days = var.log_retention_days

  tags = local.common_tags
}

#####################################
# EventBridge Schedule - ETL
#####################################

resource "aws_cloudwatch_event_rule" "ai_enrichment_etl" {
  name                = "${var.project_name}-${var.environment}-ai-enrichment-etl"
  description         = "Triggers AI enrichment ETL (Bronze to Silver)"
  schedule_expression = var.etl_schedule_expression
  state               = var.enable_etl_schedule ? "ENABLED" : "DISABLED"

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "ai_enrichment_etl" {
  rule      = aws_cloudwatch_event_rule.ai_enrichment_etl.name
  target_id = "AIEnrichmentETL"
  arn       = aws_lambda_function.ai_enrichment_etl.arn
}

resource "aws_lambda_permission" "ai_enrichment_etl_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ai_enrichment_etl.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ai_enrichment_etl.arn
}
