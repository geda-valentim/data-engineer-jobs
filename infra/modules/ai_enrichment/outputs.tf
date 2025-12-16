output "lambda_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.ai_enrichment_lambda.arn
}

output "lambda_role_name" {
  description = "Name of the Lambda execution role"
  value       = aws_iam_role.ai_enrichment_lambda.name
}

output "silver_ai_path" {
  description = "S3 path for Silver-AI output"
  value       = "s3://${var.silver_bucket_name}/${var.silver_ai_prefix}"
}

# Step Function
output "step_function_arn" {
  description = "ARN of the AI Enrichment Step Function"
  value       = aws_sfn_state_machine.ai_enrichment.arn
}

output "step_function_name" {
  description = "Name of the AI Enrichment Step Function"
  value       = aws_sfn_state_machine.ai_enrichment.name
}

# DynamoDB Tables
output "semaphore_table_name" {
  description = "Name of the DynamoDB semaphore table"
  value       = aws_dynamodb_table.semaphore.name
}

output "status_table_name" {
  description = "Name of the DynamoDB status table"
  value       = aws_dynamodb_table.status.name
}

# SQS Queue
output "jobs_queue_url" {
  description = "URL of the SQS jobs queue"
  value       = aws_sqs_queue.jobs.url
}

output "jobs_queue_arn" {
  description = "ARN of the SQS jobs queue"
  value       = aws_sqs_queue.jobs.arn
}

output "jobs_dlq_url" {
  description = "URL of the SQS dead letter queue"
  value       = aws_sqs_queue.jobs_dlq.url
}

# Bronze Output Path
output "bronze_ai_path" {
  description = "S3 path for Bronze AI enrichment output"
  value       = "s3://${var.bronze_bucket_name}/${var.bronze_ai_prefix}"
}
