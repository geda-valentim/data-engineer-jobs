# Step Function for AI Enrichment Pipeline
# Orchestrates 3-pass job enrichment with DynamoDB semaphore

resource "aws_sfn_state_machine" "ai_enrichment" {
  name     = "${var.project_name}-${var.environment}-ai-enrichment"
  role_arn = aws_iam_role.step_function.arn

  definition = templatefile("${path.module}/step_function_definition.json", {
    semaphore_table   = aws_dynamodb_table.semaphore.name
    status_table      = aws_dynamodb_table.status.name
    enrich_lambda_arn = aws_lambda_function.enrich_partition.arn
    max_concurrent    = var.max_concurrent_executions
    max_retries       = var.max_job_retries
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.step_function.arn}:*"
    include_execution_data = true
    level                  = "ERROR"
  }

  tracing_configuration {
    enabled = true
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-ai-enrichment-sfn"
  })
}

# CloudWatch Log Group for Step Function
resource "aws_cloudwatch_log_group" "step_function" {
  name              = "/aws/vendedlogs/states/${var.project_name}-${var.environment}-ai-enrichment"
  retention_in_days = 30

  tags = local.common_tags
}

# IAM Role for Step Function
resource "aws_iam_role" "step_function" {
  name = "${var.project_name}-${var.environment}-ai-enrichment-sfn-role"

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

  tags = local.common_tags
}

# IAM Policy for Step Function
resource "aws_iam_role_policy" "step_function" {
  name = "${var.project_name}-${var.environment}-ai-enrichment-sfn-policy"
  role = aws_iam_role.step_function.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvokeLambda"
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          aws_lambda_function.enrich_partition.arn,
          "${aws_lambda_function.enrich_partition.arn}:*"
        ]
      },
      {
        Sid    = "DynamoDBAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ]
        Resource = [
          aws_dynamodb_table.semaphore.arn,
          aws_dynamodb_table.status.arn
        ]
      },
      {
        Sid    = "CloudWatchLogs"
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
      },
      {
        Sid    = "XRayTracing"
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
