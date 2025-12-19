#####################################
# State Machine - Bright Data Snapshot Ingestion
#####################################

# Definição do BronzeToSilver step - Lambda ou Glue
locals {
  # ARN do Lambda ETL (vazio se use_lambda_etl = false)
  lambda_etl_arn = try(aws_lambda_function.bronze_to_silver[0].arn, "")

  # Step definitions como JSON strings para evitar type mismatch
  bronze_to_silver_step_lambda = jsonencode({
    Type           = "Task",
    Resource       = "arn:aws:states:::lambda:invoke",
    TimeoutSeconds = 600,
    OutputPath     = "$.Payload",
    Parameters = {
      "FunctionName" = local.lambda_etl_arn,
      "Payload" = {
        "year.$"  = "$.year",
        "month.$" = "$.month",
        "day.$"   = "$.day",
        "hour.$"  = "$.hour"
      }
    },
    End = true
  })

  bronze_to_silver_step_glue = jsonencode({
    Type           = "Task",
    Resource       = "arn:aws:states:::glue:startJobRun.sync",
    TimeoutSeconds = 1200,
    OutputPath     = "$",
    Parameters = {
      "JobName" = aws_glue_job.bronze_to_silver.name,
      "Arguments" = {
        "--year.$"  = "$.year",
        "--month.$" = "$.month",
        "--day.$"   = "$.day",
        "--hour.$"  = "$.hour"
      }
    },
    End = true
  })

  # Escolhe o step baseado na variável (ambos são strings agora)
  bronze_to_silver_step = var.use_lambda_etl ? local.bronze_to_silver_step_lambda : local.bronze_to_silver_step_glue

  # States base (sem BronzeToSilver)
  base_states = {
    TriggerBrightData = {
      Type           = "Task",
      TimeoutSeconds = 900,
      Resource       = "arn:aws:states:::lambda:invoke",
      OutputPath     = "$.Payload",
      Parameters = {
        "FunctionName" = aws_lambda_function.bright_data["trigger"].arn,
        "Payload.$"    = "$"
      },
      Next = "WaitBeforeCheck"
    },

    WaitBeforeCheck = {
      Type    = "Wait",
      Seconds = 30,
      Next    = "CheckStatus"
    },

    CheckStatus = {
      Type           = "Task",
      TimeoutSeconds = 60,
      Resource       = "arn:aws:states:::lambda:invoke",
      OutputPath     = "$.Payload",
      Parameters = {
        "FunctionName" = aws_lambda_function.bright_data["check_status"].arn,
        "Payload.$"    = "$"
      },
      Next = "IsReady"
    },

    IsReady = {
      Type = "Choice",
      Choices = [
        {
          Variable     = "$.status",
          StringEquals = "READY",
          Next         = "SaveToS3"
        }
      ],
      Default = "WaitBeforeCheck"
    },

    SaveToS3 = {
      Type           = "Task",
      Resource       = "arn:aws:states:::lambda:invoke",
      TimeoutSeconds = 150,
      OutputPath     = "$.Payload",
      Parameters = {
        "FunctionName" = aws_lambda_function.bright_data["save_to_s3"].arn,
        "Payload.$"    = "$"
      },
      Next = "BronzeToSilver"
    }
  }

  # States completo com BronzeToSilver (merge manual via JSON)
  all_states = merge(
    local.base_states,
    { BronzeToSilver = jsondecode(local.bronze_to_silver_step) }
  )
}

resource "aws_sfn_state_machine" "bright_data_snapshot_ingestion" {
  name     = "${var.project_name}-bright-data-snapshot"
  role_arn = aws_iam_role.bright_data_sfn_role.arn

  definition = jsonencode({
    Comment        = "Ingestão de snapshots Bright Data (LinkedIn jobs) para Bronze S3 + ETL Bronze->Silver",
    StartAt        = "TriggerBrightData",
    TimeoutSeconds = 1800,
    States         = local.all_states
  })
}
