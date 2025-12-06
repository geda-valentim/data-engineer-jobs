#####################################
# Lambda - Companies Fetcher
#####################################

# Zip do codigo da Lambda
data "archive_file" "companies_fetcher_zip" {
  type        = "zip"
  source_file = "${path.module}/../../../src/lambdas/companies_fetcher/handler.py"
  output_path = "${path.module}/lambda_packages/companies_fetcher.zip"
}

# Lambda Function
resource "aws_lambda_function" "companies_fetcher" {
  function_name = "${var.project_name}-companies-fetcher"
  role          = aws_iam_role.companies_fetcher_role.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  timeout       = 120 # 2 min - API call + S3 save
  memory_size   = 256

  filename         = data.archive_file.companies_fetcher_zip.output_path
  source_code_hash = data.archive_file.companies_fetcher_zip.output_base64sha256

  layers = [var.aws_lambda_layer_version_python_dependencies]

  # Limita concorrencia para evitar rate limit da Bright Data API
  reserved_concurrent_executions = 5

  environment {
    variables = {
      BRIGHTDATA_API_KEY_PARAM        = var.brightdata_api_key_param
      BRIGHTDATA_COMPANIES_DATASET_ID = "gd_l1vikfnt1wgvvqz95w"
      BRONZE_BUCKET_NAME              = var.bronze_bucket_name
      COMPANIES_STATUS_TABLE          = aws_dynamodb_table.companies_status.name
      REFRESH_DAYS                    = "180"
      APP_TIMEZONE                    = "America/Sao_Paulo"
    }
  }

  tags = {
    Name    = "${var.project_name}-companies-fetcher"
    Purpose = "Fetch company data from Bright Data API"
  }
}

# SQS Event Source Mapping
resource "aws_lambda_event_source_mapping" "companies_fetcher_sqs" {
  event_source_arn = aws_sqs_queue.companies_queue.arn
  function_name    = aws_lambda_function.companies_fetcher.arn

  batch_size = 1 # Processa uma mensagem por vez

  # Permite partial batch failures
  function_response_types = ["ReportBatchItemFailures"]

  # Scaling config
  scaling_config {
    maximum_concurrency = 5 # Mesma concorrencia reservada
  }
}

#####################################
# IAM Role - Companies Fetcher
#####################################

resource "aws_iam_role" "companies_fetcher_role" {
  name = "${var.project_name}-companies-fetcher-role"

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

# Permissao para logs (CloudWatch Logs)
resource "aws_iam_role_policy_attachment" "companies_fetcher_logs" {
  role       = aws_iam_role.companies_fetcher_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Permissao para SQS
resource "aws_iam_role_policy" "companies_fetcher_sqs" {
  name = "${var.project_name}-companies-fetcher-sqs"
  role = aws_iam_role.companies_fetcher_role.id

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
        Resource = aws_sqs_queue.companies_queue.arn
      }
    ]
  })
}

# Permissao para DynamoDB
resource "aws_iam_role_policy" "companies_fetcher_dynamodb" {
  name = "${var.project_name}-companies-fetcher-dynamodb"
  role = aws_iam_role.companies_fetcher_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = aws_dynamodb_table.companies_status.arn
      }
    ]
  })
}

# Permissao para S3 (write to Bronze)
resource "aws_iam_role_policy" "companies_fetcher_s3" {
  name = "${var.project_name}-companies-fetcher-s3"
  role = aws_iam_role.companies_fetcher_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "arn:aws:s3:::${var.bronze_bucket_name}/linkedin_companies/*"
      }
    ]
  })
}

# Permissao para SSM (ler API key do BrightData)
resource "aws_iam_role_policy" "companies_fetcher_ssm" {
  name = "${var.project_name}-companies-fetcher-ssm"
  role = aws_iam_role.companies_fetcher_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter"
        ]
        Resource = "arn:aws:ssm:*:*:parameter${var.brightdata_api_key_param}"
      }
    ]
  })
}

# Permissao para CloudWatch Metrics
resource "aws_iam_role_policy" "companies_fetcher_cloudwatch" {
  name = "${var.project_name}-companies-fetcher-cloudwatch"
  role = aws_iam_role.companies_fetcher_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
        Resource = "*"
      }
    ]
  })
}
