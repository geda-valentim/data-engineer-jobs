# Sprint 0: Infrastructure Setup

## Goal

Set up the foundational infrastructure for Gold Layer: Redshift Serverless, Lambda dbt runner, VPC endpoints.

## Prerequisites

- [ ] AWS account with appropriate permissions
- [ ] VPC with at least 3 private subnets (Redshift Serverless requirement)
- [ ] Terraform >= 1.5

---

## Tasks

### 0.1 dbt Project Structure

```
src/dbt_gold/
├── dbt_project.yml
├── profiles.yml              # Uses IAM auth (no credentials)
├── packages.yml              # Empty (no external packages)
├── macros/
│   └── surrogate_key.sql     # Custom macro (avoid dbt_utils)
├── models/
│   ├── staging/              # Spectrum external tables
│   ├── dimensions/
│   ├── facts/
│   ├── bridges/
│   └── aggregations/
└── seeds/
    └── dim_date.csv          # Pre-populated 2020-2030
```

**dbt_project.yml:**
```yaml
name: 'gold_layer'
version: '1.0.0'
profile: 'redshift_gold'

model-paths: ["models"]
seed-paths: ["seeds"]
macro-paths: ["macros"]

models:
  gold_layer:
    staging:
      +materialized: ephemeral
    dimensions:
      +materialized: table
      +schema: gold
    facts:
      +materialized: incremental
      +schema: gold
      +unique_key: job_posting_id
      +incremental_strategy: delete+insert
    bridges:
      +materialized: incremental
      +schema: gold
    aggregations:
      +materialized: table
      +schema: gold
```

**profiles.yml (IAM auth - no credentials needed):**
```yaml
redshift_gold:
  target: prod
  outputs:
    prod:
      type: redshift
      method: iam
      cluster_id: gold-workgroup
      host: "{{ env_var('REDSHIFT_HOST') }}"
      port: 5439
      user: "{{ env_var('REDSHIFT_USER', 'admin') }}"
      dbname: analytics
      schema: gold
      threads: 4
      connect_timeout: 300
```

### 0.2 Custom Macros (Avoid External Packages)

**macros/surrogate_key.sql:**
```sql
{% macro surrogate_key(field_list) %}
  md5(concat_ws('|', {{ field_list | join(', ') }}))
{% endmacro %}
```

**macros/generate_date_spine.sql:**
```sql
{% macro generate_date_spine(start_date, end_date) %}
  SELECT
    dateadd(day, seq, '{{ start_date }}'::date) as date_day
  FROM (
    SELECT row_number() over () - 1 as seq
    FROM stl_connection_log
    LIMIT datediff(day, '{{ start_date }}'::date, '{{ end_date }}'::date) + 1
  )
{% endmacro %}
```

---

### 0.3 Lambda Layer Build Script

**infra/scripts/build-dbt-layer.sh:**
```bash
#!/bin/bash
set -e

LAYER_DIR="layer"
rm -rf $LAYER_DIR && mkdir -p $LAYER_DIR/python

echo "Installing dbt dependencies..."
pip install dbt-core dbt-redshift -t $LAYER_DIR/python --quiet

echo "Optimizing layer size..."
find $LAYER_DIR -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
find $LAYER_DIR -name '*.pyc' -delete 2>/dev/null || true
find $LAYER_DIR -name '*.dist-info' -type d -exec rm -rf {} + 2>/dev/null || true
find $LAYER_DIR -name 'tests' -type d -exec rm -rf {} + 2>/dev/null || true

# Remove packages not needed at runtime
rm -rf $LAYER_DIR/python/psycopg2* 2>/dev/null || true
rm -rf $LAYER_DIR/python/setuptools* 2>/dev/null || true
rm -rf $LAYER_DIR/python/babel* 2>/dev/null || true
rm -rf $LAYER_DIR/python/networkx* 2>/dev/null || true

echo "Creating zip..."
cd $LAYER_DIR && zip -r -q ../dbt-redshift-layer.zip python

echo "Layer size:"
du -sh python
ls -lh ../dbt-redshift-layer.zip
```

**Expected output:** ~75 MB unzipped, ~29 MB zipped

---

### 0.4 Lambda Handler

**src/lambdas/dbt_runner/handler.py:**
```python
import subprocess
import os
import json

def handler(event, context):
    command = event.get('command', 'run')
    select = event.get('select', '')

    cmd = ['dbt', command]
    if select:
        cmd.extend(['--select', select])

    # Set dbt project directory
    os.chdir('/opt/python/dbt_gold')

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=840  # 14 min (leave 1 min buffer)
    )

    return {
        'statusCode': 0 if result.returncode == 0 else 1,
        'command': ' '.join(cmd),
        'stdout': result.stdout[-4000:],  # Last 4KB
        'stderr': result.stderr[-2000:] if result.returncode != 0 else ''
    }
```

---

### 0.5 Terraform - Security Groups

```hcl
# Security Group for Lambda (dbt-runner)
resource "aws_security_group" "lambda_dbt" {
  name        = "${var.project_name}-lambda-dbt"
  description = "Security group for dbt Lambda function"
  vpc_id      = var.vpc_id

  egress {
    from_port       = 5439
    to_port         = 5439
    protocol        = "tcp"
    description     = "Redshift Serverless"
    security_groups = [aws_security_group.redshift.id]
  }

  egress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    description     = "HTTPS (VPC Endpoints)"
    prefix_list_ids = [data.aws_prefix_list.s3.id]
    security_groups = [aws_security_group.vpc_endpoints.id]
  }
}

# Security Group for Redshift Serverless
resource "aws_security_group" "redshift" {
  name        = "${var.project_name}-redshift"
  description = "Security group for Redshift Serverless"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5439
    to_port         = 5439
    protocol        = "tcp"
    description     = "Lambda dbt-runner"
    security_groups = [aws_security_group.lambda_dbt.id]
  }
}

# Security Group for VPC Endpoints
resource "aws_security_group" "vpc_endpoints" {
  name        = "${var.project_name}-vpc-endpoints"
  description = "Security group for VPC endpoints"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    description     = "HTTPS from Lambda"
    security_groups = [aws_security_group.lambda_dbt.id]
  }
}
```

