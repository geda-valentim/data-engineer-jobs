resource "aws_cloudwatch_event_rule" "ingestion_schedule" {
  name                = "${var.project_name}-ingestion-schedule"
  description         = "Dispara o dispatcher de ingestão de jobs conforme o cron configurado"
  schedule_expression = var.ingestion_cron_expression
}

resource "aws_cloudwatch_event_target" "ingestion_schedule_dispatcher" {
  rule      = aws_cloudwatch_event_rule.ingestion_schedule.name
  target_id = "ingestion-dispatcher"
  arn       = aws_lambda_function.ingestion_dispatcher.arn
}

resource "aws_lambda_permission" "allow_eventbridge_invoke_dispatcher" {
  statement_id  = "AllowExecutionFromEventBridgeIngestionSchedule"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion_dispatcher.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ingestion_schedule.arn
}