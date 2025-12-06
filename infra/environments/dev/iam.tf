data "aws_caller_identity" "current" {}

# Lambada Exec Permissions
resource "aws_iam_role" "data_engineer_jobs_lambda_exec_role" {
  name = "data-engineer-jobs-lambda-exec-role"

  # JSON da Trust Policy (permite que o Lambda Service assuma este Role)
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_policy" "lambda_trigger_policy" {
  name        = "lambda-trigger-policy"
  description = "Lambda Trigger Policy"
  policy      = file("../../policies/lambda-trigger-policy.json")
}

resource "aws_iam_role_policy_attachment" "lambda_role_attach" {
  role       = aws_iam_role.data_engineer_jobs_lambda_exec_role.name
  policy_arn = aws_iam_policy.lambda_trigger_policy.arn
}

#Lambda SSM Bright Data
resource "aws_iam_policy" "lambda_ssm_brightdata" {
  name        = "lambda-ssm-brightdata"
  description = "Permite Lambda ler api key do BrightData no SSM"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "ssm:GetParameter"
        ],
        Resource = "arn:aws:ssm:us-east-1:${data.aws_caller_identity.current.account_id}:parameter${local.ssm_prefix}/brightdata/*"
        # => arn:aws:ssm:us-east-1:ACCOUNT:parameter/data-engineer-jobs/dev/brightdata/*
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_ssm_brightdata_attach" {
  role       = aws_iam_role.data_engineer_jobs_lambda_exec_role.name
  policy_arn = aws_iam_policy.lambda_ssm_brightdata.arn
}

#Permission Lambda  S3

resource "aws_iam_policy" "lambda_s3_bronze" {
  name        = "lambda-s3-bronze"
  description = "Permite Lambda escrever no bucket bronze"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl"
        ],
        Resource = [
          "arn:aws:s3:::${module.storage.bronze_bucket_name}/*"
        ]
      },
      {
        Effect = "Allow",
        Action = [
          "s3:ListBucket"
        ],
        Resource = [
          "arn:aws:s3:::${module.storage.bronze_bucket_name}"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_s3_bronze_attach" {
  role       = aws_iam_role.data_engineer_jobs_lambda_exec_role.name
  policy_arn = aws_iam_policy.lambda_s3_bronze.arn
}

# Permission Lambda -> SQS Companies Queue
resource "aws_iam_policy" "lambda_sqs_companies" {
  name        = "lambda-sqs-companies"
  description = "Permite Lambda enviar mensagens para fila de companies"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "sqs:SendMessage"
        ],
        Resource = [
          module.ingestion.companies_queue_arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_sqs_companies_attach" {
  role       = aws_iam_role.data_engineer_jobs_lambda_exec_role.name
  policy_arn = aws_iam_policy.lambda_sqs_companies.arn
}
