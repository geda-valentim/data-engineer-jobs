#####################################
# Lambda - SQS Queue Consumer
#####################################

# Zip do código da Lambda
data "archive_file" "queue_consumer_zip" {
  type        = "zip"
  source_file = "${path.module}/../../../src/lambdas/queue_consumer/handler.py"
  output_path = "${path.module}/lambda_packages/queue_consumer.zip"
}

# Lambda Function
resource "aws_lambda_function" "queue_consumer" {
  function_name = "${var.project_name}-${var.environment}-ingestion-queue-consumer"
  description   = "Consumes ingestion jobs from SQS and triggers BrightData snapshot collection"
  role          = aws_iam_role.queue_consumer_role.arn
  handler       = "handler.handler"
  runtime       = "python3.11"
  timeout       = 60
  memory_size   = 128

  filename         = data.archive_file.queue_consumer_zip.output_path
  source_code_hash = data.archive_file.queue_consumer_zip.output_base64sha256

  # O throttling é controlado pela Lambda verificando execuções em andamento
  # antes de iniciar novas Step Functions (MAX_CONCURRENT_EXECUTIONS)

  environment {
    variables = {
      STATE_MACHINE_ARN         = aws_sfn_state_machine.bright_data_snapshot_ingestion.arn
      MAX_CONCURRENT_EXECUTIONS = "10"
    }
  }

  tags = {
    Name    = "${var.project_name}-queue-consumer"
    Purpose = "Consume SQS messages and start Step Functions"
  }
}

# Event Source Mapping - conecta SQS à Lambda
resource "aws_lambda_event_source_mapping" "queue_consumer_trigger" {
  event_source_arn = aws_sqs_queue.ingestion_queue.arn
  function_name    = aws_lambda_function.queue_consumer.arn
  batch_size       = 1 # Processa 1 mensagem por vez
  enabled          = true

  # Limita concorrência para não sobrecarregar Step Functions e Glue
  # max_concurrent_runs do Glue = 10, então limitamos a 10 lambdas paralelas
  scaling_config {
    maximum_concurrency = 10
  }

  # Se falhar, a mensagem volta pra fila após visibility timeout
  function_response_types = ["ReportBatchItemFailures"]
}

#####################################
# IAM Role - Queue Consumer
#####################################

resource "aws_iam_role" "queue_consumer_role" {
  name = "${var.project_name}-queue-consumer-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

# Permissão para logs
resource "aws_iam_role_policy_attachment" "queue_consumer_logs" {
  role       = aws_iam_role.queue_consumer_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Permissão para SQS
resource "aws_iam_role_policy" "queue_consumer_sqs" {
  name = "${var.project_name}-queue-consumer-sqs"
  role = aws_iam_role.queue_consumer_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.ingestion_queue.arn
      }
    ]
  })
}

# Permissão para Step Functions
resource "aws_iam_role_policy" "queue_consumer_sfn" {
  name = "${var.project_name}-queue-consumer-sfn"
  role = aws_iam_role.queue_consumer_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution",
          "states:ListExecutions"
        ]
        Resource = aws_sfn_state_machine.bright_data_snapshot_ingestion.arn
      }
    ]
  })
}
