# SQS Queue for Company Processing Batches

# =============================================================================
# Main Queue
# =============================================================================

resource "aws_sqs_queue" "companies_queue" {
  name = "${local.name_prefix}-b2s-companies.fifo"

  # FIFO for ordered processing
  fifo_queue                  = true
  content_based_deduplication = true

  # Visibility timeout must exceed Lambda timeout
  visibility_timeout_seconds = var.process_lambda_timeout + 30

  # Message retention (14 days max)
  message_retention_seconds = 1209600

  # Long polling for efficiency
  receive_wait_time_seconds = 20

  # Dead letter queue
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.companies_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-b2s-companies"
  })
}

# =============================================================================
# Dead Letter Queue
# =============================================================================

resource "aws_sqs_queue" "companies_dlq" {
  name = "${local.name_prefix}-b2s-companies-dlq.fifo"

  fifo_queue                  = true
  content_based_deduplication = true
  message_retention_seconds   = 1209600 # 14 days

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-b2s-companies-dlq"
  })
}

# =============================================================================
# DLQ Alarm
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "dlq_messages" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-b2s-dlq-messages"
  alarm_description   = "Alert when messages land in Bronze-to-Silver DLQ"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = var.dlq_alarm_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.companies_dlq.name
  }

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  tags = local.common_tags
}
