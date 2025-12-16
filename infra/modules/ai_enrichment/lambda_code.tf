# Lambda Code Packaging

locals {
  lambda_source_path = "${path.module}/../../../src/lambdas/ai_enrichment"
}

# ═══════════════════════════════════════════════════════════════════════════════
# DiscoverPartitions Lambda ZIP
# ═══════════════════════════════════════════════════════════════════════════════

data "archive_file" "discover_partitions" {
  type        = "zip"
  output_path = "${path.module}/.lambda_packages/discover_partitions.zip"

  source {
    content  = file("${local.lambda_source_path}/discover_partitions/handler.py")
    filename = "handler.py"
  }
}

# ═══════════════════════════════════════════════════════════════════════════════
# InvokeEnrichment Lambda ZIP
# NOTE: This Lambda only starts Step Function executions. Lock/status management
#       is handled by the Step Function directly via DynamoDB.
# ═══════════════════════════════════════════════════════════════════════════════

data "archive_file" "invoke_enrichment" {
  type        = "zip"
  output_path = "${path.module}/.lambda_packages/invoke_enrichment.zip"

  source {
    content  = file("${local.lambda_source_path}/invoke_enrichment/handler.py")
    filename = "handler.py"
  }
}

# ═══════════════════════════════════════════════════════════════════════════════
# CleanupLocks Lambda ZIP
# ═══════════════════════════════════════════════════════════════════════════════

data "archive_file" "cleanup_locks" {
  type        = "zip"
  output_path = "${path.module}/.lambda_packages/cleanup_locks.zip"

  source {
    content  = file("${local.lambda_source_path}/cleanup_locks/handler.py")
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
  source {
    content  = file("${local.lambda_source_path}/shared/dynamo_utils.py")
    filename = "shared/dynamo_utils.py"
  }
}

# ═══════════════════════════════════════════════════════════════════════════════
# EnrichPartition Lambda ZIP (includes all submodules)
# ═══════════════════════════════════════════════════════════════════════════════

data "archive_file" "enrich_partition" {
  type        = "zip"
  output_path = "${path.module}/.lambda_packages/enrich_partition.zip"

  # Main handler
  source {
    content  = file("${local.lambda_source_path}/enrich_partition/handler.py")
    filename = "handler.py"
  }
  source {
    content  = file("${local.lambda_source_path}/enrich_partition/__init__.py")
    filename = "__init__.py"
  }
  source {
    content  = file("${local.lambda_source_path}/enrich_partition/bedrock_client.py")
    filename = "bedrock_client.py"
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
  source {
    content  = file("${local.lambda_source_path}/shared/dynamo_utils.py")
    filename = "shared/dynamo_utils.py"
  }

  # Prompts
  source {
    content  = file("${local.lambda_source_path}/enrich_partition/prompts/__init__.py")
    filename = "prompts/__init__.py"
  }
  source {
    content  = file("${local.lambda_source_path}/enrich_partition/prompts/pass1_extraction.py")
    filename = "prompts/pass1_extraction.py"
  }
  source {
    content  = file("${local.lambda_source_path}/enrich_partition/prompts/pass2_inference.py")
    filename = "prompts/pass2_inference.py"
  }
  source {
    content  = file("${local.lambda_source_path}/enrich_partition/prompts/pass3_complex.py")
    filename = "prompts/pass3_complex.py"
  }

  # Parsers
  source {
    content  = file("${local.lambda_source_path}/enrich_partition/parsers/__init__.py")
    filename = "parsers/__init__.py"
  }
  source {
    content  = file("${local.lambda_source_path}/enrich_partition/parsers/json_parser.py")
    filename = "parsers/json_parser.py"
  }
  source {
    content  = file("${local.lambda_source_path}/enrich_partition/parsers/validators.py")
    filename = "parsers/validators.py"
  }

  # Flatteners
  source {
    content  = file("${local.lambda_source_path}/enrich_partition/flatteners/__init__.py")
    filename = "flatteners/__init__.py"
  }
  source {
    content  = file("${local.lambda_source_path}/enrich_partition/flatteners/extraction.py")
    filename = "flatteners/extraction.py"
  }
  source {
    content  = file("${local.lambda_source_path}/enrich_partition/flatteners/inference.py")
    filename = "flatteners/inference.py"
  }
  source {
    content  = file("${local.lambda_source_path}/enrich_partition/flatteners/analysis.py")
    filename = "flatteners/analysis.py"
  }
}
