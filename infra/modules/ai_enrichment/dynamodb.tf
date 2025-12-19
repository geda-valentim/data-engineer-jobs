# DynamoDB Tables for AI Enrichment Pipeline
# - Semaphore: Concurrency control (max N simultaneous executions)
# - Status: Job processing status tracking per pass

# ═══════════════════════════════════════════════════════════════════════════════
# Semaphore Table - Concurrency Control
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_dynamodb_table" "semaphore" {
  name         = "${var.project_name}-${var.environment}-ai-enrichment-semaphore"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockName"

  attribute {
    name = "LockName"
    type = "S"
  }

  # Enable TTL for automatic cleanup of stale locks (optional)
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-ai-enrichment-semaphore"
  })
}

# ═══════════════════════════════════════════════════════════════════════════════
# Status Table - Job Processing Tracking
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_dynamodb_table" "status" {
  name         = "${var.project_name}-${var.environment}-ai-enrichment-status"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_posting_id"

  attribute {
    name = "job_posting_id"
    type = "S"
  }

  attribute {
    name = "overallStatus"
    type = "S"
  }

  attribute {
    name = "updatedAt"
    type = "S"
  }

  # GSI for querying by status
  global_secondary_index {
    name            = "status-index"
    hash_key        = "overallStatus"
    range_key       = "updatedAt"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-ai-enrichment-status"
  })
}

# ═══════════════════════════════════════════════════════════════════════════════
# Initialize Semaphore Record
# ═══════════════════════════════════════════════════════════════════════════════

# Note: This creates the initial semaphore record with count=0
# The Step Function will manage incrementing/decrementing
# ═══════════════════════════════════════════════════════════════════════════════
# ETL Processed Table - Tracks jobs moved from Bronze to Silver
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_dynamodb_table" "etl_processed" {
  name         = "${var.project_name}-${var.environment}-ai-etl-processed"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_posting_id"

  attribute {
    name = "job_posting_id"
    type = "S"
  }

  # TTL para limpeza automática após 90 dias (opcional)
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = false # Não precisa de PITR para tabela de controle
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-${var.environment}-ai-etl-processed"
  })
}

# ═══════════════════════════════════════════════════════════════════════════════
# Initialize Semaphore Record
# ═══════════════════════════════════════════════════════════════════════════════

resource "aws_dynamodb_table_item" "semaphore_init" {
  table_name = aws_dynamodb_table.semaphore.name
  hash_key   = aws_dynamodb_table.semaphore.hash_key

  item = jsonencode({
    LockName = {
      S = "ProcessingLock"
    }
    currentlockcount = {
      N = "0"
    }
    maxlockcount = {
      N = tostring(var.max_concurrent_executions)
    }
  })

  lifecycle {
    ignore_changes = [item]
  }
}
