resource "aws_lambda_function" "ingestion_dispatcher" {
  function_name = "${var.project_name}-ingestion-dispatcher"

  filename         = data.archive_file.dispatcher_lambda_code.output_path
  source_code_hash = data.archive_file.dispatcher_lambda_code.output_base64sha256

  role    = var.lambda_exec_role_arn
  handler = "ingestion_dispatcher.handler"  # arquivo ingestion_dispatcher.py, função handler
  runtime = "python3.12"

  timeout = 60

  layers = [
    var.aws_lambda_layer_version_python_dependencies
  ]

  environment {
    variables = {
      INGESTION_SOURCES_TABLE_NAME = aws_dynamodb_table.ingestion_sources.name
      STATE_MACHINE_ARN            = aws_sfn_state_machine.bright_data_snapshot_ingestion.arn
    }
  }
}
