# Lambda Code Packaging
# Creates ZIP archives for Lambda deployment

# =============================================================================
# Discover Companies Lambda
# =============================================================================

data "archive_file" "discover_companies" {
  type        = "zip"
  output_path = "${path.module}/.lambda_packages/discover_companies.zip"

  source {
    content  = file("${path.module}/../../../src/lambdas/bronze_to_silver/companies/handler.py")
    filename = "handler.py"
  }

  source {
    content  = file("${path.module}/../../../src/lambdas/bronze_to_silver/companies/schema.py")
    filename = "schema.py"
  }

  source {
    content  = file("${path.module}/../../../src/lambdas/bronze_to_silver/companies/transformer.py")
    filename = "transformer.py"
  }

  source {
    content  = file("${path.module}/../../../src/lambdas/bronze_to_silver/companies/__init__.py")
    filename = "__init__.py"
  }

  # Shared utilities
  source {
    content  = file("${path.module}/../../../src/lambdas/bronze_to_silver/shared/s3_utils.py")
    filename = "shared/s3_utils.py"
  }

  source {
    content  = file("${path.module}/../../../src/lambdas/bronze_to_silver/shared/company_lookup.py")
    filename = "shared/company_lookup.py"
  }

  source {
    content  = file("${path.module}/../../../src/lambdas/bronze_to_silver/shared/__init__.py")
    filename = "shared/__init__.py"
  }
}

# =============================================================================
# Process Companies Lambda (same code, different handler)
# =============================================================================

data "archive_file" "process_companies" {
  type        = "zip"
  output_path = "${path.module}/.lambda_packages/process_companies.zip"

  source {
    content  = file("${path.module}/../../../src/lambdas/bronze_to_silver/companies/handler.py")
    filename = "handler.py"
  }

  source {
    content  = file("${path.module}/../../../src/lambdas/bronze_to_silver/companies/schema.py")
    filename = "schema.py"
  }

  source {
    content  = file("${path.module}/../../../src/lambdas/bronze_to_silver/companies/transformer.py")
    filename = "transformer.py"
  }

  source {
    content  = file("${path.module}/../../../src/lambdas/bronze_to_silver/companies/__init__.py")
    filename = "__init__.py"
  }

  # Shared utilities
  source {
    content  = file("${path.module}/../../../src/lambdas/bronze_to_silver/shared/s3_utils.py")
    filename = "shared/s3_utils.py"
  }

  source {
    content  = file("${path.module}/../../../src/lambdas/bronze_to_silver/shared/company_lookup.py")
    filename = "shared/company_lookup.py"
  }

  source {
    content  = file("${path.module}/../../../src/lambdas/bronze_to_silver/shared/__init__.py")
    filename = "shared/__init__.py"
  }
}
