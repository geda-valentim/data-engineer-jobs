##############################
# Tabela DynamoDB - ingestion_sources
##############################

resource "aws_dynamodb_table" "ingestion_sources" {
  name         = "${var.project_name}-ingestion-sources"
  billing_mode = "PAY_PER_REQUEST"

  # PK + SK
  hash_key  = "source_id"
  range_key = "source_type"

  attribute {
    name = "source_id"
    type = "S"
  }

  attribute {
    name = "source_type"
    type = "S"
  }
}

##############################
# Seed inicial (fontes)
##############################

resource "aws_dynamodb_table_item" "ingestion_sources_seed" {
  for_each = { for s in var.ingestion_sources_seed : "${s.source_id}#${s.source_type}" => s }

  table_name = aws_dynamodb_table.ingestion_sources.name
  hash_key   = "source_id"
  range_key  = "source_type"

  item = jsonencode({
    source_id = { S = each.value.source_id }
    source_type = { S = each.value.source_type }

    provider      = { S = each.value.provider }
    dataset_kind  = { S = each.value.dataset_kind }
    domain        = { S = each.value.domain }
    entity        = { S = each.value.entity }

    brightdata_dataset_id = { S = each.value.brightdata_dataset_id }

    brightdata_extra_params = {
      M = {
        # map(string) → M de Dynamo
        # Ex: {"include_errors":"true","type":"discover_new"}
        for k, v in each.value.brightdata_extra_params :
        k => { S = v }
      }
    }

    request_urls = {
      L = [
        for url in each.value.request_urls : { S = url }
      ]
    }


    request_url   = { S = each.value.request_url }
    bronze_prefix = { S = each.value.bronze_prefix }
    file_format   = { S = each.value.file_format }

    enabled       = { BOOL = each.value.enabled }
    schedule_group = { S = each.value.schedule_group }
    owner          = { S = each.value.owner }
  })
}

output "ingestion_sources_table_name" {
  value = aws_dynamodb_table.ingestion_sources.name
}
