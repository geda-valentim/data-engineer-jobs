# 1. Zipar o código Python das Lambdas
data "archive_file" "lambda_code" {
  type        = "zip"
  source_dir  = "../../../src/lambdas/data_extractor/linkedin/job_listing/bright_data"
  output_path = "${path.module}/lambda_packages/bright-data.zip"
}

# 2. Definir as 3 Lambdas
locals {
  lambdas = {
    trigger = {
      handler     = "trigger.fetch_data_bright_jobs"
      description = "Triggers Bright Data collection and returns snapshot_id"
      handler = "trigger.fetch_data_bright_jobs"
      timeout = 300
    }
    check_status = {
      handler     = "check_status.get_snapshot_status"
      description = "Checks snapshot status and returns READY or PENDING"
      handler = "check_status.get_snapshot_status"
      timeout = 60
    }
    save_to_s3 = {
      handler     = "save_to_s3.save_to_s3"
      description = "Downloads data and saves to S3 Bronze"
      handler = "save_to_s3.save_to_s3"
      timeout = 300
    }
  }
}
