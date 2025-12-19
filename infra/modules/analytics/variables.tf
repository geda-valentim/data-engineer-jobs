variable "project_name" {
  type = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "silver_bucket_name" {
  type        = string
  description = "Bucket S3 da camada Silver (ex: data-engineer-jobs-silver)"
}

variable "athena_results_bucket_name" {
  description = "Bucket onde o Athena grava os resultados"
  type        = string
}
