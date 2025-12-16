# SQS Queue for AI Enrichment Job Distribution
# FIFO queue for ordered processing with deduplication

resource "aws_sqs_queue" "jobs" {
  name                        = "${var.project_name}-${var.environment}-ai-enrichment-jobs.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
  deduplication_scope         = "messageGroup"
  fifo_throughput_limit       = "perMessageGroupId"

  # Visibility timeout should be longer than Step Function timeout
  visibility_timeout_seconds = 900 # 15 minutes

  # Message retention
  message_retention_seconds = 1209600 # 14 days

  # Receive wait time for long polling
  receive_wait_time_seconds = 20

  # Redrive policy for failed messages
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.jobs_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-ai-enrichment-jobs"
  })
}

# Dead Letter Queue for failed messages
resource "aws_sqs_queue" "jobs_dlq" {
  name                      = "${var.project_name}-${var.environment}-ai-enrichment-jobs-dlq.fifo"
  fifo_queue                = true
  message_retention_seconds = 1209600 # 14 days

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-ai-enrichment-jobs-dlq"
  })
}

# CloudWatch Alarm for DLQ messages (threshold configurable)
resource "aws_cloudwatch_metric_alarm" "dlq_messages" {
  alarm_name          = "${var.project_name}-${var.environment}-ai-enrichment-dlq-alarm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = var.dlq_alarm_threshold
  alarm_description   = "AI Enrichment jobs failed and moved to DLQ (>${var.dlq_alarm_threshold} messages)"
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.jobs_dlq.name
  }

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []
  ok_actions    = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []

  tags = local.common_tags
}
