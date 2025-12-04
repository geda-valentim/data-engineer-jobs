#############################################
# IAM Role + Policy para Glue Job
#############################################

resource "aws_iam_role" "glue_bronze_to_silver_role" {
  name = "${var.project_name}-glue-bronze-to-silver-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "glue_bronze_to_silver_policy" {
  name = "${var.project_name}-glue-bronze-to-silver-policy"
  role = aws_iam_role.glue_bronze_to_silver_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # 🔹 LER do Bronze
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

      # 🔹 ESCREVER no Silver (inclui DeleteObject para overwrite de partições)
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:AbortMultipartUpload",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.silver_bucket_name}",
          "arn:aws:s3:::${var.silver_bucket_name}/*"
        ]
      },

      # 🔹 TEMP do Glue
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.glue_temp_bucket_name}",
          "arn:aws:s3:::${var.glue_temp_bucket_name}/*"
        ]
      },

      # 🔹 **NOVO**: Bucket de SCRIPTS do Glue
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.glue_scripts_bucket_name}",
          "arn:aws:s3:::${var.glue_scripts_bucket_name}/*"
        ]
      },

      # 🔹 Ler catálogo de skills no Silver (reference/skills/*)
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.silver_bucket_name}",
          "arn:aws:s3:::${var.silver_bucket_name}/reference/skills/*"
        ]
      },

      # 🔹 Logs do Glue
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}
