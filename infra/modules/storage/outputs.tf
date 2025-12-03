output "bronze_bucket_name" {
  description = "Nome do bucket bronze"
  value       = var.bronze_bucket_name
}

output "silver_bucket_name" {
  description = "Nome do bucket silver"
  value       = var.silver_bucket_name
}

output "gold_bucket_name" {
  description = "Nome do bucket gold"
  value       = var.gold_bucket_name
}

output "glue_temp_bucket_name" {
  description = "Nome do bucket temporário do Glue"
  value = aws_s3_bucket.glue_temp.bucket
}

output "glue_scripts_bucket_name" {
  description = "Nome do bucket de scripts do Glue"
  value = aws_s3_bucket.glue_scripts.bucket
}