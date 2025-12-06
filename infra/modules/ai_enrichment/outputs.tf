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
