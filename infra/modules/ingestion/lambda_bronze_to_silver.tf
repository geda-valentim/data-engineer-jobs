#####################################
# Lambda - Bronze to Silver ETL
#####################################
# Substitui Glue Job para reduzir custos (~96% economia)
# Usa pandas/awswrangler ao invés de Spark

# Zip do código da Lambda (inclui handler e backfill_handler)
data "archive_file" "bronze_to_silver_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../../src/lambdas/bronze_to_silver"
  output_path = "${path.module}/lambda_packages/bronze_to_silver.zip"
}

# Lambda Function
resource "aws_lambda_function" "bronze_to_silver" {
  count = var.use_lambda_etl ? 1 : 0

  function_name = "${var.project_name}-${var.environment}-ingestion-bronze-to-silver"
  description   = "Transforms job listings JSON from Bronze to Parquet in Silver layer"
  role          = aws_iam_role.bronze_to_silver_lambda_role[0].arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  timeout       = 300  # 5 minutos (jobs tipicamente levam 87s)
  memory_size   = 1024 # 1GB para pandas

  filename         = data.archive_file.bronze_to_silver_zip.output_path
  source_code_hash = data.archive_file.bronze_to_silver_zip.output_base64sha256

  layers = compact([
    var.aws_sdk_pandas_layer_arn,
    var.aws_lambda_layer_version_python_dependencies,
  ])

  environment {
    variables = {
      BRONZE_BUCKET = var.bronze_bucket_name
      SILVER_BUCKET = var.silver_bucket_name
      SOURCE_SYSTEM = "linkedin"
    }
  }

  tags = {
    Name    = "${var.project_name}-bronze-to-silver-lambda"
    Purpose = "ETL-Bronze-to-Silver"
  }
}

# Lambda Function - Backfill (processa múltiplas partições)
resource "aws_lambda_function" "bronze_to_silver_backfill" {
  count = var.use_lambda_etl ? 1 : 0

  function_name = "${var.project_name}-${var.environment}-ingestion-bronze-to-silver-backfill"
  description   = "Backfills multiple Bronze partitions to Silver in parallel batches"
  role          = aws_iam_role.bronze_to_silver_lambda_role[0].arn
  handler       = "backfill_handler.handler"
  runtime       = "python3.12"
  timeout       = 900  # 15 minutos (processa múltiplas partições)
  memory_size   = 2048 # 2GB para processamento paralelo

  filename         = data.archive_file.bronze_to_silver_zip.output_path
  source_code_hash = data.archive_file.bronze_to_silver_zip.output_base64sha256

  layers = compact([
    var.aws_sdk_pandas_layer_arn,
    var.aws_lambda_layer_version_python_dependencies,
  ])

  environment {
    variables = {
      BRONZE_BUCKET = var.bronze_bucket_name
      SILVER_BUCKET = var.silver_bucket_name
      SOURCE_SYSTEM = "linkedin"
    }
  }

  tags = {
    Name    = "${var.project_name}-bronze-to-silver-backfill"
    Purpose = "ETL-Bronze-to-Silver-Backfill"
  }
}

#####################################
# IAM Role - Bronze to Silver Lambda
#####################################

resource "aws_iam_role" "bronze_to_silver_lambda_role" {
  count = var.use_lambda_etl ? 1 : 0

  name = "${var.project_name}-bronze-to-silver-lambda-role"

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
resource "aws_iam_role_policy_attachment" "bronze_to_silver_lambda_logs" {
  count = var.use_lambda_etl ? 1 : 0

  role       = aws_iam_role.bronze_to_silver_lambda_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Permissão para S3 (Bronze read, Silver read/write)
resource "aws_iam_role_policy" "bronze_to_silver_lambda_s3" {
  count = var.use_lambda_etl ? 1 : 0

  name = "${var.project_name}-bronze-to-silver-lambda-s3"
  role = aws_iam_role.bronze_to_silver_lambda_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.bronze_bucket_name}",
          "arn:aws:s3:::${var.bronze_bucket_name}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.silver_bucket_name}",
          "arn:aws:s3:::${var.silver_bucket_name}/*"
        ]
      }
    ]
  })
}

# Permissão para CloudWatch Metrics
resource "aws_iam_role_policy" "bronze_to_silver_lambda_cloudwatch" {
  count = var.use_lambda_etl ? 1 : 0

  name = "${var.project_name}-bronze-to-silver-lambda-cloudwatch"
  role = aws_iam_role.bronze_to_silver_lambda_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "DataEngineerJobs/ETL"
          }
        }
      }
    ]
  })
}

#####################################
# Output
#####################################

output "bronze_to_silver_lambda_arn" {
  description = "ARN da Lambda Bronze to Silver"
  value       = var.use_lambda_etl ? aws_lambda_function.bronze_to_silver[0].arn : null
}

output "bronze_to_silver_lambda_name" {
  description = "Nome da Lambda Bronze to Silver"
  value       = var.use_lambda_etl ? aws_lambda_function.bronze_to_silver[0].function_name : null
}

output "bronze_to_silver_backfill_lambda_arn" {
  description = "ARN da Lambda Bronze to Silver Backfill"
  value       = var.use_lambda_etl ? aws_lambda_function.bronze_to_silver_backfill[0].arn : null
}

output "bronze_to_silver_backfill_lambda_name" {
  description = "Nome da Lambda Bronze to Silver Backfill"
  value       = var.use_lambda_etl ? aws_lambda_function.bronze_to_silver_backfill[0].function_name : null
}
