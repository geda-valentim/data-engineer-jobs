# Lambda Execution Role for AI Enrichment

resource "aws_iam_role" "ai_enrichment_lambda" {
  name = "${var.project_name}-ai-enrichment-lambda-${var.environment}"

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

  tags = local.common_tags
}

# CloudWatch Logs - Basic Lambda Execution
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.ai_enrichment_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# S3 Access - Read Silver, Write Silver-AI
resource "aws_iam_role_policy" "s3_access" {
  name = "s3-access"
  role = aws_iam_role.ai_enrichment_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadSilver"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.silver_bucket_name}",
          "arn:aws:s3:::${var.silver_bucket_name}/${var.silver_prefix}*"
        ]
      },
      {
        Sid    = "WriteSilverAI"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.silver_bucket_name}",
          "arn:aws:s3:::${var.silver_bucket_name}/${var.silver_ai_prefix}*"
        ]
      }
    ]
  })
}

# Bedrock Access - All Foundation Models
resource "aws_iam_role_policy" "bedrock_access" {
  name = "bedrock-access"
  role = aws_iam_role.ai_enrichment_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "InvokeModels"
      Effect = "Allow"
      Action = [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ]
      Resource = [
        "arn:aws:bedrock:${var.aws_region}::foundation-model/*"
      ]
    }]
  })
}

# CloudWatch Metrics - Custom Metrics
resource "aws_iam_role_policy" "cloudwatch_metrics" {
  name = "cloudwatch-metrics"
  role = aws_iam_role.ai_enrichment_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "PutMetrics"
      Effect = "Allow"
      Action = [
        "cloudwatch:PutMetricData"
      ]
      Resource = "*"
      Condition = {
        StringEquals = {
          "cloudwatch:namespace" = "DataEngineerJobs/AIEnrichment"
        }
      }
    }]
  })
}
