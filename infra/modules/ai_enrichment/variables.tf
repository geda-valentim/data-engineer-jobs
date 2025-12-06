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
  description = "S3 prefix for Silver-AI layer data"
  type        = string
  default     = "linkedin_ai/"
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
