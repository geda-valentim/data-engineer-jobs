resource "aws_s3_object" "skills_catalog" {
  bucket = var.silver_bucket_name

  # Onde vai ficar no S3
  key = "reference/skills/skills_catalog.json"

  # Caminho local do arquivo (partindo do root-module: infra/environments/dev)
  # JSON é gerado via `make skills-catalog` a partir do YAML
  source = "${path.root}/../../../src/skills_detection/config/skills_catalog.json"

  # Se o arquivo mudar, o md5 muda e o Terraform faz upload de novo
  etag = filemd5("${path.root}/../../../src/skills_detection/config/skills_catalog.json")

  content_type = "application/json"
}
