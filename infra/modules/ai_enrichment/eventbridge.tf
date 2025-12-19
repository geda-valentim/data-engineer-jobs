# EventBridge Rules for AI Enrichment Pipeline
# - Scheduled discovery of new partitions
# - Scheduled cleanup of orphaned locks
# - Step Function failure notifications

# ═══════════════════════════════════════════════════════════════════════════════
# Scheduled Discovery Rule - Triggers DiscoverPartitions Lambda
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_cloudwatch_event_rule" "discover_schedule" {
  name                = "${var.project_name}-${var.environment}-ai-enrichment-discover"
  description         = "Periodically discover new partitions to process"
  schedule_expression = var.discover_schedule_expression

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "discover_lambda" {
  rule      = aws_cloudwatch_event_rule.discover_schedule.name
  target_id = "DiscoverPartitionsLambda"
  arn       = aws_lambda_function.discover_partitions.arn
}

resource "aws_lambda_permission" "eventbridge_discover" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.discover_partitions.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.discover_schedule.arn
}

# ═══════════════════════════════════════════════════════════════════════════════
# Scheduled Cleanup Rule
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_cloudwatch_event_rule" "cleanup_schedule" {
  name                = "${var.project_name}-${var.environment}-ai-enrichment-cleanup"
  description         = "Periodically clean up orphaned semaphore locks"
  schedule_expression = "rate(15 minutes)"

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "cleanup_lambda" {
  rule      = aws_cloudwatch_event_rule.cleanup_schedule.name
  target_id = "CleanupLocksLambda"
  arn       = aws_lambda_function.cleanup_locks.arn
}

resource "aws_lambda_permission" "eventbridge_cleanup" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cleanup_locks.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.cleanup_schedule.arn
}

# ═══════════════════════════════════════════════════════════════════════════════
# Step Function Failure Rule
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_cloudwatch_event_rule" "sfn_failure" {
  name        = "${var.project_name}-${var.environment}-ai-enrichment-sfn-failure"
  description = "Trigger cleanup when Step Function execution fails"

  event_pattern = jsonencode({
    source      = ["aws.states"]
    detail-type = ["Step Functions Execution Status Change"]
    detail = {
      status          = ["FAILED", "TIMED_OUT", "ABORTED"]
      stateMachineArn = [aws_sfn_state_machine.ai_enrichment.arn]
    }
  })

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "sfn_failure_cleanup" {
  rule      = aws_cloudwatch_event_rule.sfn_failure.name
  target_id = "CleanupLocksOnFailure"
  arn       = aws_lambda_function.cleanup_locks.arn

  # Transform event to include only what we need
  input_transformer {
    input_paths = {
      executionArn = "$.detail.executionArn"
      status       = "$.detail.status"
    }
    input_template = <<EOF
{
  "source": "step-function-failure",
  "executionArn": <executionArn>,
  "status": <status>
}
EOF
  }
}

resource "aws_lambda_permission" "eventbridge_sfn_failure" {
  statement_id  = "AllowEventBridgeSfnFailure"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cleanup_locks.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.sfn_failure.arn
}
