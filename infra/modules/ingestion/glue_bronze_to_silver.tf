#############################################
# Upload do script do Glue pro S3
#############################################

resource "aws_s3_object" "glue_bronze_to_silver_script" {
  bucket = var.glue_scripts_bucket_name
  key    = "glue/bronze_to_silver.py"

  # estamos em infra/modules/ingestion, executando de infra/environments/dev
  # path.module → infra/modules/ingestion
  # Subindo 3 níveis: ../../../ → raiz do projeto
  source = "${path.module}/../../../src/glue_jobs/bronze_to_silver.py"

  etag = filemd5("${path.module}/../../../src/glue_jobs/bronze_to_silver.py")
}

#############################################
# Glue Job Bronze → Silver
#############################################

resource "aws_glue_job" "bronze_to_silver" {
  name     = "${var.project_name}-bronze-to-silver"
  role_arn = aws_iam_role.glue_bronze_to_silver_role.arn

  glue_version      = "4.0"
  number_of_workers = 2
  worker_type       = "G.1X"
  execution_class   = "FLEX"

  # Permite múltiplas execuções simultâneas
  # Aumentado para suportar backfill de múltiplas regiões
  execution_property {
    max_concurrent_runs = 10
  }

  command {
    name            = "glueetl"
    script_location = "s3://${var.glue_scripts_bucket_name}/${aws_s3_object.glue_bronze_to_silver_script.key}"
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
    # Módulo de skills compartilhado
    "--extra-py-files" = "s3://${var.glue_scripts_bucket_name}/glue/skills_detection.zip"
  }

  depends_on = [aws_s3_object.glue_skills_detection_zip]

  max_retries = 1
  timeout     = 20
}