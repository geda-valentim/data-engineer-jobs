#####################################
# SQS - Fila de Companies
#####################################

# Dead Letter Queue para mensagens que falharam
resource "aws_sqs_queue" "companies_dlq" {
  name                      = "${var.project_name}-companies-to-fetch-dlq"
  message_retention_seconds = 1209600 # 14 dias

  tags = {
    Name    = "${var.project_name}-companies-to-fetch-dlq"
    Purpose = "Dead letter queue for failed companies fetch messages"
  }
}

# Fila principal de companies
resource "aws_sqs_queue" "companies_queue" {
  name                       = "${var.project_name}-companies-to-fetch"
  visibility_timeout_seconds = 300 # 5 min - tempo para Lambda processar
  message_retention_seconds  = 86400 # 1 dia
  receive_wait_time_seconds  = 20 # Long polling

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.companies_dlq.arn
    maxReceiveCount     = 3 # 3 tentativas antes de ir para DLQ
  })

  tags = {
    Name    = "${var.project_name}-companies-to-fetch"
    Purpose = "Queue for companies to fetch from Bright Data"
  }
}

# Policy para permitir que a DLQ receba mensagens
resource "aws_sqs_queue_redrive_allow_policy" "companies_dlq_allow" {
  queue_url = aws_sqs_queue.companies_dlq.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.companies_queue.arn]
  })
}
