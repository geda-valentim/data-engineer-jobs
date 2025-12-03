########################################
# Glue Database
########################################

resource "aws_glue_catalog_database" "data_engineer_jobs" {
  name = "${var.project_name}_db"
}

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
  }

  storage_descriptor {
    location      = "s3://${var.silver_bucket_name}/linkedin/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
    compressed    = true
    number_of_buckets = -1

    ser_de_info {
      name                  = "parquet-serde"
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"

      parameters = {
        "serialization.format" = "1"
      }
    }

    # 🔹 Colunas "normais" (sem as partições)
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

    columns {
      name = "job_location"
      type = "string"
    }

    columns {
      name = "country_code"
      type = "string"
    }

    columns {
      name = "job_posted_datetime"
      type = "timestamp"
    }

    columns {
      name = "job_posted_date_only"
      type = "date"
    }

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
  }

  # 🔹 Partições year / month / day / hour (iguais ao que o Glue Job usa)
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

########################################
# Athena Workgroup
########################################

resource "aws_athena_workgroup" "this" {
  name = "${var.project_name}-wg"

  configuration {
    enforce_workgroup_configuration = true

    result_configuration {
      output_location = "s3://${var.athena_results_bucket_name}/results/"
    }
  }

  description = "Workgroup do Athena para o projeto ${var.project_name}"
}
