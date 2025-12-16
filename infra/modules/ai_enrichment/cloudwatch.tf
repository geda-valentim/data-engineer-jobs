# CloudWatch Alarms for AI Enrichment Pipeline Monitoring
# Error rate, latency, and operational health alarms

# ═══════════════════════════════════════════════════════════════════════════════
# Lambda Error Rate Alarm
# Triggers when EnrichPartition error rate exceeds threshold
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_cloudwatch_metric_alarm" "enrich_partition_error_rate" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-enrich-partition-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = var.error_rate_threshold
  alarm_description   = "EnrichPartition Lambda error rate >${var.error_rate_threshold}%"
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "error_rate"
    expression  = "(errors / invocations) * 100"
    label       = "Error Rate %"
    return_data = true
  }

  metric_query {
    id = "errors"
    metric {
      metric_name = "Errors"
      namespace   = "AWS/Lambda"
      period      = 300
      stat        = "Sum"
      dimensions = {
        FunctionName = aws_lambda_function.enrich_partition.function_name
      }
    }
  }

  metric_query {
    id = "invocations"
    metric {
      metric_name = "Invocations"
      namespace   = "AWS/Lambda"
      period      = 300
      stat        = "Sum"
      dimensions = {
        FunctionName = aws_lambda_function.enrich_partition.function_name
      }
    }
  }

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []
  ok_actions    = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  tags = local.common_tags
}

# ═══════════════════════════════════════════════════════════════════════════════
# Lambda Latency P99 Alarm
# Triggers when EnrichPartition P99 latency exceeds threshold
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_cloudwatch_metric_alarm" "enrich_partition_latency_p99" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-enrich-partition-latency-p99"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  extended_statistic  = "p99"
  threshold           = var.latency_p99_threshold_ms
  alarm_description   = "EnrichPartition Lambda P99 latency >${var.latency_p99_threshold_ms}ms"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.enrich_partition.function_name
  }

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []
  ok_actions    = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  tags = local.common_tags
}

# ═══════════════════════════════════════════════════════════════════════════════
# Step Function Execution Failed Alarm
# Triggers when Step Function executions fail
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_cloudwatch_metric_alarm" "step_function_failures" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-ai-enrichment-sf-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "AI Enrichment Step Function executions failing (>5 in 5 min)"
  treat_missing_data  = "notBreaching"

  dimensions = {
    StateMachineArn = aws_sfn_state_machine.ai_enrichment.arn
  }

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []
  ok_actions    = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  tags = local.common_tags
}

# ═══════════════════════════════════════════════════════════════════════════════
# Semaphore Lock Contention Alarm
# Monitors DynamoDB ConditionalCheckFailed - actual lock acquisition failures
# High values indicate max_concurrent_executions may be too low
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_cloudwatch_metric_alarm" "lock_contention" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.project_name}-${var.environment}-ai-enrichment-lock-contention"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ConditionalCheckFailedRequests"
  namespace           = "AWS/DynamoDB"
  period              = 300
  statistic           = "Sum"
  threshold           = var.lock_contention_threshold
  alarm_description   = "High lock contention (>${var.lock_contention_threshold} conditional check failures in 5min) - consider increasing max_concurrent_executions"
  treat_missing_data  = "notBreaching"

  dimensions = {
    TableName = aws_dynamodb_table.semaphore.name
  }

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  tags = local.common_tags
}

# ═══════════════════════════════════════════════════════════════════════════════
# CloudWatch Dashboard for AI Enrichment
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_cloudwatch_dashboard" "ai_enrichment" {
  count = var.enable_alarms ? 1 : 0

  dashboard_name = "${var.project_name}-${var.environment}-ai-enrichment"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "EnrichPartition - Invocations & Errors"
          region = var.aws_region
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.enrich_partition.function_name, { stat = "Sum", period = 60 }],
            [".", "Errors", ".", ".", { stat = "Sum", period = 60 }]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "EnrichPartition - Duration (P50, P99)"
          region = var.aws_region
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.enrich_partition.function_name, { stat = "p50", period = 60 }],
            [".", ".", ".", ".", { stat = "p99", period = 60 }]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Step Function Executions"
          region = var.aws_region
          metrics = [
            ["AWS/States", "ExecutionsStarted", "StateMachineArn", aws_sfn_state_machine.ai_enrichment.arn, { stat = "Sum", period = 60 }],
            [".", "ExecutionsSucceeded", ".", ".", { stat = "Sum", period = 60 }],
            [".", "ExecutionsFailed", ".", ".", { stat = "Sum", period = 60 }]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "SQS Queue Metrics"
          region = var.aws_region
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.jobs.name, { stat = "Average", period = 60 }],
            [".", "ApproximateAgeOfOldestMessage", ".", ".", { stat = "Maximum", period = 60 }],
            [".", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.jobs_dlq.name, { stat = "Sum", period = 60, label = "DLQ Messages" }]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "Lock Contention (Semaphore)"
          region = var.aws_region
          metrics = [
            ["AWS/DynamoDB", "ConditionalCheckFailedRequests", "TableName", aws_dynamodb_table.semaphore.name, { stat = "Sum", period = 60, label = "Lock Acquisition Retries" }],
            [".", "SuccessfulRequestLatency", ".", ".", "Operation", "UpdateItem", { stat = "Average", period = 60, label = "UpdateItem Latency (ms)" }]
          ]
          annotations = {
            horizontal = [
              {
                label = "Contention Threshold"
                value = var.lock_contention_threshold / 5 # Per minute (alarm is 5min)
              }
            ]
          }
        }
      }
    ]
  })
}
