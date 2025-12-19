# =============================================================================
# Core Configuration
# =============================================================================

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

# =============================================================================
# Data Sources - S3 Buckets
# =============================================================================

variable "bronze_bucket_name" {
  description = "Name of the Bronze S3 bucket (source)"
  type        = string
}

variable "silver_bucket_name" {
  description = "Name of the Silver S3 bucket (destination)"
  type        = string
}

variable "bronze_companies_prefix" {
  description = "S3 prefix for company JSON files in Bronze bucket"
  type        = string
  default     = "linkedin_companies/"
}

variable "silver_companies_prefix" {
  description = "S3 prefix for company Parquet files in Silver bucket"
  type        = string
  default     = "linkedin_companies/"
}

# =============================================================================
# Lambda Layers
# =============================================================================

variable "python_deps_layer_arn" {
  description = <<-EOT
    ARN of the Lambda layer containing Python dependencies.
    Should include: pyarrow, pandas, boto3, etc.
  EOT
  type        = string
}

variable "aws_sdk_pandas_layer_arn" {
  description = <<-EOT
    ARN of the AWS SDK Pandas layer (AWS managed).
    Example: arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python312:15
  EOT
  type        = string
  default     = ""
}

# =============================================================================
# Processing Configuration
# =============================================================================

variable "max_companies_per_batch" {
  description = <<-EOT
    Maximum number of companies to process per Lambda invocation.

    Scaling considerations:
    - Each company JSON is ~50KB avg
    - 100 companies ≈ 5MB input
    - Parquet output is ~10x smaller
    - Lambda memory should be 2x input size

    Recommended: 100-500 for 512MB Lambda
  EOT
  type        = number
  default     = 200
}

variable "sqs_batch_size" {
  description = <<-EOT
    Number of SQS messages per Lambda invocation.
    Each message contains a batch of company_ids.

    Recommended: 1-5 (since each message is already a batch)
  EOT
  type        = number
  default     = 1
}

variable "process_lambda_timeout" {
  description = <<-EOT
    Timeout in seconds for the process Lambda.

    Processing 200 companies typically takes 10-30 seconds.
    Set higher for safety margin.
  EOT
  type        = number
  default     = 120
}

variable "process_lambda_memory" {
  description = <<-EOT
    Memory in MB for the process Lambda.

    PyArrow + Pandas need ~256MB base.
    Add ~2MB per 100 companies.

    Recommended: 512-1024 MB
  EOT
  type        = number
  default     = 512
}

# =============================================================================
# Schedule Configuration
# =============================================================================

variable "discover_schedule_expression" {
  description = <<-EOT
    EventBridge schedule expression for discovery runs.

    Examples:
    - "rate(1 hour)" - Run every hour
    - "rate(6 hours)" - Run every 6 hours
    - "cron(0 2 * * ? *)" - Run at 2 AM UTC daily

    For initial bulk load, trigger manually or use "rate(5 minutes)"
  EOT
  type        = string
  default     = "rate(1 hour)"
}

variable "enable_schedule" {
  description = "Enable/disable the EventBridge schedule"
  type        = bool
  default     = true
}

# =============================================================================
# Monitoring Configuration
# =============================================================================

variable "enable_alarms" {
  description = "Enable CloudWatch alarms"
  type        = bool
  default     = true
}

variable "alarm_sns_topic_arn" {
  description = "SNS topic ARN for alarm notifications (optional)"
  type        = string
  default     = ""
}

variable "dlq_alarm_threshold" {
  description = "Number of messages in DLQ to trigger alarm"
  type        = number
  default     = 5
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

# =============================================================================
# Bucket Hash Configuration
# =============================================================================

variable "num_buckets" {
  description = <<-EOT
    Number of hash buckets for partitioning.

    This MUST match the value in company_lookup.py (NUM_BUCKETS).
    Changing this requires re-processing all data.

    Default: 50 (optimal for up to 500K companies)
  EOT
  type        = number
  default     = 50
}
