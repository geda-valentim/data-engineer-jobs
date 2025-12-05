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
  timeout       = 60  # 1 min - só gera JSON e inicia Step Function
  memory_size   = 256

  filename         = data.archive_file.backfill_fanout_zip.output_path
  source_code_hash = data.archive_file.backfill_fanout_zip.output_base64sha256

  environment {
    variables = {
      BACKFILL_BUCKET              = var.data_lake_bucket_name
      ORCHESTRATOR_STATE_MACHINE_ARN = aws_sfn_state_machine.backfill_orchestrator.arn
    }
  }

  tags = {
    Name    = "${var.project_name}-backfill-fanout"
    Purpose = "Generate payloads and start backfill orchestrator"
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

# Permissão para S3 (salvar manifest)
resource "aws_iam_role_policy" "backfill_fanout_s3" {
  name = "${var.project_name}-backfill-fanout-s3"
  role = aws_iam_role.backfill_fanout_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "${var.data_lake_bucket_arn}/backfill-manifests/*"
      }
    ]
  })
}

# Permissão para Step Functions (iniciar orquestrador)
resource "aws_iam_role_policy" "backfill_fanout_sfn" {
  name = "${var.project_name}-backfill-fanout-sfn"
  role = aws_iam_role.backfill_fanout_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution"
        ]
        Resource = aws_sfn_state_machine.backfill_orchestrator.arn
      }
    ]
  })
}
