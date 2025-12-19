# Outputs for Bronze to Silver Module

# =============================================================================
# Lambda Functions
# =============================================================================

output "discover_lambda_arn" {
  description = "ARN of the discover companies Lambda function"
  value       = aws_lambda_function.discover_companies.arn
}

output "discover_lambda_name" {
  description = "Name of the discover companies Lambda function"
  value       = aws_lambda_function.discover_companies.function_name
}

output "process_lambda_arn" {
  description = "ARN of the process companies Lambda function"
  value       = aws_lambda_function.process_companies.arn
}

output "process_lambda_name" {
  description = "Name of the process companies Lambda function"
  value       = aws_lambda_function.process_companies.function_name
}

# =============================================================================
# SQS Queues
# =============================================================================

output "queue_url" {
  description = "URL of the companies processing queue"
  value       = aws_sqs_queue.companies_queue.url
}

output "queue_arn" {
  description = "ARN of the companies processing queue"
  value       = aws_sqs_queue.companies_queue.arn
}

output "dlq_url" {
  description = "URL of the dead letter queue"
  value       = aws_sqs_queue.companies_dlq.url
}

output "dlq_arn" {
  description = "ARN of the dead letter queue"
  value       = aws_sqs_queue.companies_dlq.arn
}

# =============================================================================
# IAM
# =============================================================================

output "lambda_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda_execution.arn
}

output "lambda_role_name" {
  description = "Name of the Lambda execution role"
  value       = aws_iam_role.lambda_execution.name
}

# =============================================================================
# EventBridge
# =============================================================================

output "schedule_rule_arn" {
  description = "ARN of the EventBridge schedule rule"
  value       = aws_cloudwatch_event_rule.discover_schedule.arn
}

output "schedule_rule_name" {
  description = "Name of the EventBridge schedule rule"
  value       = aws_cloudwatch_event_rule.discover_schedule.name
}

# =============================================================================
# Configuration
# =============================================================================

output "silver_output_path" {
  description = "S3 path where Silver data is written"
  value       = "s3://${var.silver_bucket_name}/${var.silver_companies_prefix}"
}

output "num_buckets" {
  description = "Number of hash buckets for partitioning"
  value       = var.num_buckets
}
