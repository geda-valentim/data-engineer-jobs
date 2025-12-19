variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "silver_bucket_name" {
  description = "Name of the Silver bucket (source data)"
  type        = string
}

variable "silver_prefix" {
  description = "S3 prefix for Silver layer data"
  type        = string
  default     = "linkedin/"
}

variable "silver_ai_prefix" {
  description = "S3 prefix for Silver-AI layer data (source-agnostic)"
  type        = string
  default     = "ai_enrichment/"
}

# Bedrock Model Configuration
# openai.gpt-oss-120b-1:0: $0.00015/1K input, $0.0003/1K output (extremely cheap!)
variable "bedrock_model_pass1" {
  description = "Bedrock model ID for Pass 1 (extraction)"
  type        = string
  default     = "openai.gpt-oss-120b-1:0"
}

variable "bedrock_model_pass2" {
  description = "Bedrock model ID for Pass 2 (inference)"
  type        = string
  default     = "openai.gpt-oss-120b-1:0"
}

variable "bedrock_model_pass3" {
  description = "Bedrock model ID for Pass 3 (analysis)"
  type        = string
  default     = "openai.gpt-oss-120b-1:0"
}

# Lambda Layers
variable "python_deps_layer_arn" {
  description = "ARN of existing bright-data-python-dependencies layer"
  type        = string
}

variable "aws_sdk_pandas_layer_arn" {
  description = "ARN of AWS managed SDK for Pandas layer"
  type        = string
}

# Processing Configuration
variable "max_partitions_per_run" {
  description = "Maximum partitions to process per Step Functions execution"
  type        = number
  default     = 10
}

variable "max_concurrent_executions" {
  description = <<-EOT
    Maximum concurrent Step Function executions (semaphore limit).

    Scaling considerations:
    - Each concurrent execution processes 1 job through 3 passes
    - With 180s per pass (worst case), throughput = N * 60 / 540 = N/9 jobs/min
    - Default 10 = ~1.1 jobs/min = ~66 jobs/hour
    - Set to 20 = ~2.2 jobs/min = ~133 jobs/hour
    - Set to 50 = ~5.5 jobs/min = ~333 jobs/hour

    Check your Bedrock quota before increasing:
    - us-east-1 default: 100 RPM for most models
    - Each job = 3 Bedrock calls, so max_concurrent = quota/3
  EOT
  type        = number
  default     = 10
}

variable "sqs_batch_size" {
  description = <<-EOT
    Number of SQS messages to process per Lambda invocation.

    Higher values improve throughput but require careful error handling.
    ReportBatchItemFailures is enabled to handle partial failures.

    - 1: Safe, sequential processing (default)
    - 5-10: Good balance of throughput and error isolation
    - 10+: High throughput, ensure Step Function handles failures gracefully
  EOT
  type        = number
  default     = 5
}

variable "enrich_partition_timeout" {
  description = <<-EOT
    Timeout in seconds for EnrichPartition Lambda.

    Each invocation processes a single pass (pass1/pass2/pass3).
    Bedrock calls typically complete in 10-60s depending on model and prompt size.

    - 180s: Default, adequate for most models
    - 300s: Recommended for slow models or large prompts
    - 600s: Maximum for complex analysis passes
  EOT
  type        = number
  default     = 180
}

variable "max_jobs_per_partition" {
  description = "Maximum jobs to process per partition"
  type        = number
  default     = 100
}

variable "min_jobs_to_publish" {
  description = "Minimum pending jobs to publish per discover run (backfill until target met)"
  type        = number
  default     = 100
}

variable "max_job_retries" {
  description = "Maximum retries for failed jobs before marking as permanently failed"
  type        = number
  default     = 3
}

# Bronze Bucket Configuration
variable "bronze_bucket_name" {
  description = "Name of the Bronze bucket (AI enrichment output)"
  type        = string
}

variable "bronze_ai_prefix" {
  description = "S3 prefix for Bronze AI enrichment data"
  type        = string
  default     = "ai_enrichment/"
}

# Cleanup Configuration
variable "lock_timeout_minutes" {
  description = "Minutes before a lock is considered orphaned"
  type        = number
  default     = 30
}

# EventBridge Schedules
variable "discover_schedule_expression" {
  description = "Schedule expression for DiscoverPartitions (e.g., 'rate(1 hour)' or 'cron(0 * * * ? *)')"
  type        = string
  default     = "rate(1 hour)"
}

# ═══════════════════════════════════════════════════════════════════════════════
# CloudWatch Alarms Configuration
# ═══════════════════════════════════════════════════════════════════════════════

variable "alarm_sns_topic_arn" {
  description = "SNS topic ARN for alarm notifications. Leave empty to disable notifications."
  type        = string
  default     = ""
}

variable "dlq_alarm_threshold" {
  description = "Number of DLQ messages to trigger alarm"
  type        = number
  default     = 10
}

variable "error_rate_threshold" {
  description = "Error rate percentage to trigger alarm (0-100)"
  type        = number
  default     = 5
}

variable "latency_p99_threshold_ms" {
  description = "P99 latency in milliseconds to trigger alarm"
  type        = number
  default     = 120000 # 120 seconds
}

variable "lock_contention_threshold" {
  description = <<-EOT
    Number of DynamoDB ConditionalCheckFailed events (in 5min) to trigger lock contention alarm.
    High values indicate the semaphore is frequently at capacity.
    Consider increasing max_concurrent_executions if this alarm fires.
  EOT
  type        = number
  default     = 50 # ~10 retries per minute = likely bottleneck
}

variable "enable_alarms" {
  description = "Enable CloudWatch alarms for monitoring"
  type        = bool
  default     = true
}

# ═══════════════════════════════════════════════════════════════════════════════
# Circuit Breaker Configuration
# ═══════════════════════════════════════════════════════════════════════════════

variable "circuit_breaker_failure_threshold" {
  description = "Number of failures before circuit opens"
  type        = number
  default     = 5
}

variable "circuit_breaker_recovery_timeout" {
  description = "Seconds to wait before attempting recovery (half-open state)"
  type        = number
  default     = 60
}

# ═══════════════════════════════════════════════════════════════════════════════
# ETL Configuration (Bronze AI → Silver AI)
# ═══════════════════════════════════════════════════════════════════════════════

variable "etl_schedule_expression" {
  description = "Schedule expression for AI Enrichment ETL (e.g., 'rate(30 minutes)')"
  type        = string
  default     = "rate(30 minutes)"
}

variable "enable_etl_schedule" {
  description = "Enable the ETL schedule"
  type        = bool
  default     = true
}

variable "etl_max_jobs_per_run" {
  description = "Maximum jobs to process per ETL run"
  type        = number
  default     = 500
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 14
}
