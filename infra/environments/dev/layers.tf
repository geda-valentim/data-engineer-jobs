
# Lambda Layer com dependências Python
resource "aws_lambda_layer_version" "python_dependencies" {
  filename   = "../../layers/python-deps/layer.zip"
  layer_name = "bright-data-python-dependencies"

  compatible_runtimes = ["python3.12"]

  source_code_hash = filebase64sha256("../../layers/python-deps/layer.zip")
}

# AWS Managed SDK for Pandas Layer (awswrangler)
# Used by AI Enrichment Lambdas for Parquet I/O
# ARN format: arn:aws:lambda:<region>:336392948345:layer:AWSSDKPandas-Python312:<version>
# See: https://aws-sdk-pandas.readthedocs.io/en/stable/layers.html
locals {
  aws_sdk_pandas_layer_arn = "arn:aws:lambda:${var.region}:336392948345:layer:AWSSDKPandas-Python312:13"
}

output "python_deps_layer_arn" {
  value = aws_lambda_layer_version.python_dependencies.arn
}

output "aws_sdk_pandas_layer_arn" {
  value = local.aws_sdk_pandas_layer_arn
}
