# Bronze to Silver ETL Module
# Transforms raw JSON data from Bronze layer to optimized Parquet in Silver layer

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.0"
    }
  }
}

locals {
  lambda_runtime = "python3.12"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    Component   = "bronze-to-silver"
    ManagedBy   = "terraform"
  }

  # Naming convention
  name_prefix = "${var.project_name}-${var.environment}"
}
