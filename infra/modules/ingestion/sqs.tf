#####################################
# SQS - Fila de Ingestão
#####################################

# Dead Letter Queue para mensagens que falharam
resource "aws_sqs_queue" "ingestion_dlq" {
  name                      = "${var.project_name}-ingestion-dlq"
  message_retention_seconds = 1209600 # 14 dias

  tags = {
    Name    = "${var.project_name}-ingestion-dlq"
    Purpose = "Dead letter queue for failed ingestion messages"
  }
}

# Fila principal de ingestão
resource "aws_sqs_queue" "ingestion_queue" {
  name                       = "${var.project_name}-ingestion-queue"
  visibility_timeout_seconds = 900   # 15 min - tempo para Lambda processar
  message_retention_seconds  = 86400 # 1 dia
  receive_wait_time_seconds  = 20    # Long polling

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ingestion_dlq.arn
    maxReceiveCount     = 3 # 3 tentativas antes de ir para DLQ
  })

  tags = {
    Name    = "${var.project_name}-ingestion-queue"
    Purpose = "Queue for ingestion requests with throttling"
  }
}

# Policy para permitir que a DLQ receba mensagens
resource "aws_sqs_queue_redrive_allow_policy" "ingestion_dlq_allow" {
  queue_url = aws_sqs_queue.ingestion_dlq.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.ingestion_queue.arn]
  })
}
