########################################
# Outputs do módulo Analytics
########################################

output "glue_database_name" {
  description = "Nome do Glue Database"
  value       = aws_glue_catalog_database.data_engineer_jobs.name
}

output "glue_table_name" {
  description = "Nome da tabela linkedin_silver"
  value       = aws_glue_catalog_table.linkedin_silver.name
}

output "athena_workgroup_name" {
  description = "Nome do Athena Workgroup"
  value       = aws_athena_workgroup.this.name
}

output "athena_workgroup_arn" {
  description = "ARN do Athena Workgroup"
  value       = aws_athena_workgroup.this.arn
}
