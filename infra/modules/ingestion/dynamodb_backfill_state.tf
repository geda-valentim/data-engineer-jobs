#####################################
# DynamoDB Table - Backfill Processing State
#####################################
# Tracks which Silver layer partitions have been processed by the
# companies backfill scanner to avoid duplicate processing.
#
# Schema:
# - partition_key (PK): "year=2025/month=12/day=08/hour=10"
# - processed_at: ISO timestamp when partition was processed
# - companies_found: Count of unique companies in partition
# - companies_queued: Count of companies sent to SQS
# - ttl: Unix timestamp for automatic cleanup (90 days)

resource "aws_dynamodb_table" "backfill_processing_state" {
  name         = "${var.project_name}-backfill-processing-state"
  billing_mode = "PAY_PER_REQUEST" # On-demand (no capacity planning needed)
  hash_key     = "partition_key"

  attribute {
    name = "partition_key"
    type = "S" # String: "year=YYYY/month=MM/day=DD/hour=HH"
  }

  # TTL enabled for automatic cleanup of old entries
  ttl {
    enabled        = true
    attribute_name = "ttl"
  }

  tags = {
    Name    = "${var.project_name}-backfill-processing-state"
    Purpose = "Track processed Silver partitions for companies backfill"
  }
}
