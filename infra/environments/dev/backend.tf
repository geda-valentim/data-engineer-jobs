terraform {
  backend "s3" {
    bucket       = "data-engineer-jobs-terraform-state" # Use o nome exato do bucket que você criou
    key          = "dev/terraform.tfstate"              # O caminho/nome do arquivo dentro do bucket
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}