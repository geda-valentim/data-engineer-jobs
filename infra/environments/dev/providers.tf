provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "Data Engineer Jobs"
      Environment = "Dev"
      ManagedBy   = "Terraform"
    }
  }
}