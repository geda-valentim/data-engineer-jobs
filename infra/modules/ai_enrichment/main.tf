# AI Enrichment Module
# Serverless pipeline for enriching job postings with AI-derived metadata

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

locals {
  lambda_runtime = "python3.12"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    Component   = "ai-enrichment"
    ManagedBy   = "terraform"
  }
}
