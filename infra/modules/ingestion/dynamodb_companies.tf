##############################
# Tabela DynamoDB - companies_status
##############################

resource "aws_dynamodb_table" "companies_status" {
  name         = "${var.project_name}-companies-status"
  billing_mode = "PAY_PER_REQUEST"

  # PK simples - company_id
  hash_key = "company_id"

  attribute {
    name = "company_id"
    type = "S"
  }

  tags = {
    Name    = "${var.project_name}-companies-status"
    Purpose = "Track companies fetch status to avoid duplicate API calls"
  }
}
