#####################################
# State Machine - Backfill Orchestrator (Distributed Map)
#####################################

resource "aws_sfn_state_machine" "backfill_orchestrator" {
  name     = "${var.project_name}-backfill-orchestrator"
  role_arn = aws_iam_role.backfill_orchestrator_role.arn

  definition = jsonencode({
    Comment = "Orquestra backfill com Distributed Map - controla concorrência de execuções"
    StartAt = "ProcessBackfillItems"
    States = {
      ProcessBackfillItems = {
        Type = "Map"

        # Controle de concorrência - máximo de execuções paralelas
        MaxConcurrency = 10

        # Lê items do manifest no S3
        ItemReader = {
          Resource = "arn:aws:states:::s3:getObject"
          ReaderConfig = {
            InputType = "JSON"
          }
          Parameters = {
            "Bucket.$" = "$.manifest_bucket"
            "Key.$"    = "$.manifest_key"
          }
        }

        # Seleciona o array "items" do JSON
        ItemsPath = "$.items"

        # Cada item é processado pela Step Function existente
        ItemProcessor = {
          ProcessorConfig = {
            Mode          = "DISTRIBUTED"
            ExecutionType = "STANDARD"
          }
          StartAt = "StartIngestion"
          States = {
            StartIngestion = {
              Type     = "Task"
              Resource = "arn:aws:states:::states:startExecution.sync:2"
              Parameters = {
                StateMachineArn = aws_sfn_state_machine.bright_data_snapshot_ingestion.arn
                # Passa o item atual como input para a Step Function filha
                "Input.$" = "$"
              }
              End = true
              # Retry em caso de throttling
              Retry = [
                {
                  ErrorEquals     = ["States.TaskFailed", "StepFunctions.ExecutionLimitExceeded"]
                  IntervalSeconds = 60
                  MaxAttempts     = 3
                  BackoffRate     = 2
                }
              ]
              # Catch para não falhar todo o Map se uma execução falhar
              Catch = [
                {
                  ErrorEquals = ["States.ALL"]
                  ResultPath  = "$.error"
                  Next        = "MarkAsFailed"
                }
              ]
            }
            MarkAsFailed = {
              Type = "Pass"
              Result = {
                status = "FAILED"
              }
              ResultPath = "$.execution_status"
              End        = true
            }
          }
        }

        # Configuração do resultado
        ResultPath = "$.map_results"
        End        = true
      }
    }
  })

  tags = {
    Name    = "${var.project_name}-backfill-orchestrator"
    Purpose = "Orchestrate backfill with controlled concurrency"
  }
}

#####################################
# IAM Role - Backfill Orchestrator
#####################################

resource "aws_iam_role" "backfill_orchestrator_role" {
  name = "${var.project_name}-backfill-orchestrator-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "states.amazonaws.com"
      }
    }]
  })
}

# Permissão para ler do S3
resource "aws_iam_role_policy" "backfill_orchestrator_s3" {
  name = "${var.project_name}-backfill-orchestrator-s3"
  role = aws_iam_role.backfill_orchestrator_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.data_lake_bucket_arn,
          "${var.data_lake_bucket_arn}/*"
        ]
      }
    ]
  })
}

# Permissão para iniciar e monitorar Step Functions filhas
resource "aws_iam_role_policy" "backfill_orchestrator_sfn" {
  name = "${var.project_name}-backfill-orchestrator-sfn"
  role = aws_iam_role.backfill_orchestrator_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution",
          "states:DescribeExecution",
          "states:StopExecution"
        ]
        Resource = aws_sfn_state_machine.bright_data_snapshot_ingestion.arn
      },
      {
        Effect = "Allow"
        Action = [
          "states:DescribeExecution",
          "states:StopExecution"
        ]
        Resource = "arn:aws:states:*:*:execution:${aws_sfn_state_machine.bright_data_snapshot_ingestion.name}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "events:PutTargets",
          "events:PutRule",
          "events:DescribeRule"
        ]
        Resource = "arn:aws:events:*:*:rule/StepFunctionsGetEventsForStepFunctionsExecutionRule"
      }
    ]
  })
}

# Permissão para logs
resource "aws_iam_role_policy_attachment" "backfill_orchestrator_logs" {
  role       = aws_iam_role.backfill_orchestrator_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}
