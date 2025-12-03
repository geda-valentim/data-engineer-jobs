data "archive_file" "dispatcher_lambda_code" {
  type        = "zip"
  source_dir  = "${path.module}/../../../src/scheduler"
  output_path = "${path.module}/lambda_packages/dispatcher.zip"
}
