#############################################
# Upload do script do Glue pro S3
#############################################

resource "aws_s3_object" "glue_skills_backfill_script" {
  bucket = var.glue_scripts_bucket_name
  key    = "glue/skills_backfill.py"

  source = "${path.module}/../../../src/glue_jobs/skills_backfill.py"
  etag   = filemd5("${path.module}/../../../src/glue_jobs/skills_backfill.py")
}

# Upload do módulo skill_matcher (dependência)
resource "aws_s3_object" "glue_skill_matcher_module" {
  bucket = var.glue_scripts_bucket_name
  key    = "glue/skills_detection/skill_matcher.py"

  source = "${path.module}/../../../src/skills_detection/skill_matcher.py"
  etag   = filemd5("${path.module}/../../../src/skills_detection/skill_matcher.py")
}

# __init__.py para o pacote
resource "aws_s3_object" "glue_skill_matcher_init" {
  bucket       = var.glue_scripts_bucket_name
  key          = "glue/skills_detection/__init__.py"
  content      = ""
  content_type = "text/x-python"
}

#############################################
# Glue Job Skills Backfill
#############################################

resource "aws_glue_job" "skills_backfill" {
  name     = "${var.project_name}-skills-backfill"
  role_arn = aws_iam_role.glue_bronze_to_silver_role.arn

  glue_version      = "4.0"
  number_of_workers = 4 # Mais workers para backfill
  worker_type       = "G.1X"

  command {
    name            = "glueetl"
    script_location = "s3://${var.glue_scripts_bucket_name}/${aws_s3_object.glue_skills_backfill_script.key}"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-spark-ui"                  = "true"
    "--TempDir"                          = "s3://${var.glue_temp_bucket_name}/temp/"
    "--silver_bucket"                    = var.silver_bucket_name
    "--source_system"                    = "linkedin"
    # Adiciona o diretório de scripts ao PYTHONPATH para imports
    "--extra-py-files"                   = "s3://${var.glue_scripts_bucket_name}/glue/skills_detection/skill_matcher.py"
  }

  max_retries = 0 # Backfill não deve ter retry automático
  timeout     = 120 # 2 horas para processar histórico
}
