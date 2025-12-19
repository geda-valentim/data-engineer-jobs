# EventBridge Rules for Bronze to Silver Pipeline

# =============================================================================
# Scheduled Discovery Rule
# =============================================================================

resource "aws_cloudwatch_event_rule" "discover_schedule" {
  name                = "${local.name_prefix}-b2s-discover-schedule"
  description         = "Triggers company discovery for Bronze to Silver ETL"
  schedule_expression = var.discover_schedule_expression
  state               = var.enable_schedule ? "ENABLED" : "DISABLED"

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "discover_lambda" {
  rule      = aws_cloudwatch_event_rule.discover_schedule.name
  target_id = "DiscoverCompaniesLambda"
  arn       = aws_lambda_function.discover_companies.arn

  # Pass mode in the event
  input = jsonencode({
    mode          = "discover"
    source        = "eventbridge"
    schedule_time = "<aws.scheduler.scheduled-time>"
  })
}

resource "aws_lambda_permission" "eventbridge_discover" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.discover_companies.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.discover_schedule.arn
}
