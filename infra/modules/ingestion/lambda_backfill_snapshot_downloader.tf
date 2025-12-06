#####################################
# Lambda - Backfill Snapshot Downloader
#####################################

# Zip do código da Lambda
data "archive_file" "backfill_snapshot_downloader_zip" {
  type        = "zip"
  source_file = "${path.module}/../../../src/lambdas/backfill_snapshot_downloader/handler.py"
  output_path = "${path.module}/lambda_packages/backfill_snapshot_downloader.zip"
}

# Lambda Function
resource "aws_lambda_function" "backfill_snapshot_downloader" {
  function_name = "${var.project_name}-backfill-snapshot-downloader"
  role          = aws_iam_role.backfill_snapshot_downloader_role.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  timeout       = 300 # 5 min - pode baixar múltiplos snapshots
  memory_size   = 512 # Precisa de memória para snapshots grandes

  filename         = data.archive_file.backfill_snapshot_downloader_zip.output_path
  source_code_hash = data.archive_file.backfill_snapshot_downloader_zip.output_base64sha256

  layers = [var.aws_lambda_layer_version_python_dependencies]

  environment {
    variables = {
      BRIGHTDATA_API_KEY_PARAM = var.brightdata_api_key_param
      BRONZE_BUCKET_NAME       = var.bronze_bucket_name
      APP_TIMEZONE             = "America/Sao_Paulo"
    }
  }

  tags = {
    Name    = "${var.project_name}-backfill-snapshot-downloader"
    Purpose = "Download pending BrightData snapshots to S3"
  }
}

#####################################
# IAM Role - Backfill Snapshot Downloader
#####################################

resource "aws_iam_role" "backfill_snapshot_downloader_role" {
  name = "${var.project_name}-backfill-snapshot-downloader-role"

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

# Permissão para logs (CloudWatch Logs)
resource "aws_iam_role_policy_attachment" "backfill_snapshot_downloader_logs" {
  role       = aws_iam_role.backfill_snapshot_downloader_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Permissão para S3 (read to check existence, write to save snapshots)
resource "aws_iam_role_policy" "backfill_snapshot_downloader_s3" {
  name = "${var.project_name}-backfill-snapshot-downloader-s3"
  role = aws_iam_role.backfill_snapshot_downloader_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:HeadObject",
          "s3:PutObject"
        ]
        Resource = "arn:aws:s3:::${var.bronze_bucket_name}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = "arn:aws:s3:::${var.bronze_bucket_name}"
      }
    ]
  })
}

# Permissão para SSM (ler API key do BrightData)
resource "aws_iam_role_policy" "backfill_snapshot_downloader_ssm" {
  name = "${var.project_name}-backfill-snapshot-downloader-ssm"
  role = aws_iam_role.backfill_snapshot_downloader_role.id

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

# Permissão para CloudWatch Metrics
resource "aws_iam_role_policy" "backfill_snapshot_downloader_cloudwatch" {
  name = "${var.project_name}-backfill-snapshot-downloader-cloudwatch"
  role = aws_iam_role.backfill_snapshot_downloader_role.id

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
