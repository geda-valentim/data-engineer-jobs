########################################
# Glue Table - linkedin_silver
########################################

resource "aws_glue_catalog_table" "linkedin_silver" {
  name          = "linkedin_silver"
  database_name = aws_glue_catalog_database.data_engineer_jobs.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    classification        = "parquet"
    "parquet.compression" = "SNAPPY"
    EXTERNAL              = "TRUE"

    # Partition Projection desabilitado - usar MSCK REPAIR TABLE para registrar partições
    # Para volumes pequenos, scan direto é mais rápido que projeção
    "projection.enabled" = "false"
  }

  storage_descriptor {
    location          = "s3://${var.silver_bucket_name}/linkedin/"
    input_format      = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format     = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
    compressed        = true
    number_of_buckets = -1

    ser_de_info {
      name                  = "parquet-serde"
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    # Identificação
    columns {
      name = "job_posting_id"
      type = "string"
    }
    columns {
      name = "source_system"
      type = "string"
    }
    columns {
      name = "url"
      type = "string"
    }
    columns {
      name = "scraped_at"
      type = "timestamp"
    }

    # Empresa
    columns {
      name = "company_name"
      type = "string"
    }
    columns {
      name = "company_id"
      type = "string"
    }
    columns {
      name = "company_url"
      type = "string"
    }

    # Vaga
    columns {
      name = "job_title"
      type = "string"
    }
    columns {
      name = "job_seniority_level"
      type = "string"
    }
    columns {
      name = "job_function"
      type = "string"
    }
    columns {
      name = "job_employment_type"
      type = "string"
    }
    columns {
      name = "job_industries"
      type = "string"
    }

    # Localização
    columns {
      name = "job_location"
      type = "string"
    }
    columns {
      name = "country_code"
      type = "string"
    }

    # Datas
    columns {
      name = "job_posted_datetime"
      type = "timestamp"
    }
    columns {
      name = "job_posted_date_only"
      type = "date"
    }

    # Aplicação
    columns {
      name = "application_availability"
      type = "boolean"
    }
    columns {
      name = "apply_link"
      type = "string"
    }
    columns {
      name = "job_num_applicants"
      type = "int"
    }

    # Salário
    columns {
      name = "salary_min"
      type = "double"
    }
    columns {
      name = "salary_max"
      type = "double"
    }
    columns {
      name = "salary_currency"
      type = "string"
    }
    columns {
      name = "salary_period"
      type = "string"
    }

    # Recrutador
    columns {
      name = "job_poster_name"
      type = "string"
    }
    columns {
      name = "job_poster_title"
      type = "string"
    }
    columns {
      name = "job_poster_url"
      type = "string"
    }

    # Descrição
    columns {
      name = "job_summary"
      type = "string"
    }
    columns {
      name = "job_description_html"
      type = "string"
    }
    columns {
      name = "job_description_text"
      type = "string"
    }

    # Skills (detectadas automaticamente)
    columns {
      name = "skills_canonical"
      type = "array<string>"
    }
    columns {
      name = "skills_families"
      type = "array<string>"
    }
    columns {
      name = "skills_raw_hits"
      type = "array<string>"
    }
    columns {
      name = "skills_catalog_version"
      type = "string"
    }
  }

  # Partições
  partition_keys {
    name = "year"
    type = "int"
  }
  partition_keys {
    name = "month"
    type = "int"
  }
  partition_keys {
    name = "day"
    type = "int"
  }
  partition_keys {
    name = "hour"
    type = "int"
  }
}
