data "aws_iam_policy_document" "dispatcher_policy_doc" {
  statement {
    sid = "AllowScanIngestionSources"
    actions = [
      "dynamodb:Scan",
      "dynamodb:GetItem",
      "dynamodb:DescribeTable",
    ]
    resources = [
      aws_dynamodb_table.ingestion_sources.arn
    ]
  }

  statement {
    sid = "AllowStartStepFunctions"
    actions = [
      "states:StartExecution"
    ]
    resources = [
      aws_sfn_state_machine.bright_data_snapshot_ingestion.arn
    ]
  }
}

resource "aws_iam_policy" "dispatcher_policy" {
  name        = "${var.project_name}-dispatcher-policy"
  description = "Permite dispatcher ler DynamoDB e startar Step Functions"

  policy = data.aws_iam_policy_document.dispatcher_policy_doc.json
}

resource "aws_iam_role_policy_attachment" "dispatcher_policy_attach" {
  role       = split("/", var.lambda_exec_role_arn)[1]
  policy_arn = aws_iam_policy.dispatcher_policy.arn
}
