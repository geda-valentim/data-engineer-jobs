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