---

### 0.6 Terraform - Redshift Serverless

```hcl
resource "aws_redshiftserverless_namespace" "gold" {
  namespace_name      = "${var.project_name}-gold"
  db_name             = "analytics"
  admin_username      = "admin"
  admin_user_password = random_password.redshift_admin.result
  iam_roles           = [aws_iam_role.redshift_spectrum.arn]

  tags = {
    Environment = var.environment
  }
}

resource "aws_redshiftserverless_workgroup" "gold" {
  namespace_name = aws_redshiftserverless_namespace.gold.namespace_name
  workgroup_name = "${var.project_name}-gold-workgroup"
  base_capacity  = var.redshift_base_rpu  # 8 RPU minimum

  security_group_ids = [aws_security_group.redshift.id]
  subnet_ids         = var.private_subnet_ids  # Must be 3+ AZs

  config_parameter {
    parameter_key   = "enable_case_sensitive_identifier"
    parameter_value = "true"
  }
}

resource "random_password" "redshift_admin" {
  length  = 32
  special = false
}
```

---

### 0.7 Terraform - VPC Endpoints (Single-AZ for Cost)

```hcl
# S3 Gateway Endpoint (FREE)
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = var.private_route_table_ids
}

# CloudWatch Logs Interface Endpoint (~$7/month single-AZ)
resource "aws_vpc_endpoint" "logs" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.logs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [var.private_subnet_ids[0]]  # Single AZ
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
}

# Secrets Manager Interface Endpoint (~$7/month single-AZ)
# Only needed if NOT using IAM auth
resource "aws_vpc_endpoint" "secretsmanager" {
  count               = var.use_iam_auth ? 0 : 1
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [var.private_subnet_ids[0]]  # Same AZ as logs
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
}
```

---

### 0.8 Terraform - Lambda dbt Runner

```hcl
resource "aws_lambda_function" "dbt_runner" {
  function_name = "${var.project_name}-dbt-runner"
  role          = aws_iam_role.lambda_dbt.arn
  handler       = "handler.handler"
  runtime       = "python3.11"
  timeout       = 900  # 15 minutes
  memory_size   = 512

  layers = [
    aws_lambda_layer_version.dbt_redshift.arn,
    aws_lambda_layer_version.dbt_project.arn
  ]

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda_dbt.id]
  }

  environment {
    variables = {
      REDSHIFT_HOST = aws_redshiftserverless_workgroup.gold.endpoint[0].address
      REDSHIFT_USER = "admin"
      DBT_PROFILES_DIR = "/opt/python/dbt_gold"
    }
  }
}
```

---

### 0.9 Terraform - Redshift IAM Role (for Spectrum)

```hcl
resource "aws_iam_role" "redshift_spectrum" {
  name = "${var.project_name}-redshift-spectrum"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "redshift.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "redshift_spectrum" {
  role = aws_iam_role.redshift_spectrum.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetPartition",
          "glue:GetPartitions"
        ]
        Resource = [
          "arn:aws:glue:${var.region}:${var.account_id}:catalog",
          "arn:aws:glue:${var.region}:${var.account_id}:database/silver_*",
          "arn:aws:glue:${var.region}:${var.account_id}:table/silver_*/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.silver_bucket}",
          "arn:aws:s3:::${var.silver_bucket}/*"
        ]
      }
    ]
  })
}
```

---

### 0.10 Create Redshift External Schema (One-time)

```sql
-- Run this manually after Redshift is created
CREATE EXTERNAL SCHEMA silver_linkedin
FROM DATA CATALOG
DATABASE 'silver_linkedin'
IAM_ROLE 'arn:aws:iam::ACCOUNT:role/PROJECT-redshift-spectrum'
CREATE EXTERNAL DATABASE IF NOT EXISTS;

CREATE EXTERNAL SCHEMA silver_companies
FROM DATA CATALOG
DATABASE 'silver_companies'
IAM_ROLE 'arn:aws:iam::ACCOUNT:role/PROJECT-redshift-spectrum'
CREATE EXTERNAL DATABASE IF NOT EXISTS;

CREATE EXTERNAL SCHEMA silver_ai
FROM DATA CATALOG
DATABASE 'silver_ai_enrichment'
IAM_ROLE 'arn:aws:iam::ACCOUNT:role/PROJECT-redshift-spectrum'
CREATE EXTERNAL DATABASE IF NOT EXISTS;

-- Create Gold schema
CREATE SCHEMA IF NOT EXISTS gold;
```

---

## Acceptance Criteria

- [ ] `terraform apply` completes without errors
- [ ] Redshift Serverless workgroup is accessible
- [ ] Lambda can run `dbt debug` successfully
- [ ] External schemas query Silver data via Spectrum
- [ ] VPC endpoints allow Lambda to log and access S3

---

## Cost Estimate

| Component | Monthly Cost |
|-----------|--------------|
| Redshift Serverless (8 RPU, ~1-2hr/day) | ~$20-30 |
| VPC Endpoints (single-AZ) | ~$7-15 |
| Lambda | ~$1 |
| **Total** | **~$28-46** |
