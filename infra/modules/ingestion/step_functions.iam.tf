#####################################
# IAM Role para Step Functions
#####################################

resource "aws_iam_role" "bright_data_sfn_role" {
  name = "${var.project_name}-bright-data-sfn-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "states.amazonaws.com"
      },
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_policy" "bright_data_sfn_policy" {
  name        = "${var.project_name}-bright-data-sfn-policy"
  description = "Permite Step Functions invocar as Lambdas de ingestão, rodar Glue Job e escrever logs"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      # Invocar Lambdas de ingestão
      {
        Effect = "Allow",
        Action = [
          "lambda:InvokeFunction"
        ],
        Resource = compact([
          aws_lambda_function.bright_data["trigger"].arn,
          aws_lambda_function.bright_data["check_status"].arn,
          aws_lambda_function.bright_data["save_to_s3"].arn,
          # Lambda ETL (usa local com try() para evitar erro quando count=0)
          local.lambda_etl_arn
        ])
      },

      # Rodar o Glue Job bronze_to_silver via Step Functions (startJobRun.sync)
      {
        Effect = "Allow",
        Action = [
          "glue:StartJobRun",
          "glue:GetJobRun",
          "glue:GetJobRuns",
          "glue:GetJob"
        ],
        Resource = aws_glue_job.bronze_to_silver.arn
      },

      # Logs da própria Step Functions
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "bright_data_sfn_policy_attach" {
  role       = aws_iam_role.bright_data_sfn_role.name
  policy_arn = aws_iam_policy.bright_data_sfn_policy.arn
}
