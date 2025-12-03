
# Lambda Layer com dependências Python
resource "aws_lambda_layer_version" "python_dependencies" {
  filename   = "../../layers/python-deps/layer.zip"
  layer_name = "bright-data-python-dependencies"

  compatible_runtimes = ["python3.12"]

  source_code_hash = filebase64sha256("../../layers/python-deps/layer.zip")
}
