variable "bronze_bucket_name" {
    description = "Bucket bronze"
    type = string
    default = "bronze"
}

variable "silver_bucket_name" {
    description = "Bucket silver"
    type = string
    default = "silver"
}

variable "gold_bucket_name" {
    description = "Bucket gold"
    type = string
    default = "gold"
}

variable "glue_temp_bucket_name" {
  type = string
  default = "glue-temp"
}

variable "glue_scripts_bucket_name" {
    type = string
    default = "glue-scripts"
}

variable "athena_results_bucket_name" {
  description = "Nome do bucket onde o Athena vai salvar os resultados"
  type        = string
}
