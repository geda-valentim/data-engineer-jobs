variable "project_name" {
  type        = string
  description = "Nome base do projeto (prefixo de recursos)"
}

variable "bronze_bucket_name" {
  type = string
}

variable "silver_bucket_name" {
  type = string
}

variable "ingestion_cron_expression" {
  type        = string
  description = "Expression cron do EventBridge para disparar a ingestão"
  default     = "cron(0 * * * ? *)" # A cada hora no minuto 0
}

variable "lambda_exec_role_arn" {
  type        = string
  description = "IAM Role ARN usado pelas Lambdas de ingestão"
}

variable "aws_lambda_layer_version_python_dependencies" {
  type        = string
  description = "IAM Role ARN usado pelas Lambdas de ingestão"
}

variable "brightdata_api_key_param" {
  type        = string
  description = "Nome do parâmetro SSM com a API key do BrightData"
}


variable "ingestion_sources_seed" {
  description = "Fontes de ingestão para seed inicial no DynamoDB"
  type = list(object({
    source_id             = string
    source_type           = string         # "jobs_listing" etc.

    provider              = string         # "brightdata"
    dataset_kind          = string         # "snapshot"

    domain                = string         # "linkedin"
    entity                = string         # "jobs"

    brightdata_dataset_id = string
    brightdata_extra_params = map(string)  # include_errors, type, discover_by...

    request_urls          = list(string)
    request_url           = string         # URL base de request (se quiser logar)
    bronze_prefix         = string         # prefixo dentro do bronze
    file_format           = string         # "jsonl", "json", "csv"...

    enabled               = bool
    schedule_group        = string         # "daily_midday" etc.
    owner                 = string
  }))
  default = []
}

variable "glue_temp_bucket_name" {
  type = string
}

variable "glue_scripts_bucket_name" {
  type = string
}

variable "data_lake_bucket_name" {
  type        = string
  description = "Nome do bucket S3 do data lake (para backfill manifests)"
}

variable "data_lake_bucket_arn" {
  type        = string
  description = "ARN do bucket S3 do data lake"
}
