#####################################
# SQS FIFO - Fila de Companies
#####################################
# Usando FIFO com MessageGroupId único para garantir:
# - Processamento sequencial (uma mensagem por vez)
# - Lambda só recebe próxima mensagem após terminar a atual
# - Controle de concorrência sem precisar de reserved_concurrent_executions
# Ref: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/fifo-queue-lambda-behavior.html

# Dead Letter Queue FIFO
resource "aws_sqs_queue" "companies_dlq" {
  name                        = "${var.project_name}-companies-to-fetch-dlq.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  message_retention_seconds   = 1209600 # 14 dias

  tags = {
    Name    = "${var.project_name}-companies-to-fetch-dlq"
    Purpose = "Dead letter queue for failed companies fetch messages"
  }
}

# Fila principal de companies - FIFO
resource "aws_sqs_queue" "companies_queue" {
  name                        = "${var.project_name}-companies-to-fetch.fifo"
  fifo_queue                  = true
  content_based_deduplication = true                # Deduplica por hash do conteúdo
  deduplication_scope         = "messageGroup"      # Deduplica dentro do grupo
  fifo_throughput_limit       = "perMessageGroupId" # Throughput por grupo

  visibility_timeout_seconds = 420   # 7 min - tempo para SF completar
  message_retention_seconds  = 86400 # 1 dia
  receive_wait_time_seconds  = 20    # Long polling

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.companies_dlq.arn
    maxReceiveCount     = 3 # 3 tentativas antes de ir para DLQ
  })

  tags = {
    Name    = "${var.project_name}-companies-to-fetch"
    Purpose = "Queue for companies to fetch from Bright Data - FIFO for concurrency control"
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
