#####################################
# Outputs - Ingestion Module
#####################################

# SQS
output "ingestion_queue_url" {
  description = "URL da fila SQS de ingestão"
  value       = aws_sqs_queue.ingestion_queue.url
}

output "ingestion_queue_arn" {
  description = "ARN da fila SQS de ingestão"
  value       = aws_sqs_queue.ingestion_queue.arn
}

output "ingestion_dlq_url" {
  description = "URL da DLQ de ingestão"
  value       = aws_sqs_queue.ingestion_dlq.url
}

output "ingestion_dlq_arn" {
  description = "ARN da DLQ de ingestão"
  value       = aws_sqs_queue.ingestion_dlq.arn
}

# Lambdas
output "queue_consumer_function_name" {
  description = "Nome da Lambda queue consumer"
  value       = aws_lambda_function.queue_consumer.function_name
}

output "backfill_fanout_function_name" {
  description = "Nome da Lambda backfill fan-out"
  value       = aws_lambda_function.backfill_fanout.function_name
}

output "backfill_fanout_function_arn" {
  description = "ARN da Lambda backfill fan-out"
  value       = aws_lambda_function.backfill_fanout.arn
}

# Step Function
output "state_machine_arn" {
  description = "ARN da Step Function de ingestão"
  value       = aws_sfn_state_machine.bright_data_snapshot_ingestion.arn
}

# Glue Jobs
output "bronze_to_silver_job_name" {
  description = "Nome do Glue Job Bronze to Silver"
  value       = aws_glue_job.bronze_to_silver.name
}
