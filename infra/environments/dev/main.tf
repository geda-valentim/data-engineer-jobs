
module "storage" {
  source             = "../../modules/storage/"
  bronze_bucket_name = "data-engineer-jobs-bronze"
  silver_bucket_name = "data-engineer-jobs-silver"
  gold_bucket_name   = "data-engineer-jobs-gold"

  glue_temp_bucket_name   = "data-engineer-jobs-glue-temp"
  glue_scripts_bucket_name = "data-engineer-jobs-glue-scripts"
}

module "ingestion" {
  source                  = "../../modules/ingestion"
  project_name            = var.project_name
  bronze_bucket_name      = module.storage.bronze_bucket_name
  silver_bucket_name      = module.storage.silver_bucket_name
  glue_temp_bucket_name   = module.storage.glue_temp_bucket_name
  glue_scripts_bucket_name = module.storage.glue_scripts_bucket_name

  lambda_exec_role_arn = aws_iam_role.data_engineer_jobs_lambda_exec_role.arn
  aws_lambda_layer_version_python_dependencies = aws_lambda_layer_version.python_dependencies.arn

  brightdata_api_key_param = "${local.ssm_prefix}/brightdata/api-key"

  ingestion_sources_seed = local.ingestion_sources_seed
}

#module "monitoring" {
#  source = "../../modules/monitoring"
#  project_name = var.project_name
#}