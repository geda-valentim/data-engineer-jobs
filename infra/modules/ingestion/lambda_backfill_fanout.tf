#####################################
# Lambda - Backfill Fan-out
#####################################

# Zip do código da Lambda (inclui handler + config de geo_ids)
data "archive_file" "backfill_fanout_zip" {
  type        = "zip"
  output_path = "${path.module}/lambda_packages/backfill_fanout.zip"

  source {
    content  = file("${path.module}/../../../src/lambdas/backfill_fanout/handler.py")
    filename = "handler.py"
  }

  source {
    content  = file("${path.module}/../../../src/lambdas/data_extractor/linkedin/config/linkedin_geo_ids_flat.json")
    filename = "data_extractor/linkedin/config/linkedin_geo_ids_flat.json"
  }
}

# Lambda Function
resource "aws_lambda_function" "backfill_fanout" {
  function_name = "${var.project_name}-backfill-fanout"
  role          = aws_iam_role.backfill_fanout_role.arn
  handler       = "handler.handler"
  runtime       = "python3.11"
  timeout       = 300  # 5 min - pode enviar muitas mensagens
  memory_size   = 128

  filename         = data.archive_file.backfill_fanout_zip.output_path
  source_code_hash = data.archive_file.backfill_fanout_zip.output_base64sha256

  environment {
    variables = {
      INGESTION_QUEUE_URL = aws_sqs_queue.ingestion_queue.url
    }
  }

  tags = {
    Name    = "${var.project_name}-backfill-fanout"
    Purpose = "Send multiple messages to SQS for backfill operations"
  }
}

#####################################
# IAM Role - Backfill Fan-out
#####################################

resource "aws_iam_role" "backfill_fanout_role" {
  name = "${var.project_name}-backfill-fanout-role"

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
resource "aws_iam_role_policy_attachment" "backfill_fanout_logs" {
  role       = aws_iam_role.backfill_fanout_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Permissão para SQS
resource "aws_iam_role_policy" "backfill_fanout_sqs" {
  name = "${var.project_name}-backfill-fanout-sqs"
  role = aws_iam_role.backfill_fanout_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:GetQueueUrl"
        ]
        Resource = aws_sqs_queue.ingestion_queue.arn
      }
    ]
  })
}
