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
    sid = "AllowSendToIngestionQueue"
    actions = [
      "sqs:SendMessage"
    ]
    resources = [
      aws_sqs_queue.ingestion_queue.arn
    ]
  }
}

resource "aws_iam_policy" "dispatcher_policy" {
  name        = "${var.project_name}-dispatcher-policy"
  description = "Permite dispatcher ler DynamoDB e enviar mensagens para SQS"

  policy = data.aws_iam_policy_document.dispatcher_policy_doc.json
}

resource "aws_iam_role_policy_attachment" "dispatcher_policy_attach" {
  role       = split("/", var.lambda_exec_role_arn)[1]
  policy_arn = aws_iam_policy.dispatcher_policy.arn
}
