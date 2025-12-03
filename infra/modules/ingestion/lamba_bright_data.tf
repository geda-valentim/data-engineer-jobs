resource "aws_lambda_function" "bright_data" {
  for_each = local.lambdas

  filename         = data.archive_file.lambda_code.output_path
  function_name    = "bright-data-${each.key}"
  role            = var.lambda_exec_role_arn
  handler         = each.value.handler
  runtime         = "python3.12"
  timeout         = each.value.timeout
  
  source_code_hash = data.archive_file.lambda_code.output_base64sha256

  layers = [var.aws_lambda_layer_version_python_dependencies]

  environment {
    variables = {
      BRIGHTDATA_API_KEY_PARAM = var.brightdata_api_key_param
      bronze_bucket_name  = var.bronze_bucket_name
      APP_TIMEZONE        = "America/Sao_Paulo"
    }
  }
}