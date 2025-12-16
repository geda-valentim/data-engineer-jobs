
module "storage" {
  source             = "../../modules/storage/"
  bronze_bucket_name = "data-engineer-jobs-bronze"
  silver_bucket_name = "data-engineer-jobs-silver"
  gold_bucket_name   = "data-engineer-jobs-gold"

  glue_temp_bucket_name   = "data-engineer-jobs-glue-temp"
  glue_scripts_bucket_name = "data-engineer-jobs-glue-scripts"

  athena_results_bucket_name = "data-engineer-jobs-athena-results"

}

module "ingestion" {
  source                   = "../../modules/ingestion"
  project_name             = var.project_name
  bronze_bucket_name       = module.storage.bronze_bucket_name
  silver_bucket_name       = module.storage.silver_bucket_name
  glue_temp_bucket_name    = module.storage.glue_temp_bucket_name
  glue_scripts_bucket_name = module.storage.glue_scripts_bucket_name

  # Bucket para backfill manifests (Distributed Map)
  data_lake_bucket_name = module.storage.bronze_bucket_name
  data_lake_bucket_arn  = module.storage.bronze_bucket_arn

  lambda_exec_role_arn = aws_iam_role.data_engineer_jobs_lambda_exec_role.arn
  aws_lambda_layer_version_python_dependencies = aws_lambda_layer_version.python_dependencies.arn

  brightdata_api_key_param = "${local.ssm_prefix}/brightdata/api-key"

  ingestion_sources_seed = local.ingestion_sources_seed
}

module "analytics" {
  source = "../../modules/analytics"

  project_name               = var.project_name
  silver_bucket_name         = module.storage.silver_bucket_name
  athena_results_bucket_name = module.storage.athena_results_bucket_name
}


#module "monitoring" {
#  source = "../../modules/monitoring"
#  project_name = var.project_name
#}

# AI Enrichment Module - 3-Pass Bedrock Pipeline
module "ai_enrichment" {
  source = "../../modules/ai_enrichment"

  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.region

  silver_bucket_name = module.storage.silver_bucket_name
  bronze_bucket_name = module.storage.bronze_bucket_name
  silver_prefix      = "linkedin/"
  silver_ai_prefix   = "linkedin_ai/"

  # Lambda Layers
  python_deps_layer_arn    = aws_lambda_layer_version.python_dependencies.arn
  aws_sdk_pandas_layer_arn = local.aws_sdk_pandas_layer_arn

  # openai.gpt-oss-120b-1:0: $0.00015/1K input, $0.0003/1K output (extremely cheap!)
  bedrock_model_pass1 = "openai.gpt-oss-120b-1:0"
  bedrock_model_pass2 = "openai.gpt-oss-120b-1:0"
  bedrock_model_pass3 = "openai.gpt-oss-120b-1:0"

  max_partitions_per_run = 10
}