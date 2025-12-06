# Lambda Code Packaging

locals {
  lambda_source_path = "${path.module}/../../../src/lambdas/ai_enrichment"
}

# DiscoverPartitions Lambda ZIP
data "archive_file" "discover_partitions" {
  type        = "zip"
  source_dir  = "${local.lambda_source_path}/discover_partitions"
  output_path = "${path.module}/.lambda_packages/discover_partitions.zip"
}

# EnrichPartition Lambda ZIP (includes all submodules)
data "archive_file" "enrich_partition" {
  type        = "zip"
  output_path = "${path.module}/.lambda_packages/enrich_partition.zip"

  source {
    content  = file("${local.lambda_source_path}/enrich_partition/handler.py")
    filename = "handler.py"
  }

  # Shared utilities
  source {
    content  = file("${local.lambda_source_path}/shared/__init__.py")
    filename = "shared/__init__.py"
  }
  source {
    content  = file("${local.lambda_source_path}/shared/s3_utils.py")
    filename = "shared/s3_utils.py"
  }

  # Note: Additional sources (prompts, parsers, flatteners) will be added in Sprints 2-4
}
