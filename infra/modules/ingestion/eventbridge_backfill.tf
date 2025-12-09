#####################################
# EventBridge Rule - Companies Backfill Daily Schedule
#####################################
# Triggers the companies backfill scanner Lambda daily at 3 AM UTC
# to discover and queue missing companies from Silver layer.

resource "aws_cloudwatch_event_rule" "companies_backfill_daily" {
  name                = "${var.project_name}-companies-backfill-daily"
  description         = "Trigger companies backfill scanner daily at 3 AM UTC"
  schedule_expression = "cron(0 3 * * ? *)" # 3 AM UTC every day

  tags = {
    Name    = "${var.project_name}-companies-backfill-daily"
    Purpose = "Daily schedule for companies backfill scanner"
  }
}

# Target: Lambda Function
resource "aws_cloudwatch_event_target" "companies_backfill_daily_target" {
  rule      = aws_cloudwatch_event_rule.companies_backfill_daily.name
  target_id = "CompaniesBackfillLambda"
  arn       = aws_lambda_function.companies_backfill_scanner.arn

  # Optional: Pass default configuration
  input = jsonencode({
    lookback_days  = 30
    max_partitions = 10
    force_mode     = false
    dry_run        = false
  })
}

# Permission for EventBridge to invoke Lambda
resource "aws_lambda_permission" "allow_eventbridge_backfill" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.companies_backfill_scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.companies_backfill_daily.arn
}
