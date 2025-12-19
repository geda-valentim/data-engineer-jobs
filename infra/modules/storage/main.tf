resource "aws_s3_bucket" "bronze" {
  bucket = var.bronze_bucket_name
}

resource "aws_s3_bucket" "silver" {
  bucket = var.silver_bucket_name
}

resource "aws_s3_bucket" "gold" {
  bucket = var.gold_bucket_name
}

resource "aws_s3_bucket" "glue_temp" {
  bucket = var.glue_temp_bucket_name
}

resource "aws_s3_bucket" "glue_scripts" {
  bucket = var.glue_scripts_bucket_name
}

resource "aws_s3_bucket" "athena_results" {
  bucket = var.athena_results_bucket_name
}

# Lifecycle policy para limpar resultados antigos do Athena
resource "aws_s3_bucket_lifecycle_configuration" "athena_results_lifecycle" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    id     = "delete-old-query-results"
    status = "Enabled"

    # Deleta objetos após 24 horas (1 dia)
    expiration {
      days = 1
    }

    # Aplica a todos os objetos no bucket
    filter {}
  }
}
