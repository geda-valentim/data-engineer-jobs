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

output "backfill_snapshot_downloader_function_name" {
  description = "Nome da Lambda backfill snapshot downloader"
  value       = aws_lambda_function.backfill_snapshot_downloader.function_name
}

output "backfill_snapshot_downloader_function_arn" {
  description = "ARN da Lambda backfill snapshot downloader"
  value       = aws_lambda_function.backfill_snapshot_downloader.arn
}

# Step Functions
output "state_machine_arn" {
  description = "ARN da Step Function de ingestão"
  value       = aws_sfn_state_machine.bright_data_snapshot_ingestion.arn
}

output "orchestrator_state_machine_arn" {
  description = "ARN da Step Function orquestradora (Distributed Map)"
  value       = aws_sfn_state_machine.backfill_orchestrator.arn
}

output "orchestrator_state_machine_name" {
  description = "Nome da Step Function orquestradora"
  value       = aws_sfn_state_machine.backfill_orchestrator.name
}

# Glue Jobs
output "bronze_to_silver_job_name" {
  description = "Nome do Glue Job Bronze to Silver"
  value       = aws_glue_job.bronze_to_silver.name
}

# Companies SQS
output "companies_queue_url" {
  description = "URL da fila SQS de companies"
  value       = aws_sqs_queue.companies_queue.url
}

output "companies_queue_arn" {
  description = "ARN da fila SQS de companies"
  value       = aws_sqs_queue.companies_queue.arn
}

output "companies_dlq_url" {
  description = "URL da DLQ de companies"
  value       = aws_sqs_queue.companies_dlq.url
}

# Companies DynamoDB
output "companies_status_table_name" {
  description = "Nome da tabela DynamoDB de status de companies"
  value       = aws_dynamodb_table.companies_status.name
}

output "companies_status_table_arn" {
  description = "ARN da tabela DynamoDB de status de companies"
  value       = aws_dynamodb_table.companies_status.arn
}

# Companies Lambda
output "companies_fetcher_function_name" {
  description = "Nome da Lambda companies fetcher"
  value       = aws_lambda_function.companies_fetcher.function_name
}

output "companies_fetcher_function_arn" {
  description = "ARN da Lambda companies fetcher"
  value       = aws_lambda_function.companies_fetcher.arn
}
