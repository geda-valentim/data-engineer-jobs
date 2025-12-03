locals {
  ssm_prefix = "/${var.project_name}/${var.environment}"
}

locals {
  ingestion_sources_seed = jsondecode(
    file("${path.root}/../../../ingestion_sources.dev.json")
  )
}
