# IAM Roles and Policies for Bronze to Silver Lambdas

# =============================================================================
# Lambda Execution Role
# =============================================================================

resource "aws_iam_role" "lambda_execution" {
  name = "${local.name_prefix}-b2s-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

# =============================================================================
# Managed Policy - Basic Lambda Execution (CloudWatch Logs)
# =============================================================================

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# =============================================================================
# Custom Policy - S3 Read (Bronze Bucket)
# =============================================================================

resource "aws_iam_role_policy" "s3_bronze_read" {
  name = "S3BronzeRead"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ListBronzeBucket"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
        ]
        Resource = "arn:aws:s3:::${var.bronze_bucket_name}"
        Condition = {
          StringLike = {
            "s3:prefix" = ["${var.bronze_companies_prefix}*"]
          }
        }
      },
      {
        Sid    = "ReadBronzeObjects"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:HeadObject",
        ]
        Resource = "arn:aws:s3:::${var.bronze_bucket_name}/${var.bronze_companies_prefix}*"
      }
    ]
  })
}

# =============================================================================
# Custom Policy - S3 Write (Silver Bucket)
# =============================================================================

resource "aws_iam_role_policy" "s3_silver_write" {
  name = "S3SilverWrite"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ListSilverBucket"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
        ]
        Resource = "arn:aws:s3:::${var.silver_bucket_name}"
        Condition = {
          StringLike = {
            "s3:prefix" = ["${var.silver_companies_prefix}*"]
          }
        }
      },
      {
        Sid    = "WriteSilverObjects"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:HeadObject",
          "s3:DeleteObject",
        ]
        Resource = "arn:aws:s3:::${var.silver_bucket_name}/${var.silver_companies_prefix}*"
      }
    ]
  })
}

# =============================================================================
# Custom Policy - SQS Access
# =============================================================================

resource "aws_iam_role_policy" "sqs_access" {
  name = "SQSAccess"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SendToQueue"
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:SendMessageBatch",
          "sqs:GetQueueAttributes",
        ]
        Resource = aws_sqs_queue.companies_queue.arn
      },
      {
        Sid    = "ReceiveFromQueue"
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility",
        ]
        Resource = aws_sqs_queue.companies_queue.arn
      }
    ]
  })
}

# =============================================================================
# Custom Policy - CloudWatch Metrics
# =============================================================================

resource "aws_iam_role_policy" "cloudwatch_metrics" {
  name = "CloudWatchMetrics"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "PutMetrics"
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "${var.project_name}/BronzeToSilver"
          }
        }
      }
    ]
  })
}
