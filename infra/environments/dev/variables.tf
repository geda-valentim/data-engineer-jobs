variable "region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type        = string
  description = "Nome base do projeto (prefixo de recursos)"
  default     = "data-engineer-jobs"
}

variable "environment" {
  type        = string
  description = "Nome do ambiente"
  default     = "dev"
}

