#############################################
# Upload do script do Glue pro S3
#############################################

resource "aws_s3_object" "glue_bronze_to_silver_backfill_script" {
  bucket = var.glue_scripts_bucket_name
  key    = "glue/bronze_to_silver_backfill.py"

  source = "${path.module}/../../../src/glue_jobs/bronze_to_silver_backfill.py"
  etag   = filemd5("${path.module}/../../../src/glue_jobs/bronze_to_silver_backfill.py")
}

#############################################
# Glue Job Bronze to Silver Backfill
#############################################

resource "aws_glue_job" "bronze_to_silver_backfill" {
  name     = "${var.project_name}-bronze-to-silver-backfill"
  role_arn = aws_iam_role.glue_bronze_to_silver_role.arn

  glue_version      = "4.0"
  number_of_workers = 4 # Mais workers para backfill
  worker_type       = "G.1X"

  command {
    name            = "glueetl"
    script_location = "s3://${var.glue_scripts_bucket_name}/${aws_s3_object.glue_bronze_to_silver_backfill_script.key}"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-spark-ui"                  = "true"
    "--TempDir"                          = "s3://${var.glue_temp_bucket_name}/temp/"
    "--bronze_bucket"                    = var.bronze_bucket_name
    "--silver_bucket"                    = var.silver_bucket_name
    "--source_system"                    = "linkedin"
    "--extra-py-files"                   = "s3://${var.glue_scripts_bucket_name}/glue/skills_detection.zip"
  }

  max_retries = 0   # Backfill não deve ter retry automático
  timeout     = 180 # 3 horas para processar histórico
}

#############################################
# Output
#############################################

output "bronze_to_silver_backfill_job_name" {
  description = "Nome do Glue Job Bronze to Silver Backfill"
  value       = aws_glue_job.bronze_to_silver_backfill.name
}
