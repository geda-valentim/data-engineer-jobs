########################################
# Glue Database
########################################

resource "aws_glue_catalog_database" "data_engineer_jobs" {
  # Usa underscores para evitar problemas de sintaxe SQL com hífens
  name = replace("${var.project_name}_db", "-", "_")
}

########################################
# Athena Workgroup
########################################

resource "aws_athena_workgroup" "this" {
  name = "${var.project_name}-wg"

  configuration {
    enforce_workgroup_configuration = true

    result_configuration {
      output_location = "s3://${var.athena_results_bucket_name}/results/"
    }
  }

  description = "Workgroup do Athena para o projeto ${var.project_name}"
}
