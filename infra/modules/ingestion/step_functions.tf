#####################################
# State Machine - Bright Data Snapshot Ingestion
#####################################

resource "aws_sfn_state_machine" "bright_data_snapshot_ingestion" {
  name     = "${var.project_name}-bright-data-snapshot"
  role_arn = aws_iam_role.bright_data_sfn_role.arn

  definition = jsonencode({
    Comment        = "Ingestão de snapshots Bright Data (LinkedIn jobs) para Bronze S3 + Glue Bronze->Silver",
    StartAt        = "TriggerBrightData",
    TimeoutSeconds = 1800,
    States = {
      TriggerBrightData = {
        Type           = "Task",
        TimeoutSeconds = 900,
        Resource       = "arn:aws:states:::lambda:invoke",
        OutputPath     = "$.Payload",
        Parameters = {
          "FunctionName" = aws_lambda_function.bright_data["trigger"].arn,
          # Passa o estado inteiro como event para a Lambda
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
        # Em vez de terminar aqui, agora chamamos o Glue
        Next = "BronzeToSilver"
      },

      BronzeToSilver = {
        Type           = "Task",
        Resource       = "arn:aws:states:::glue:startJobRun.sync",
        TimeoutSeconds = 1200,
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
      }
    }
  })
}
