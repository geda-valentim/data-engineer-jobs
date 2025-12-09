#####################################
# Lambda - Companies Backfill Scanner
#####################################
# Scans Silver layer Parquet files for unique companies and queues
# missing companies to SQS FIFO for fetching.
#
# Execution:
# - Scheduled daily via EventBridge (3 AM UTC)
# - Can be invoked manually with specific partition
#
# Architecture:
# - Reads from Silver layer (Parquet)
# - Filters against DynamoDB cache (companies-status)
# - Sends to SQS FIFO (companies-to-fetch)
# - Tracks state in DynamoDB (backfill-processing-state)

# Zip do codigo da Lambda
data "archive_file" "companies_backfill_scanner_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../../src/lambdas/companies_backfill_scanner"
  output_path = "${path.module}/lambda_packages/companies_backfill_scanner.zip"
}

# Lambda Function
resource "aws_lambda_function" "companies_backfill_scanner" {
  function_name = "${var.project_name}-companies-backfill-scanner"
  role          = aws_iam_role.companies_backfill_scanner_role.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  timeout       = 300 # 5 minutes
  memory_size   = 512

  filename         = data.archive_file.companies_backfill_scanner_zip.output_path
  source_code_hash = data.archive_file.companies_backfill_scanner_zip.output_base64sha256

  # Python dependencies layers:
  # - AWS SDK for pandas (includes pandas, pyarrow, numpy, boto3)
  # - Custom layer with project dependencies
  layers = [
    "arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python312:13",
    var.aws_lambda_layer_version_python_dependencies
  ]

  environment {
    variables = {
      SILVER_BUCKET_NAME       = var.silver_bucket_name
      COMPANIES_STATUS_TABLE   = aws_dynamodb_table.companies_status.name
      BACKFILL_STATE_TABLE     = aws_dynamodb_table.backfill_processing_state.name
      COMPANIES_QUEUE_URL      = aws_sqs_queue.companies_queue.url
      LOOKBACK_DAYS            = "30"  # Last 30 days by default
      MAX_PARTITIONS_PER_RUN   = "10"  # Process 10 partitions per run
    }
  }

  tags = {
    Name    = "${var.project_name}-companies-backfill-scanner"
    Purpose = "Scan Silver layer for missing companies and queue for fetching"
  }
}

#####################################
# IAM Role - Companies Backfill Scanner
#####################################

resource "aws_iam_role" "companies_backfill_scanner_role" {
  name = "${var.project_name}-companies-backfill-scanner-role"

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
resource "aws_iam_role_policy_attachment" "companies_backfill_scanner_logs" {
  role       = aws_iam_role.companies_backfill_scanner_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Permissao para S3 (read Silver layer)
resource "aws_iam_role_policy" "companies_backfill_scanner_s3" {
  name = "${var.project_name}-companies-backfill-scanner-s3"
  role = aws_iam_role.companies_backfill_scanner_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = "arn:aws:s3:::${var.silver_bucket_name}"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "arn:aws:s3:::${var.silver_bucket_name}/linkedin/*"
      }
    ]
  })
}

# Permissao para DynamoDB (read companies-status, read/write backfill-state)
resource "aws_iam_role_policy" "companies_backfill_scanner_dynamodb" {
  name = "${var.project_name}-companies-backfill-scanner-dynamodb"
  role = aws_iam_role.companies_backfill_scanner_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:BatchGetItem"
        ]
        Resource = aws_dynamodb_table.companies_status.arn
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:BatchGetItem"
        ]
        Resource = aws_dynamodb_table.backfill_processing_state.arn
      }
    ]
  })
}

# Permissao para SQS (send messages to FIFO queue)
resource "aws_iam_role_policy" "companies_backfill_scanner_sqs" {
  name = "${var.project_name}-companies-backfill-scanner-sqs"
  role = aws_iam_role.companies_backfill_scanner_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:SendMessageBatch",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl"
        ]
        Resource = aws_sqs_queue.companies_queue.arn
      }
    ]
  })
}

# Permissao para CloudWatch Metrics (custom metrics)
resource "aws_iam_role_policy" "companies_backfill_scanner_cloudwatch" {
  name = "${var.project_name}-companies-backfill-scanner-cloudwatch"
  role = aws_iam_role.companies_backfill_scanner_role.id

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
