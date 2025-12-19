# Gold Layer - dbt + Redshift Serverless Implementation Plan

## Overview

Implementar o Gold Layer usando **dbt + Redshift Serverless** em arquitetura 100% serverless.

| Aspect | Decision |
|--------|----------|
| **Transform Engine** | dbt-core + dbt-redshift |
| **Compute** | AWS Lambda (dbt runner) |
| **Data Warehouse** | Amazon Redshift Serverless |
| **Orchestration** | Step Functions |
| **Storage** | Redshift Managed Storage |
| **Catalog** | Redshift + Glue Data Catalog |
| **Cost Estimate** | ~$30-50/month |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ORCHESTRATION                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   EventBridge ──► Step Functions ──► Lambda (dbt runner)                    │
│   (daily 6AM)     (orchestrate)      (execute dbt)                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DBT EXECUTION                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Lambda                    dbt                 Redshift Serverless          │
│   ┌─────────────┐      ┌──────────────┐      ┌─────────────────┐           │
│   │ dbt Layer   │─────►│ Compile SQL  │─────►│ Execute Queries │           │
│   │ Project     │      │ Run Models   │      │ (RPU-based)     │           │
│   └─────────────┘      └──────────────┘      └─────────────────┘           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Silver (S3/Glue)             Gold (Redshift Serverless)                  │
│   ┌─────────────────┐         ┌─────────────────────────────────┐          │
│   │ linkedin/       │────────►│ gold.dimensions (55 tables)     │          │
│   │ linkedin_co/    │  COPY   │ gold.facts      (1 table)       │          │
│   │ ai_enrichment/  │────────►│ gold.bridges    (16 tables)     │          │
│   └─────────────────┘         │ gold.aggs       (8 tables)      │          │
│   (External Schema)           │ gold.confidence (1 table)       │          │
│                               └─────────────────────────────────┘          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Project Setup
### Phase 2: Lambda Layer & Runner
### Phase 3: Staging Models (Silver refs)
### Phase 4: Dimension Models
### Phase 5: Fact & Bridge Models
### Phase 6: Aggregations & Tests
### Phase 7: Orchestration (Step Functions)
### Phase 8: Documentation
### Phase 9: Observability & Alerting

---

## Phase 1: Project Setup

**Goal**: Create dbt project structure and local development environment.

### Tasks

- [ ] **1.1** Create dbt project directory structure
  ```
  dbt_gold/
  ├── dbt_project.yml
  ├── profiles.yml
  ├── packages.yml
  ├── models/
  │   ├── staging/
  │   ├── dimensions/
  │   ├── facts/
  │   ├── bridges/
  │   └── aggregations/
  ├── macros/
  ├── tests/
  ├── seeds/
  └── snapshots/
  ```

- [ ] **1.2** Configure `dbt_project.yml`
  ```yaml
  name: 'gold_layer'
  version: '1.0.0'
  config-version: 2

  profile: 'gold_layer'

  model-paths: ["models"]
  analysis-paths: ["analyses"]
  test-paths: ["tests"]
  seed-paths: ["seeds"]
  macro-paths: ["macros"]
  snapshot-paths: ["snapshots"]

  target-path: "target"
  clean-targets: ["target", "dbt_packages"]

  models:
    gold_layer:
      staging:
        +materialized: view
        +schema: staging
      dimensions:
        +materialized: table
        +schema: gold
        +tags: ['dimensions']
      facts:
        +materialized: incremental
        +incremental_strategy: delete+insert  # NOT append (creates duplicates)
        +schema: gold
        +tags: ['facts']
      bridges:
        +materialized: table
        +schema: gold
        +tags: ['bridges']
      aggregations:
        +materialized: table
        +schema: gold
        +tags: ['aggregations']
  ```

- [ ] **1.3** Configure `profiles.yml`
  ```yaml
  # Reference: https://docs.getdbt.com/docs/core/connect-data-platform/redshift-setup
  gold_layer:
    target: prod
    outputs:
      prod:
        type: redshift
        # Connection (Serverless endpoint format)
        host: "{{ env_var('REDSHIFT_HOST') }}"  # workgroup.account-id.region.redshift-serverless.amazonaws.com
        port: 5439
        dbname: analytics  # Create this DB (AWS default is "dev")
        schema: gold

        # Auth - IAM (recommended for Serverless)
        method: iam
        user: dbt_user  # Ignored for Serverless but required
        region: us-east-1
        # cluster_id: not needed for Serverless
        # iam_profile: default  # Or use env vars AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

        # Performance
        threads: 4
        connect_timeout: 30
        retries: 3

        # Optional
        ra3_node: true      # Enable cross-database sources (Spectrum)
        autocommit: true    # Default, required for DDL
        sslmode: require    # SSL connection mode
  ```

  > **Note**: For Redshift Serverless with IAM auth:
  > - `user` field is ignored but still required
  > - `cluster_id` is not needed
  > - Use `iam_profile` or env vars (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
  > - Lambda uses IAM role automatically (no credentials needed)

- [ ] **1.4** Configure `packages.yml`
  ```yaml
  packages:
    - package: dbt-labs/dbt_utils
      version: 1.1.1
    - package: calogica/dbt_expectations
      version: 0.10.1
  ```

- [ ] **1.5** Install dependencies locally
  ```bash
  # dbt-redshift uses redshift_connector (not psycopg2) since v1.5
  pip install dbt-core dbt-redshift
  cd dbt_gold
  dbt deps
  dbt debug
  ```

- [ ] **1.6** Create Redshift database and schemas
  ```sql
  -- Connect to Redshift Serverless (default "dev" database first)
  CREATE DATABASE analytics;

  -- Switch to analytics database, then create schemas
  \c analytics
  CREATE SCHEMA IF NOT EXISTS gold;
  CREATE SCHEMA IF NOT EXISTS staging;
  ```

- [ ] **1.7** Create external schema for Silver (S3/Glue)
  ```sql
  -- Allow Redshift to query Silver data via Spectrum
  CREATE EXTERNAL SCHEMA silver_external
  FROM DATA CATALOG
  DATABASE 'silver'
  IAM_ROLE 'arn:aws:iam::ACCOUNT:role/RedshiftSpectrumRole'
  REGION 'us-east-1';
  ```

### Acceptance Criteria
- [ ] `dbt debug` passes
- [ ] Can connect to Redshift Serverless
- [ ] Database `analytics` created
- [ ] Schema `gold` and `staging` created
- [ ] External schema `silver_external` created

---

## Phase 2: Lambda Layer & Runner

**Goal**: Create serverless dbt execution environment.

### Lambda Layer Size Analysis

> **Initial Concern**: dbt dependencies estimated at ~300 MB, exceeding the 250 MB Lambda layer limit.
>
> **Actual Measurement**: Layer fits comfortably within limits.

| Version | Unzipped | Zipped | Status |
|---------|----------|--------|--------|
| Original (all deps) | 173 MB | 59 MB | ✓ Under 250 MB limit |
| Optimized (no tests/cache) | 112 MB | 39 MB | ✓ Under 50 MB direct upload |
| **Minimal (recommended)** | **75 MB** | **29 MB** | ✓ Best option |

**Optimization removals:**
- `__pycache__`, `*.pyc`, `*.dist-info` (~10 MB)
- `psycopg2` (~11 MB) - not needed, dbt-redshift uses `redshift_connector`
- `setuptools` (~10 MB) - not needed at runtime
- `babel` (~33 MB) - i18n only, not needed
- `networkx` (~18 MB) - lineage graph generation (run locally with `dbt docs`)

**Verified packages in minimal layer:**
- ✓ dbt-core + dbt-redshift
- ✓ redshift_connector
- ✓ boto3, botocore
- ✓ jinja2, pydantic

---

### Tasks

- [ ] **2.1** Create optimized dbt Lambda Layer build script
  ```bash
  #!/bin/bash
  # infra/scripts/build-dbt-layer.sh
  set -e

  LAYER_DIR="layer"
  rm -rf $LAYER_DIR && mkdir -p $LAYER_DIR/python

  echo "Installing dbt dependencies..."
  pip install dbt-core dbt-redshift -t $LAYER_DIR/python --quiet

  echo "Optimizing layer size..."
  # Remove unnecessary files
  find $LAYER_DIR -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
  find $LAYER_DIR -name '*.pyc' -delete 2>/dev/null || true
  find $LAYER_DIR -name '*.dist-info' -type d -exec rm -rf {} + 2>/dev/null || true
  find $LAYER_DIR -name 'tests' -type d -exec rm -rf {} + 2>/dev/null || true

  # Remove packages not needed at runtime
  rm -rf $LAYER_DIR/python/psycopg2* 2>/dev/null || true       # Not used by dbt-redshift
  rm -rf $LAYER_DIR/python/setuptools* 2>/dev/null || true     # Not needed at runtime
  rm -rf $LAYER_DIR/python/babel* 2>/dev/null || true          # i18n only
  rm -rf $LAYER_DIR/python/networkx* 2>/dev/null || true       # Lineage graph only

  echo "Creating zip..."
  cd $LAYER_DIR && zip -r -q ../dbt-redshift-layer.zip python

  echo "Layer size:"
  du -sh python
  ls -lh ../dbt-redshift-layer.zip
  ```

- [ ] **2.2** Create dbt project Lambda Layer
  ```bash
  # Package dbt project as layer
  zip -r dbt-project-layer.zip dbt_gold/
  ```

- [ ] **2.3** Create Lambda function `dbt-runner`
  - Runtime: Python 3.11
  - Memory: 512 MB
  - Timeout: 15 minutes
  - Layers: dbt-redshift-layer, dbt-project-layer
  - VPC: Required (Redshift Serverless runs in VPC)

- [ ] **2.4** Create Lambda handler
  ```python
  # src/lambdas/dbt_runner/handler.py
  def handler(event, context):
      command = event.get('command', 'run')
      select = event.get('select', '')
      # Execute dbt command
  ```

- [ ] **2.5** Create IAM role with permissions
  - Redshift: GetClusterCredentials, ExecuteStatement, GetStatementResult
  - Redshift-Serverless: GetCredentials, GetWorkgroup
  - S3: Read Silver (for Spectrum), Write unload results
  - Glue: GetTable, GetDatabase (for Spectrum external tables)
  - EC2: CreateNetworkInterface, DescribeNetworkInterfaces (VPC access)

- [ ] **2.6** Add dbt_docs bucket to storage module
  ```hcl
  # infra/modules/storage/variables.tf (ADD)
  variable "dbt_docs_bucket_name" {
    description = "Bucket for dbt documentation"
    type        = string
    default     = "dbt-docs"
  }
  ```

  ```hcl
  # infra/modules/storage/main.tf (ADD)
  resource "aws_s3_bucket" "dbt_docs" {
    bucket = var.dbt_docs_bucket_name
  }
  ```

  ```hcl
  # infra/modules/storage/outputs.tf (ADD)
  output "dbt_docs_bucket_name" {
    description = "Nome do bucket de documentação dbt"
    value       = aws_s3_bucket.dbt_docs.bucket
  }

  output "dbt_docs_bucket_arn" {
    description = "ARN do bucket de documentação dbt"
    value       = aws_s3_bucket.dbt_docs.arn
  }
  ```

- [ ] **2.7** Create gold_dbt module structure
  ```
  infra/modules/gold_dbt/
  ├── variables.tf              # Module inputs
  ├── outputs.tf                # Module outputs
  ├── redshift_serverless.tf    # Namespace + Workgroup
  ├── redshift_iam.tf           # Spectrum IAM role
  ├── lambda.tf                 # dbt-runner Lambda
  ├── lambda_iam.tf             # Lambda IAM role
  ├── layers.tf                 # dbt Lambda layers
  ├── security_groups.tf        # VPC security groups
  ├── vpc_endpoints.tf          # S3, CloudWatch endpoints
  └── docs_hosting.tf           # CloudFront for dbt docs
  ```

- [ ] **2.8** Create module variables (following project pattern)
  ```hcl
  # infra/modules/gold_dbt/variables.tf
  variable "project_name" {
    description = "Project name for resource naming"
    type        = string
  }

  variable "environment" {
    description = "Environment name (dev, staging, prod)"
    type        = string
  }

  # Bucket references (from storage module)
  variable "silver_bucket_name" {
    description = "Silver bucket name (for Spectrum)"
    type        = string
  }

  variable "silver_bucket_arn" {
    description = "Silver bucket ARN"
    type        = string
  }

  variable "dbt_docs_bucket_name" {
    description = "dbt docs bucket name"
    type        = string
  }

  variable "dbt_docs_bucket_arn" {
    description = "dbt docs bucket ARN"
    type        = string
  }

  # Redshift configuration (password managed via Secrets Manager)
  variable "redshift_base_capacity" {
    description = "Redshift Serverless base RPU (8-512)"
    type        = number
    default     = 8
  }

  variable "redshift_database_name" {
    description = "Redshift database name"
    type        = string
    default     = "analytics"
  }

  # VPC configuration (Redshift Serverless requires 3 AZs minimum)
  variable "vpc_id" {
    description = "VPC ID for Lambda and Redshift"
    type        = string
  }

  variable "private_subnet_ids" {
    description = "Private subnet IDs (minimum 3, in different AZs)"
    type        = list(string)

    validation {
      condition     = length(var.private_subnet_ids) >= 3
      error_message = "Redshift Serverless requires at least 3 subnets."
    }
  }

  # AZ validation (done via data source, see redshift.tf)
  ```

- [ ] **2.8b** Validate AZ distribution (not just count)
  ```hcl
  # infra/modules/gold_dbt/redshift.tf

  # Validate that subnets are in different AZs
  data "aws_subnet" "private" {
    for_each = toset(var.private_subnet_ids)
    id       = each.value
  }

  locals {
    unique_azs = distinct([for s in data.aws_subnet.private : s.availability_zone])
  }

  # This will fail terraform plan if AZs < 3
  resource "null_resource" "validate_azs" {
    count = length(local.unique_azs) >= 3 ? 0 : "ERROR: Subnets must be in at least 3 different AZs"
  }

  variable "private_route_table_ids" {
    description = "Private route table IDs (for S3 Gateway Endpoint)"
    type        = list(string)
  }

  # S3 prefixes (following project pattern)
  variable "silver_prefix" {
    description = "S3 prefix for Silver linkedin data"
    type        = string
    default     = "linkedin/"
  }

  variable "silver_companies_prefix" {
    description = "S3 prefix for Silver companies data"
    type        = string
    default     = "linkedin_companies/"
  }

  variable "silver_ai_prefix" {
    description = "S3 prefix for Silver AI enrichment data"
    type        = string
    default     = "ai_enrichment/"
  }
  ```

- [ ] **2.9** Create Security Groups
  ```hcl
  # infra/modules/gold_dbt/security_groups.tf

  # Security Group for Lambda (dbt-runner)
  resource "aws_security_group" "lambda_dbt" {
    name        = "${var.project_name}-${var.environment}-lambda-dbt"
    description = "Security group for dbt Lambda function"
    vpc_id      = var.vpc_id

    # Outbound to Redshift
    egress {
      description     = "Redshift Serverless"
      from_port       = 5439
      to_port         = 5439
      protocol        = "tcp"
      security_groups = [aws_security_group.redshift.id]
    }

    # Outbound to S3 (via VPC endpoint)
    egress {
      description     = "S3 VPC Endpoint"
      from_port       = 443
      to_port         = 443
      protocol        = "tcp"
      prefix_list_ids = [data.aws_prefix_list.s3.id]
    }

    tags = {
      Name        = "${var.project_name}-${var.environment}-lambda-dbt"
      Project     = var.project_name
      Environment = var.environment
    }
  }

  # Security Group for Redshift Serverless
  resource "aws_security_group" "redshift" {
    name        = "${var.project_name}-${var.environment}-redshift"
    description = "Security group for Redshift Serverless"
    vpc_id      = var.vpc_id

    # Inbound from Lambda
    ingress {
      description     = "Lambda dbt-runner"
      from_port       = 5439
      to_port         = 5439
      protocol        = "tcp"
      security_groups = [aws_security_group.lambda_dbt.id]
    }

    # Outbound to S3 (for Spectrum)
    egress {
      description     = "S3 for Spectrum"
      from_port       = 443
      to_port         = 443
      protocol        = "tcp"
      prefix_list_ids = [data.aws_prefix_list.s3.id]
    }

    tags = {
      Name        = "${var.project_name}-${var.environment}-redshift"
      Project     = var.project_name
      Environment = var.environment
    }
  }

  # S3 prefix list for VPC endpoint
  data "aws_prefix_list" "s3" {
    filter {
      name   = "prefix-list-name"
      values = ["com.amazonaws.${data.aws_region.current.name}.s3"]
    }
  }

  data "aws_region" "current" {}
  ```

- [ ] **2.10** Create Secrets Manager for Redshift password
  ```hcl
  # infra/modules/gold_dbt/secrets.tf

  # Generate random password
  resource "random_password" "redshift_admin" {
    length           = 32
    special          = true
    override_special = "!#$%&*()-_=+[]{}<>:?"
  }

  # Store in Secrets Manager
  resource "aws_secretsmanager_secret" "redshift_admin" {
    name        = "${var.project_name}/${var.environment}/redshift-admin"
    description = "Redshift Serverless admin credentials"

    tags = {
      Project     = var.project_name
      Environment = var.environment
    }
  }

  resource "aws_secretsmanager_secret_version" "redshift_admin" {
    secret_id = aws_secretsmanager_secret.redshift_admin.id
    secret_string = jsonencode({
      username = "admin"
      password = random_password.redshift_admin.result
      host     = aws_redshiftserverless_workgroup.gold.endpoint[0].address
      port     = 5439
      database = var.redshift_database_name
    })
  }

  # IAM policy for Lambda to read secret
  resource "aws_iam_policy" "lambda_secrets" {
    name = "${var.project_name}-${var.environment}-lambda-secrets"
    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [{
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.redshift_admin.arn
      }]
    })
  }
  ```

- [ ] **2.11** Create Redshift Serverless resources
  ```hcl
  # infra/modules/gold_dbt/redshift_serverless.tf
  resource "aws_redshiftserverless_namespace" "gold" {
    namespace_name      = "${var.project_name}-${var.environment}-gold"
    db_name             = var.redshift_database_name
    admin_username      = "admin"
    admin_user_password = random_password.redshift_admin.result  # From Secrets Manager
    iam_roles           = [aws_iam_role.redshift_spectrum.arn]

    # Manage credentials externally
    manage_admin_password = false

    tags = {
      Project     = var.project_name
      Environment = var.environment
    }
  }

  resource "aws_redshiftserverless_workgroup" "gold" {
    namespace_name = aws_redshiftserverless_namespace.gold.namespace_name
    workgroup_name = "${var.project_name}-${var.environment}-gold"
    base_capacity  = var.redshift_base_capacity

    # VPC configuration (requires 3 AZs)
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.redshift.id]

    # Require SSL connections
    config_parameter {
      parameter_key   = "require_ssl"
      parameter_value = "true"
    }

    config_parameter {
      parameter_key   = "enable_user_activity_logging"
      parameter_value = "true"
    }

    tags = {
      Project     = var.project_name
      Environment = var.environment
    }
  }
  ```

- [ ] **2.11** Create VPC Endpoints
  ```hcl
  # infra/modules/gold_dbt/vpc_endpoints.tf

  # S3 Gateway Endpoint (FREE - required for Spectrum)
  resource "aws_vpc_endpoint" "s3" {
    vpc_id            = var.vpc_id
    service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
    vpc_endpoint_type = "Gateway"
    route_table_ids   = var.private_route_table_ids

    tags = {
      Name        = "${var.project_name}-${var.environment}-s3-endpoint"
      Project     = var.project_name
      Environment = var.environment
    }
  }

  # CloudWatch Logs Interface Endpoint (for Lambda logs)
  resource "aws_vpc_endpoint" "logs" {
    vpc_id              = var.vpc_id
    service_name        = "com.amazonaws.${data.aws_region.current.name}.logs"
    vpc_endpoint_type   = "Interface"
    subnet_ids          = var.private_subnet_ids
    security_group_ids  = [aws_security_group.vpc_endpoints.id]
    private_dns_enabled = true

    tags = {
      Name        = "${var.project_name}-${var.environment}-logs-endpoint"
      Project     = var.project_name
      Environment = var.environment
    }
  }

  # Secrets Manager Interface Endpoint (REQUIRED for Lambda in VPC)
  # Without this, Lambda cannot retrieve Redshift credentials from Secrets Manager
  # See: https://repost.aws/knowledge-center/lambda-secret-vpc
  resource "aws_vpc_endpoint" "secretsmanager" {
    vpc_id              = var.vpc_id
    service_name        = "com.amazonaws.${data.aws_region.current.name}.secretsmanager"
    vpc_endpoint_type   = "Interface"
    subnet_ids          = var.private_subnet_ids
    security_group_ids  = [aws_security_group.vpc_endpoints.id]
    private_dns_enabled = true

    tags = {
      Name        = "${var.project_name}-${var.environment}-secretsmanager-endpoint"
      Project     = var.project_name
      Environment = var.environment
    }
  }

  # Security Group for VPC Endpoints
  resource "aws_security_group" "vpc_endpoints" {
    name        = "${var.project_name}-${var.environment}-vpc-endpoints"
    description = "Security group for VPC endpoints"
    vpc_id      = var.vpc_id

    ingress {
      description     = "HTTPS from Lambda"
      from_port       = 443
      to_port         = 443
      protocol        = "tcp"
      security_groups = [aws_security_group.lambda_dbt.id]
    }

    tags = {
      Name        = "${var.project_name}-${var.environment}-vpc-endpoints"
      Project     = var.project_name
      Environment = var.environment
    }
  }
  ```

- [ ] **2.12** Create module outputs
  ```hcl
  # infra/modules/gold_dbt/outputs.tf
  output "redshift_workgroup_endpoint" {
    description = "Redshift Serverless workgroup endpoint"
    value       = aws_redshiftserverless_workgroup.gold.endpoint[0].address
  }

  output "redshift_workgroup_name" {
    description = "Redshift Serverless workgroup name"
    value       = aws_redshiftserverless_workgroup.gold.workgroup_name
  }

  output "redshift_namespace_name" {
    description = "Redshift Serverless namespace name"
    value       = aws_redshiftserverless_namespace.gold.namespace_name
  }

  output "redshift_database_name" {
    description = "Redshift database name"
    value       = var.redshift_database_name
  }

  output "dbt_runner_lambda_arn" {
    description = "dbt runner Lambda ARN"
    value       = aws_lambda_function.dbt_runner.arn
  }

  output "dbt_docs_cloudfront_url" {
    description = "dbt docs CloudFront URL"
    value       = "https://${aws_cloudfront_distribution.dbt_docs.domain_name}"
  }
  ```

- [ ] **2.11** Wire module in environment (following project pattern)
  ```hcl
  # infra/environments/dev/main.tf (ADD)
  module "gold_dbt" {
    source       = "../../modules/gold_dbt"
    project_name = var.project_name
    environment  = var.environment

    # Bucket references (from storage module)
    silver_bucket_name   = module.storage.silver_bucket_name
    silver_bucket_arn    = module.storage.silver_bucket_arn
    dbt_docs_bucket_name = module.storage.dbt_docs_bucket_name
    dbt_docs_bucket_arn  = module.storage.dbt_docs_bucket_arn

    # S3 prefixes
    silver_prefix           = "linkedin/"
    silver_companies_prefix = "linkedin_companies/"
    silver_ai_prefix        = "ai_enrichment/"

    # Redshift configuration (password auto-generated and stored in Secrets Manager)
    redshift_base_capacity  = 8
    redshift_database_name  = "analytics"

    # VPC configuration (Redshift requires 3 AZs)
    vpc_id                  = module.vpc.vpc_id
    private_subnet_ids      = module.vpc.private_subnet_ids
    private_route_table_ids = module.vpc.private_route_table_ids
  }
  ```

  ```hcl
  # infra/environments/dev/main.tf - Update storage module call
  module "storage" {
    source      = "../../modules/storage/"
    environment = var.environment

    bronze_bucket_name         = "data-engineer-jobs-bronze"
    silver_bucket_name         = "data-engineer-jobs-silver"
    gold_bucket_name           = "data-engineer-jobs-gold"
    glue_temp_bucket_name      = "data-engineer-jobs-glue-temp"
    glue_scripts_bucket_name   = "data-engineer-jobs-glue-scripts"
    athena_results_bucket_name = "data-engineer-jobs-athena-results"
    dbt_docs_bucket_name       = "data-engineer-jobs-dbt-docs"  # ADD
  }
  ```

- [ ] **2.12** Test Lambda locally with SAM
  ```bash
  sam local invoke DbtRunner --event test-event.json
  ```

### Acceptance Criteria
- [ ] Storage module updated with dbt_docs bucket
- [ ] gold_dbt module created with all resources
- [ ] Redshift Serverless workgroup created
- [ ] Lambda deploys successfully (in VPC)
- [ ] `dbt debug` runs in Lambda
- [ ] `dbt run --select dim_date` works

---

## Phase 3: Staging Models (Silver refs)

**Goal**: Create staging layer that references Silver sources.

### Spectrum Query Performance Analysis

#### The Re-scan Problem

When staging models are **views** over Spectrum external tables, every downstream model re-scans S3:

```
┌──────────────────────────────────────────────────────────────────┐
│  VIEWS (Current Design)                                          │
│                                                                  │
│  S3 (Silver)                                                     │
│       ↓                                                          │
│  stg_linkedin (VIEW) ──────┬──► dim_company      (scan #1)       │
│       ↓                    ├──► dim_location     (scan #2)       │
│       ↓                    ├──► fact_job_posting (scan #3)       │
│       ↓                    └──► bridge_* (x16)   (scans #4-19)   │
│                                                                  │
│  Problem: 20 downstream models = 20 S3 scans                     │
└──────────────────────────────────────────────────────────────────┘
```

#### Impact Analysis (Current Data: ~364 MB Silver)

| Scenario | Data Scanned | Cost/Run | Time |
|----------|--------------|----------|------|
| Full scan (no pruning) | 364 MB × 20 = 7.3 GB | $0.036 | ~40s |
| **With partition pruning** | 43 MB × 20 = 860 MB | $0.004 | ~17s |
| Materialized staging | 43 MB × 1 = 43 MB | $0.0002 | ~11s |

> **Key Insight**: With **partition pruning** (year/month/day/hour), we only scan ~43 MB per 4h window, not the full 364 MB.

#### Why It's NOT a Critical Problem (Yet)

1. **Small data volume**: 364 MB total, ~43 MB per 4h window
2. **Partition pruning**: Silver is partitioned by `year/month/day/hour`
3. **Parquet pushdown**: Columnar format + predicate pushdown reduces bytes read
4. **Incremental processing**: Only processing new data each run
5. **Serverless auto-scaling**: Redshift Serverless scales for concurrent queries

#### Cost Projection

| Timeframe | Silver Size | Full Scan/Month | With Pruning/Month |
|-----------|-------------|-----------------|-------------------|
| Current | 364 MB | $0.31 | $0.04 |
| 6 months | 1.4 GB | $1.20 | $0.04 |
| 1 year | 2.8 GB | $2.40 | $0.04 |

> Partition pruning keeps costs constant regardless of historical data growth!

#### Recommendation: Views → Tables Migration Path

```yaml
# Stage 1: Start with views (current implementation)
# models/staging/stg_linkedin.sql
{{ config(materialized='view') }}

SELECT * FROM {{ source('silver', 'linkedin') }}
WHERE year = {{ var('year') }}
  AND month = {{ var('month') }}
  AND day >= {{ var('day_start') }}

# Stage 2: Switch to tables if needed (future optimization)
{{ config(
    materialized='table',
    pre_hook="TRUNCATE {{ this }}"
) }}
```

**Switch to materialized tables when:**
- [ ] Pipeline duration exceeds 10 minutes
- [ ] Silver data exceeds 10 GB
- [ ] Concurrent query contention observed in CloudWatch
- [ ] Spectrum costs exceed $10/month

#### Partition Pruning Implementation

```sql
-- models/staging/stg_linkedin.sql
{{ config(materialized='view') }}

SELECT
    job_posting_id,
    job_title,
    company_id,
    -- ... columns
FROM {{ source('silver', 'linkedin') }}
{% if is_incremental() %}
-- Partition pruning: only scan recent partitions
WHERE year = EXTRACT(YEAR FROM CURRENT_DATE)
  AND month = EXTRACT(MONTH FROM CURRENT_DATE)
  AND day >= EXTRACT(DAY FROM CURRENT_DATE) - 1
{% endif %}
```

---

### Tasks

- [ ] **3.1** Create sources.yml
  ```yaml
  # models/staging/sources.yml
  version: 2
  sources:
    - name: silver
      database: analytics  # Redshift database (created in Phase 1)
      schema: silver_external  # Spectrum external schema
      tables:
        - name: linkedin
          description: "Job postings from LinkedIn (S3 via Spectrum)"
          columns:
            - name: job_posting_id
              tests:
                - not_null
                - unique
        - name: linkedin_companies
          description: "Company profiles (S3 via Spectrum)"
        - name: ai_enrichment
          description: "AI-enriched job data (S3 via Spectrum)"
  ```

- [ ] **3.2** Create `stg_linkedin.sql`
  ```sql
  SELECT
      job_posting_id,
      job_title,
      company_id,
      -- ... all columns with clean names
  FROM {{ source('silver', 'linkedin') }}
  ```

- [ ] **3.3** Create `stg_linkedin_companies.sql`

- [ ] **3.4** Create `stg_ai_enrichment.sql`

- [ ] **3.5** Add schema tests for staging models

- [ ] **3.6** Run and validate staging models
  ```bash
  dbt run --select staging
  dbt test --select staging
  ```

### Acceptance Criteria
- [ ] 3 staging models created
- [ ] All tests pass
- [ ] Views created in Redshift `staging` schema

---

## Phase 4: Dimension Models

**Goal**: Create all 55 dimension tables.

### Tasks

#### Static Dimensions (Pre-populated)

- [ ] **4.1** Create seed files for static dimensions
  ```
  seeds/
  ├── dim_date.csv
  ├── dim_time.csv
  ├── dim_seniority.csv
  ├── dim_job_family.csv
  ├── dim_work_model.csv
  ├── dim_employment_type.csv
  ├── dim_contract_type.csv
  ├── dim_cloud_platform.csv
  ├── dim_education.csv
  ├── dim_visa_status.csv
  └── ... (all static dimensions)
  ```

- [ ] **4.2** Load seeds
  ```bash
  dbt seed
  ```

#### Dynamic Dimensions (From Silver)

- [ ] **4.3** Create `dim_company.sql` (SCD Type 2)
  - Source: SLV-CO
  - Surrogate key generation
  - SCD2 logic with snapshots

- [ ] **4.4** Create `dim_location.sql`
  - Source: SLV-LI.job_location
  - Parse city, state, country

- [ ] **4.5** Create `dim_skill.sql` (Snowflake)
  - Source: SLV-LI.skills_canonical
  - Links to dim_skill_type, dim_skill_category, dim_skill_family

- [ ] **4.6** Create remaining dynamic dimensions
  - dim_certification
  - dim_benefit
  - dim_ml_tool
  - dim_strength_category
  - dim_concern_category
  - dim_best_fit_category
  - dim_probe_category
  - dim_leverage_category
  - dim_maturity_signal
  - dim_dev_practice
  - dim_culture_signal
  - dim_career_track
  - dim_country
  - dim_us_state

- [ ] **4.7** Add tests for all dimensions
  ```yaml
  # models/dimensions/schema.yml
  models:
    - name: dim_company
      columns:
        - name: company_key
          tests: [unique, not_null]
        - name: company_id
          tests: [not_null]
  ```

- [ ] **4.8** Run and validate dimensions
  ```bash
  dbt run --select dimensions
  dbt test --select dimensions
  ```

### Acceptance Criteria
- [ ] 55 dimension tables created
- [ ] All surrogate keys generated
- [ ] All tests pass
- [ ] dim_company SCD2 working

---

## Phase 5: Fact & Bridge Models

**Goal**: Create fact table and 16 bridge tables.

### Redshift Incremental Strategy

#### The Duplicate Problem

```
┌─────────────────────────────────────────────────────────────────────┐
│  DEFAULT: append strategy                                            │
│                                                                      │
│  Run 1: job_id='abc' inserted ✓                                      │
│  Run 2: job_id='abc' re-processed → DUPLICATE ❌                     │
│  Run 3: job_id='abc' re-processed → TRIPLICATE ❌❌                   │
│                                                                      │
│  Result: Same job appears multiple times in fact table               │
└─────────────────────────────────────────────────────────────────────┘
```

#### Strategy Comparison for Redshift

| Strategy | Duplicates | Performance | Use Case |
|----------|------------|-------------|----------|
| `append` | YES ❌ | Fastest | Never for facts |
| `delete+insert` | NO ✓ | Fast* | **RECOMMENDED** |
| `merge` | NO ✓ | Slower | If updates needed |
| `insert_overwrite` | NO ✓ | Fast | Partitioned tables |

> **\*** With `incremental_predicates` on sort key, `delete+insert` is very fast.

#### Why delete+insert > merge for Redshift

1. **No primary key enforcement**: Redshift doesn't enforce unique constraints
2. **DELETE optimization**: With `incremental_predicates`, DELETE uses zone map pruning
3. **Simpler logic**: Full row replacement vs column-by-column update
4. **Benchmarks**: [delete+insert typically faster for bulk loads](https://stellans.io/dbt-merge-vs-deleteinsert/)

---

### Tasks

#### Fact Table

- [ ] **5.1** Create `fact_job_posting.sql` with proper incremental config
  ```sql
  -- models/facts/fact_job_posting.sql
  {{ config(
      materialized='incremental',
      unique_key='job_id',
      incremental_strategy='delete+insert',

      -- CRITICAL: Optimize DELETE performance with sort key predicate
      incremental_predicates=[
          "DBT_INTERNAL_DEST.posted_at >= (SELECT MIN(posted_at) FROM DBT_INTERNAL_SOURCE)"
      ],

      -- Redshift physical design
      sort='posted_at',           -- Sort by date for time-series queries
      dist='company_sk'           -- Distribute by company for joins
  ) }}

  WITH source_data AS (
      SELECT
          job_posting_id as job_id,
          job_title,
          company_id,
          posted_at,
          ingestion_timestamp,
          -- ... all columns
      FROM {{ ref('stg_linkedin') }}
      {% if is_incremental() %}
      -- Only process new/updated records
      WHERE ingestion_timestamp > (SELECT MAX(ingestion_timestamp) FROM {{ this }})
      {% endif %}
  ),

  with_keys AS (
      SELECT
          -- Surrogate key
          {{ dbt_utils.generate_surrogate_key(['job_id']) }} as job_sk,

          -- Natural key (for incremental matching)
          job_id,

          -- Dimension keys (lookups)
          c.company_sk,
          l.location_sk,
          d.date_sk as posted_date_sk,
          -- ... 37 dimension keys

          -- Measures
          salary_min_usd,
          salary_max_usd,
          -- ... 17 measures

          -- Flags
          has_salary,
          is_remote,
          -- ... 15 flags

          -- Metadata
          ingestion_timestamp,
          CURRENT_TIMESTAMP as dbt_updated_at

      FROM source_data s
      LEFT JOIN {{ ref('dim_company') }} c ON s.company_id = c.company_id
      LEFT JOIN {{ ref('dim_location') }} l ON s.job_location = l.raw_location
      LEFT JOIN {{ ref('dim_date') }} d ON DATE(s.posted_at) = d.date_day
      -- ... more dimension joins
  )

  SELECT * FROM with_keys
  ```

- [ ] **5.2** Configure model properties
  ```yaml
  # models/facts/schema.yml
  models:
    - name: fact_job_posting
      description: "Grain: 1 row per job posting"
      config:
        contract:
          enforced: true  # Schema enforcement
      columns:
        - name: job_sk
          data_type: varchar
          tests:
            - unique
            - not_null
        - name: job_id
          data_type: varchar
          tests:
            - unique  # Natural key uniqueness
            - not_null
        - name: company_sk
          tests:
            - relationships:
                to: ref('dim_company')
                field: company_sk
  ```

- [ ] **5.3** Add fact table tests
  - Referential integrity to all dimensions
  - Unique job_id (natural key)
  - Not null constraints

#### Bridge Tables

- [ ] **5.3** Create Skills Bridge
  - `bridge_job_skills.sql` (unified hard + soft)
  - Links to dim_skill snowflake

- [ ] **5.4** Create Tech Stack Bridges
  - `bridge_job_certifications.sql`
  - `bridge_job_cloud_stack.sql`
  - `bridge_job_ml_tools.sql`

- [ ] **5.5** Create Benefits & Career Bridges
  - `bridge_job_benefits.sql`
  - `bridge_job_career_tracks.sql`

- [ ] **5.6** Create Geographic Bridges
  - `bridge_job_geo_restrictions.sql`
  - `bridge_job_us_state_restrictions.sql`

- [ ] **5.7** Create Culture & Quality Bridges
  - `bridge_job_maturity_signals.sql`
  - `bridge_job_dev_practices.sql`
  - `bridge_job_culture_signals.sql`

- [ ] **5.8** Create Summary Bridges
  - `bridge_job_strengths.sql`
  - `bridge_job_concerns.sql`
  - `bridge_job_best_fit.sql`
  - `bridge_job_probes.sql`
  - `bridge_job_leverage.sql`

- [ ] **5.9** Add tests for all bridges
  ```yaml
  models:
    - name: bridge_job_skills
      columns:
        - name: job_posting_key
          tests:
            - relationships:
                to: ref('fact_job_posting')
                field: job_posting_key
        - name: skill_key
          tests:
            - relationships:
                to: ref('dim_skill')
                field: skill_key
  ```

- [ ] **5.10** Run and validate
  ```bash
  dbt run --select facts bridges
  dbt test --select facts bridges
  ```

### Acceptance Criteria
- [ ] 1 fact table created
- [ ] 16 bridge tables created
- [ ] All FK relationships valid
- [ ] Incremental working

---

## Phase 6: Aggregations & Tests

**Goal**: Create aggregation tables and comprehensive tests.

### Tasks

#### Aggregation Tables

- [ ] **6.1** Create `agg_daily_job_metrics.sql`
  - Grain: day × seniority × job_family × country × work_model

- [ ] **6.2** Create `agg_weekly_job_metrics.sql`

- [ ] **6.3** Create `agg_monthly_job_metrics.sql`

- [ ] **6.4** Create `agg_skills_demand.sql`
  - Grain: week × skill × seniority × job_family

- [ ] **6.5** Create `agg_salary_benchmarks.sql`
  - Percentiles by dimensions

- [ ] **6.6** Create `agg_posting_time_analysis.sql`
  - Best hours to apply

- [ ] **6.7** Create `agg_hourly_posting_summary.sql`

- [ ] **6.8** Create `job_confidence_details.sql`
  - Field-level confidence from Pass 2/3

#### Data Quality Tests

- [ ] **6.9** Create custom tests
  ```sql
  -- tests/assert_salary_range_valid.sql
  SELECT *
  FROM {{ ref('fact_job_posting') }}
  WHERE salary_min_usd > salary_max_usd
  ```

- [ ] **6.10** Add dbt_expectations tests
  ```yaml
  - dbt_expectations.expect_column_values_to_be_between:
      column_name: recommendation_score
      min_value: 0
      max_value: 1
  ```

- [ ] **6.11** Run full test suite
  ```bash
  dbt test
  ```

#### Cross-Layer Reconciliation

- [ ] **6.12** Create reconciliation model for delta validation
  ```sql
  -- models/data_quality/reconciliation_silver_gold.sql
  {{ config(
      materialized='table',
      tags=['data_quality', 'reconciliation']
  ) }}

  /*
    Reconciliation Strategy:
    - Compare records PROCESSED in this run (Silver delta)
    - vs records INSERTED in Gold (Gold delta)
    - NOT total counts (they will differ by design)
  */

  WITH run_metadata AS (
      -- Get the last successful run timestamp
      SELECT
          COALESCE(
              (SELECT MAX(dbt_updated_at) FROM {{ ref('fact_job_posting') }}),
              '1900-01-01'::timestamp
          ) as last_gold_update
  ),

  silver_delta AS (
      -- Records that SHOULD have been processed (new since last run)
      SELECT
          COUNT(*) as silver_new_records,
          COUNT(DISTINCT job_posting_id) as silver_unique_jobs
      FROM {{ source('silver', 'linkedin') }}
      WHERE ingestion_timestamp > (SELECT last_gold_update FROM run_metadata)
  ),

  gold_delta AS (
      -- Records that WERE processed (inserted/updated in this run)
      SELECT
          COUNT(*) as gold_new_records,
          COUNT(DISTINCT job_id) as gold_unique_jobs
      FROM {{ ref('fact_job_posting') }}
      WHERE dbt_updated_at > (SELECT last_gold_update FROM run_metadata)
  ),

  totals AS (
      -- Total counts for reference
      SELECT
          (SELECT COUNT(*) FROM {{ ref('fact_job_posting') }}) as gold_total,
          (SELECT COUNT(DISTINCT job_posting_id) FROM {{ source('silver', 'linkedin') }}) as silver_total
  )

  SELECT
      CURRENT_TIMESTAMP as reconciliation_timestamp,

      -- Delta comparison (this run)
      s.silver_new_records,
      s.silver_unique_jobs,
      g.gold_new_records,
      g.gold_unique_jobs,

      -- Variance
      s.silver_unique_jobs - g.gold_unique_jobs as delta_variance,

      -- Status
      CASE
          WHEN s.silver_unique_jobs = 0 AND g.gold_unique_jobs = 0 THEN 'NO_NEW_DATA'
          WHEN ABS(s.silver_unique_jobs - g.gold_unique_jobs) <= 10 THEN 'OK'
          WHEN ABS(s.silver_unique_jobs - g.gold_unique_jobs) <= 50 THEN 'WARNING'
          ELSE 'ALERT'
      END as delta_status,

      -- Totals (for reference only)
      t.silver_total,
      t.gold_total,
      t.silver_total - t.gold_total as total_variance,

      -- Expected: totals should match (after full historical load)
      CASE
          WHEN t.silver_total = t.gold_total THEN 'SYNCED'
          WHEN t.gold_total < t.silver_total THEN 'GOLD_BEHIND'  -- Normal during incremental
          ELSE 'GOLD_AHEAD'  -- Potential duplicate issue
      END as total_status

  FROM silver_delta s
  CROSS JOIN gold_delta g
  CROSS JOIN totals t
  ```

- [ ] **6.13** Create reconciliation test (fails on ALERT)
  ```sql
  -- tests/assert_reconciliation_ok.sql
  SELECT *
  FROM {{ ref('reconciliation_silver_gold') }}
  WHERE delta_status = 'ALERT'
  ```

- [ ] **6.14** Create orphan records check
  ```sql
  -- tests/assert_no_orphan_dimension_keys.sql
  -- Fact records with dimension keys that don't exist
  SELECT f.job_id, f.company_sk
  FROM {{ ref('fact_job_posting') }} f
  LEFT JOIN {{ ref('dim_company') }} c ON f.company_sk = c.company_sk
  WHERE c.company_sk IS NULL
    AND f.company_sk IS NOT NULL
  ```

- [ ] **6.15** Create late-arriving data model
  ```sql
  -- models/data_quality/late_arriving_data.sql
  {{ config(materialized='table', tags=['data_quality']) }}

  /*
    Identifies records that arrived late (posted_at << ingestion_timestamp)
    These may need special handling or backfill
  */
  SELECT
      job_id,
      posted_at,
      ingestion_timestamp,
      DATEDIFF(day, posted_at, ingestion_timestamp) as days_late,
      CASE
          WHEN DATEDIFF(day, posted_at, ingestion_timestamp) > 7 THEN 'VERY_LATE'
          WHEN DATEDIFF(day, posted_at, ingestion_timestamp) > 3 THEN 'LATE'
          ELSE 'ON_TIME'
      END as arrival_status
  FROM {{ ref('fact_job_posting') }}
  WHERE DATEDIFF(day, posted_at, ingestion_timestamp) > 1
  ORDER BY days_late DESC
  ```

### Acceptance Criteria
- [ ] 8 aggregation tables created
- [ ] All data quality tests pass
- [ ] No orphan records
- [ ] Salary ranges valid
- [ ] Reconciliation delta_status != 'ALERT'
- [ ] No orphan dimension keys

---

## Phase 7: Orchestration (Step Functions)

**Goal**: Create production orchestration with Step Functions.

### Tasks

- [ ] **7.1** Create Step Functions definition (with parallelism)

  **Cold Start Mitigation:**

  Redshift Serverless + Lambda VPC cold start can add ~2-3 min overhead:
  ```
  Lambda cold start (VPC): 10-30s
  Redshift wake from idle: 30-60s
  dbt compile: 30-60s
  ─────────────────────────────
  Total overhead: ~2-3 min (first run after idle)
  ```

  **Mitigation**: Add warm-up step that runs `dbt debug` to:
  1. Initialize Lambda VPC network interfaces
  2. Wake up Redshift Serverless
  3. Validate connection before pipeline starts

  **Execution Flow:**
  ```
  WarmupRedshift (dbt debug) ← NEW: Wakes Redshift + tests connection
      │
      ▼
  DbtSeed
      │
      ▼
  ┌───────────────────────────────────────┐
  │        DimensionsParallel             │
  │  ┌─────────────┐  ┌─────────────┐     │
  │  │ StaticDims  │  │ DynamicDims │     │  ← Parallel (independent)
  │  │ (seeds)     │  │ (company,   │     │
  │  │             │  │  location)  │     │
  │  └─────────────┘  └─────────────┘     │
  └───────────────────────────────────────┘
      │
      ▼
  DbtRunFacts (depends on all dims)
      │
      ▼
  ┌───────────────────────────────────────┐
  │        BridgesParallel                │
  │  ┌─────────────┐  ┌─────────────┐     │
  │  │ BridgesA    │  │ BridgesB    │     │  ← Parallel (independent)
  │  │ (skills,    │  │ (tools,     │     │
  │  │  industries)│  │  certs)     │     │
  │  └─────────────┘  └─────────────┘     │
  └───────────────────────────────────────┘
      │
      ▼
  DbtRunAggregations
      │
      ▼
  DbtTest
  ```

  ```json
  {
    "StartAt": "WarmupRedshift",
    "States": {
      "WarmupRedshift": {
        "Type": "Task",
        "Resource": "arn:aws:lambda:...:dbt-runner",
        "Parameters": {"command": "debug"},
        "TimeoutSeconds": 180,
        "Retry": [{
          "ErrorEquals": ["States.ALL"],
          "MaxAttempts": 2,
          "BackoffRate": 2
        }],
        "Next": "DbtSeed",
        "Comment": "Wakes up Redshift Serverless and tests connection"
      },
      "DbtSeed": {
        "Type": "Task",
        "Resource": "arn:aws:lambda:...:dbt-runner",
        "Parameters": {"command": "seed"},
        "Next": "DimensionsParallel"
      },
      "DimensionsParallel": {
        "Type": "Parallel",
        "Branches": [
          {
            "StartAt": "StaticDims",
            "States": {
              "StaticDims": {
                "Type": "Task",
                "Resource": "arn:aws:lambda:...:dbt-runner",
                "Parameters": {"command": "run", "select": "tag:dim_static"},
                "End": true
              }
            }
          },
          {
            "StartAt": "DynamicDims",
            "States": {
              "DynamicDims": {
                "Type": "Task",
                "Resource": "arn:aws:lambda:...:dbt-runner",
                "Parameters": {"command": "run", "select": "tag:dim_dynamic"},
                "End": true
              }
            }
          }
        ],
        "Next": "DbtRunFacts"
      },
      "DbtRunFacts": {
        "Type": "Task",
        "Resource": "arn:aws:lambda:...:dbt-runner",
        "Parameters": {"command": "run", "select": "tag:facts"},
        "Next": "BridgesParallel"
      },
      "BridgesParallel": {
        "Type": "Parallel",
        "Branches": [
          {
            "StartAt": "BridgesGroupA",
            "States": {
              "BridgesGroupA": {
                "Type": "Task",
                "Resource": "arn:aws:lambda:...:dbt-runner",
                "Parameters": {"command": "run", "select": "tag:bridge_group_a"},
                "End": true
              }
            }
          },
          {
            "StartAt": "BridgesGroupB",
            "States": {
              "BridgesGroupB": {
                "Type": "Task",
                "Resource": "arn:aws:lambda:...:dbt-runner",
                "Parameters": {"command": "run", "select": "tag:bridge_group_b"},
                "End": true
              }
            }
          }
        ],
        "Next": "DbtRunAggregations"
      },
      "DbtRunAggregations": {
        "Type": "Task",
        "Resource": "arn:aws:lambda:...:dbt-runner",
        "Parameters": {"command": "run", "select": "tag:aggregations"},
        "Next": "DbtTest"
      },
      "DbtTest": {
        "Type": "Task",
        "Resource": "arn:aws:lambda:...:dbt-runner",
        "Parameters": {"command": "test", "select": "tag:critical"},
        "Next": "Success"
      },
      "Success": {
        "Type": "Succeed"
      }
    }
  }
  ```

- [ ] **7.2** Create EventBridge schedule
  - Daily at 6 AM UTC
  - After Silver pipeline completes

- [ ] **7.3** Add error handling and retries
  ```json
  "Retry": [
    {
      "ErrorEquals": ["States.ALL"],
      "MaxAttempts": 2,
      "BackoffRate": 2
    }
  ],
  "Catch": [
    {
      "ErrorEquals": ["States.ALL"],
      "Next": "NotifyFailure"
    }
  ]
  ```

- [ ] **7.4** Create SNS notifications
  - Success notification
  - Failure notification with logs

- [ ] **7.5** Create basic CloudWatch alarms (detailed observability in Phase 9)

- [ ] **7.6** Create Terraform module
  ```
  infra/modules/gold_dbt/
  ├── step_function.tf
  ├── step_function_definition.json
  ├── eventbridge.tf
  ├── sns.tf
  └── cloudwatch.tf
  ```

### Acceptance Criteria
- [ ] Step Functions deployed
- [ ] Daily schedule working
- [ ] Notifications configured
- [ ] Dashboard created

---

## Phase 8: Documentation & Lineage

**Goal**: Generate and host dbt documentation with lineage graphs.

### dbt Docs Overview

dbt generates static HTML documentation including:
- **Lineage Graph**: Visual DAG of model dependencies
- **Model Details**: Descriptions, columns, tests
- **Source Freshness**: Data staleness indicators
- **Compiled SQL**: Actual queries executed

### Tasks

- [ ] **8.1** Add descriptions to all models
  ```yaml
  # models/facts/schema.yml
  models:
    - name: fact_job_posting
      description: |
        Central fact table containing one row per job posting.
        Grain: job_posting_id
        Source: SLV-LI, SLV-AI
      columns:
        - name: job_posting_key
          description: "Surrogate key (SK)"
        - name: salary_min_usd
          description: "Minimum salary converted to USD"
  ```

- [ ] **8.2** Generate dbt docs
  ```bash
  dbt docs generate
  # Creates: target/manifest.json, target/catalog.json, target/index.html
  ```

- [ ] **8.3** Configure S3 bucket for docs (bucket created in storage module)
  ```hcl
  # infra/modules/gold_dbt/docs_hosting.tf
  # Note: Bucket is created in storage module, referenced via variable

  resource "aws_s3_bucket_website_configuration" "dbt_docs" {
    bucket = var.dbt_docs_bucket_name
    index_document { suffix = "index.html" }
  }

  resource "aws_s3_bucket_policy" "dbt_docs" {
    bucket = var.dbt_docs_bucket_name
    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [{
        Effect    = "Allow"
        Principal = { AWS = aws_cloudfront_origin_access_identity.dbt_docs.iam_arn }
        Action    = "s3:GetObject"
        Resource  = "${var.dbt_docs_bucket_arn}/*"
      }]
    })
  }
  ```

- [ ] **8.4** Create CloudFront distribution with authentication

  **Authentication Options:**

  | Option | Complexity | Use Case |
  |--------|------------|----------|
  | CloudFront Functions (Basic Auth) | Low | Internal team, simple password |
  | Lambda@Edge + Cognito | Medium | SSO integration, user management |
  | AWS WAF + IP Whitelist | Low | Office/VPN access only |

  ```hcl
  # infra/modules/gold_dbt/docs_hosting.tf (continued)
  data "aws_s3_bucket" "dbt_docs" {
    bucket = var.dbt_docs_bucket_name
  }

  resource "aws_cloudfront_origin_access_identity" "dbt_docs" {
    comment = "OAI for ${var.project_name} dbt docs"
  }

  # Option 1: CloudFront Function for Basic Auth (simple, no extra cost)
  resource "aws_cloudfront_function" "basic_auth" {
    name    = "${var.project_name}-${var.environment}-docs-auth"
    runtime = "cloudfront-js-1.0"
    publish = true
    code    = <<-EOF
      function handler(event) {
        var request = event.request;
        var headers = request.headers;

        // Base64 encoded "user:password" - store in Secrets Manager in production
        var authString = "Basic " + "ZGJ0OmRidC1kb2NzLTIwMjQ="; // dbt:dbt-docs-2024

        if (!headers.authorization || headers.authorization.value !== authString) {
          return {
            statusCode: 401,
            statusDescription: 'Unauthorized',
            headers: {
              'www-authenticate': { value: 'Basic realm="dbt docs"' }
            }
          };
        }
        return request;
      }
    EOF
  }

  resource "aws_cloudfront_distribution" "dbt_docs" {
    origin {
      domain_name = data.aws_s3_bucket.dbt_docs.bucket_regional_domain_name
      origin_id   = "${var.project_name}-dbt-docs"
      s3_origin_config {
        origin_access_identity = aws_cloudfront_origin_access_identity.dbt_docs.cloudfront_access_identity_path
      }
    }

    enabled             = true
    default_root_object = "index.html"

    default_cache_behavior {
      allowed_methods        = ["GET", "HEAD"]
      cached_methods         = ["GET", "HEAD"]
      target_origin_id       = "${var.project_name}-dbt-docs"
      viewer_protocol_policy = "redirect-to-https"

      # Attach Basic Auth function
      function_association {
        event_type   = "viewer-request"
        function_arn = aws_cloudfront_function.basic_auth.arn
      }

      forwarded_values {
        query_string = false
        cookies { forward = "none" }
      }

      min_ttl     = 0
      default_ttl = 3600
      max_ttl     = 86400
    }

    restrictions {
      geo_restriction { restriction_type = "none" }
    }

    viewer_certificate {
      cloudfront_default_certificate = true
    }

    tags = {
      Project     = var.project_name
      Environment = var.environment
    }
  }
  ```

  **Alternative: Lambda@Edge with Cognito** (for SSO/enterprise auth)
  ```hcl
  # infra/modules/gold_dbt/docs_auth_cognito.tf (optional)

  resource "aws_cognito_user_pool" "dbt_docs" {
    name = "${var.project_name}-${var.environment}-dbt-docs"

    password_policy {
      minimum_length    = 12
      require_lowercase = true
      require_numbers   = true
      require_symbols   = true
      require_uppercase = true
    }
  }

  resource "aws_cognito_user_pool_client" "dbt_docs" {
    name         = "dbt-docs-client"
    user_pool_id = aws_cognito_user_pool.dbt_docs.id

    explicit_auth_flows = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]

    callback_urls = [
      "https://${aws_cloudfront_distribution.dbt_docs.domain_name}/callback"
    ]
  }

  # Lambda@Edge function for Cognito auth (deployed to us-east-1)
  # See: https://github.com/awslabs/cognito-at-edge
  ```

- [ ] **8.5** Add docs deploy to Step Functions
  ```json
  {
    "DbtDocsGenerate": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:dbt-runner",
      "Parameters": {"command": "docs generate"},
      "Next": "DeployDocs"
    },
    "DeployDocs": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:dbt-runner",
      "Parameters": {"command": "deploy-docs"},
      "Next": "Success"
    }
  }
  ```

- [ ] **8.6** Create docs deploy script in Lambda handler
  ```python
  # src/lambdas/dbt_runner/handler.py
  import os
  import boto3

  def deploy_docs():
      """Sync dbt docs to S3 (bucket from env var)"""
      s3 = boto3.client('s3')
      bucket = os.environ['DBT_DOCS_BUCKET']  # From Terraform

      docs_files = ['index.html', 'manifest.json', 'catalog.json']
      for f in docs_files:
          s3.upload_file(
              f'/tmp/dbt_gold/target/{f}',
              bucket,
              f,
              ExtraArgs={'ContentType': 'text/html' if f.endswith('.html') else 'application/json'}
          )
  ```

  ```hcl
  # infra/modules/gold_dbt/lambda.tf - Environment variables
  resource "aws_lambda_function" "dbt_runner" {
    function_name = "${var.project_name}-${var.environment}-dbt-runner"
    # ...

    environment {
      variables = {
        REDSHIFT_HOST     = aws_redshiftserverless_workgroup.gold.endpoint[0].address
        REDSHIFT_DATABASE = var.redshift_database_name
        DBT_DOCS_BUCKET   = var.dbt_docs_bucket_name
        SILVER_BUCKET     = var.silver_bucket_name
      }
    }
  }
  ```

- [ ] **8.7** Create README for dbt project

### Accessing the Lineage

| Method | URL | Access |
|--------|-----|--------|
| **CloudFront** | `https://d1234.cloudfront.net` | Basic Auth (CloudFront Function) |
| **Direct S3** | Pre-signed URLs (1hr expiry) | Private |
| **Local** | `dbt docs serve` | Development only |

> **Auth Options**: CloudFront Function (Basic Auth), Lambda@Edge + Cognito (SSO), or AWS WAF (IP whitelist). See Phase 8.4 for implementation.

### Lineage Graph Features

The dbt lineage graph shows:
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ source:         │────►│ stg_linkedin    │────►│ dim_company     │
│ silver.linkedin │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                │
                                ▼
                        ┌─────────────────┐
                        │ fact_job_posting│
                        └─────────────────┘
```

- Click any node to see: SQL, columns, tests, freshness
- Filter by tag: `tag:dimensions`, `tag:facts`
- Search models, columns, descriptions

### Acceptance Criteria
- [ ] All models have descriptions
- [ ] Docs generated successfully
- [ ] S3 bucket + CloudFront deployed
- [ ] Docs accessible via CloudFront URL
- [ ] Lineage graph renders correctly

---

## Phase 9: Observability & Alerting

**Goal**: Implement comprehensive monitoring, structured logging, and alerting strategy.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         OBSERVABILITY STACK                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Lambda Logs          dbt Artifacts         Redshift Metrics           │
│   (Structured JSON)    (run_results.json)    (RPU, Queries)             │
│         │                    │                     │                     │
│         ▼                    ▼                     ▼                     │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │                    CloudWatch Logs                                │  │
│   │  Log Groups:                                                      │  │
│   │  • /aws/lambda/dbt-runner                                        │  │
│   │  • /dbt/run-results                                              │  │
│   │  • /dbt/test-results                                             │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│                              │                                           │
│         ┌────────────────────┼────────────────────┐                     │
│         ▼                    ▼                    ▼                     │
│   ┌───────────┐        ┌───────────┐        ┌───────────┐              │
│   │ Metrics   │        │ Alarms    │        │ Dashboard │              │
│   │ Filters   │───────►│ (SNS)     │        │           │              │
│   └───────────┘        └───────────┘        └───────────┘              │
│                              │                                           │
│                              ▼                                           │
│                    ┌─────────────────┐                                  │
│                    │  SNS → Email/   │                                  │
│                    │  Slack/PagerDuty│                                  │
│                    └─────────────────┘                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Tasks

#### Structured Logging

- [ ] **9.1** Implement structured JSON logging in Lambda
  ```python
  # src/lambdas/dbt_runner/logger.py
  import json
  import logging
  from datetime import datetime

  class StructuredLogger:
      def __init__(self, context):
          self.logger = logging.getLogger()
          self.logger.setLevel(logging.INFO)
          self.context = {
              "request_id": context.aws_request_id,
              "function_name": context.function_name,
              "environment": os.environ.get("ENVIRONMENT", "dev")
          }

      def log(self, level: str, message: str, **kwargs):
          log_entry = {
              "timestamp": datetime.utcnow().isoformat(),
              "level": level,
              "message": message,
              **self.context,
              **kwargs
          }
          print(json.dumps(log_entry))

      def dbt_run_start(self, command: str, select: str = None):
          self.log("INFO", "dbt_run_started",
                   dbt_command=command,
                   dbt_select=select)

      def dbt_run_complete(self, command: str, duration_seconds: float,
                           models_success: int, models_error: int):
          self.log("INFO", "dbt_run_completed",
                   dbt_command=command,
                   duration_seconds=duration_seconds,
                   models_success=models_success,
                   models_error=models_error,
                   status="success" if models_error == 0 else "partial_failure")

      def dbt_run_failed(self, command: str, error: str):
          self.log("ERROR", "dbt_run_failed",
                   dbt_command=command,
                   error=error)

      def dbt_test_results(self, passed: int, failed: int, warnings: int):
          self.log("INFO", "dbt_test_results",
                   tests_passed=passed,
                   tests_failed=failed,
                   tests_warnings=warnings,
                   status="success" if failed == 0 else "failure")
  ```

- [ ] **9.2** Parse and log dbt run_results.json
  ```python
  # src/lambdas/dbt_runner/dbt_results.py
  import json

  def parse_run_results(results_path: str) -> dict:
      """Parse dbt run_results.json and extract metrics"""
      with open(results_path) as f:
          results = json.load(f)

      summary = {
          "elapsed_time": results.get("elapsed_time"),
          "models_total": len(results.get("results", [])),
          "models_success": 0,
          "models_error": 0,
          "models_skipped": 0,
          "errors": []
      }

      for result in results.get("results", []):
          status = result.get("status")
          if status == "success":
              summary["models_success"] += 1
          elif status == "error":
              summary["models_error"] += 1
              summary["errors"].append({
                  "model": result.get("unique_id"),
                  "message": result.get("message")
              })
          elif status == "skipped":
              summary["models_skipped"] += 1

      return summary
  ```

- [ ] **9.3** Log dbt artifacts to CloudWatch
  ```python
  # src/lambdas/dbt_runner/handler.py
  import boto3

  def log_dbt_artifacts(run_results: dict, logger: StructuredLogger):
      """Send dbt results to dedicated CloudWatch log group"""
      logs_client = boto3.client('logs')

      log_group = "/dbt/run-results"
      log_stream = f"{datetime.utcnow().strftime('%Y/%m/%d')}"

      logs_client.put_log_events(
          logGroupName=log_group,
          logStreamName=log_stream,
          logEvents=[{
              "timestamp": int(datetime.utcnow().timestamp() * 1000),
              "message": json.dumps(run_results)
          }]
      )
  ```

#### CloudWatch Metrics

- [ ] **9.4** Create custom CloudWatch metrics
  ```python
  # src/lambdas/dbt_runner/metrics.py
  import boto3

  def publish_dbt_metrics(run_results: dict, namespace: str = "dbt/gold"):
      cloudwatch = boto3.client('cloudwatch')

      metrics = [
          {
              "MetricName": "ModelsSuccess",
              "Value": run_results["models_success"],
              "Unit": "Count"
          },
          {
              "MetricName": "ModelsError",
              "Value": run_results["models_error"],
              "Unit": "Count"
          },
          {
              "MetricName": "RunDuration",
              "Value": run_results["elapsed_time"],
              "Unit": "Seconds"
          },
          {
              "MetricName": "TestsPassed",
              "Value": run_results.get("tests_passed", 0),
              "Unit": "Count"
          },
          {
              "MetricName": "TestsFailed",
              "Value": run_results.get("tests_failed", 0),
              "Unit": "Count"
          }
      ]

      cloudwatch.put_metric_data(
          Namespace=namespace,
          MetricData=metrics
      )
  ```

- [ ] **9.5** Create Terraform for CloudWatch Log Groups
  ```hcl
  # infra/modules/gold_dbt/observability.tf

  # Log Groups
  resource "aws_cloudwatch_log_group" "dbt_runner" {
    name              = "/aws/lambda/${var.project_name}-${var.environment}-dbt-runner"
    retention_in_days = 30

    tags = {
      Project     = var.project_name
      Environment = var.environment
    }
  }

  resource "aws_cloudwatch_log_group" "dbt_run_results" {
    name              = "/dbt/run-results"
    retention_in_days = 90

    tags = {
      Project     = var.project_name
      Environment = var.environment
    }
  }

  resource "aws_cloudwatch_log_group" "dbt_test_results" {
    name              = "/dbt/test-results"
    retention_in_days = 90

    tags = {
      Project     = var.project_name
      Environment = var.environment
    }
  }
  ```

#### CloudWatch Alarms

- [ ] **9.6** Create alerting alarms
  ```hcl
  # infra/modules/gold_dbt/alarms.tf

  # SNS Topic for alerts
  resource "aws_sns_topic" "dbt_alerts" {
    name = "${var.project_name}-${var.environment}-dbt-alerts"
  }

  # Alarm: dbt run failures
  resource "aws_cloudwatch_metric_alarm" "dbt_run_failures" {
    alarm_name          = "${var.project_name}-${var.environment}-dbt-run-failures"
    comparison_operator = "GreaterThanThreshold"
    evaluation_periods  = 1
    metric_name         = "ModelsError"
    namespace           = "dbt/gold"
    period              = 300
    statistic           = "Sum"
    threshold           = 0
    alarm_description   = "dbt models failed during run"
    alarm_actions       = [aws_sns_topic.dbt_alerts.arn]

    tags = {
      Project     = var.project_name
      Environment = var.environment
    }
  }

  # Alarm: dbt test failures
  resource "aws_cloudwatch_metric_alarm" "dbt_test_failures" {
    alarm_name          = "${var.project_name}-${var.environment}-dbt-test-failures"
    comparison_operator = "GreaterThanThreshold"
    evaluation_periods  = 1
    metric_name         = "TestsFailed"
    namespace           = "dbt/gold"
    period              = 300
    statistic           = "Sum"
    threshold           = 0
    alarm_description   = "dbt tests failed"
    alarm_actions       = [aws_sns_topic.dbt_alerts.arn]

    tags = {
      Project     = var.project_name
      Environment = var.environment
    }
  }

  # Alarm: Long running dbt job
  resource "aws_cloudwatch_metric_alarm" "dbt_long_running" {
    alarm_name          = "${var.project_name}-${var.environment}-dbt-long-running"
    comparison_operator = "GreaterThanThreshold"
    evaluation_periods  = 1
    metric_name         = "RunDuration"
    namespace           = "dbt/gold"
    period              = 300
    statistic           = "Maximum"
    threshold           = 600  # 10 minutes
    alarm_description   = "dbt run taking longer than expected"
    alarm_actions       = [aws_sns_topic.dbt_alerts.arn]

    tags = {
      Project     = var.project_name
      Environment = var.environment
    }
  }

  # Alarm: Lambda errors
  resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
    alarm_name          = "${var.project_name}-${var.environment}-dbt-lambda-errors"
    comparison_operator = "GreaterThanThreshold"
    evaluation_periods  = 1
    metric_name         = "Errors"
    namespace           = "AWS/Lambda"
    period              = 300
    statistic           = "Sum"
    threshold           = 0
    alarm_description   = "dbt Lambda function errors"
    alarm_actions       = [aws_sns_topic.dbt_alerts.arn]

    dimensions = {
      FunctionName = aws_lambda_function.dbt_runner.function_name
    }

    tags = {
      Project     = var.project_name
      Environment = var.environment
    }
  }

  # Alarm: Redshift RPU cost spike
  resource "aws_cloudwatch_metric_alarm" "redshift_rpu_spike" {
    alarm_name          = "${var.project_name}-${var.environment}-redshift-rpu-spike"
    comparison_operator = "GreaterThanThreshold"
    evaluation_periods  = 3
    metric_name         = "ComputeCapacity"
    namespace           = "AWS/Redshift-Serverless"
    period              = 300
    statistic           = "Average"
    threshold           = 32  # Alert if RPU exceeds 32 (4x base)
    alarm_description   = "Redshift Serverless RPU usage spike"
    alarm_actions       = [aws_sns_topic.dbt_alerts.arn]

    dimensions = {
      Workgroup = aws_redshiftserverless_workgroup.gold.workgroup_name
    }

    tags = {
      Project     = var.project_name
      Environment = var.environment
    }
  }

  # Alarm: Step Function failures
  resource "aws_cloudwatch_metric_alarm" "step_function_failures" {
    alarm_name          = "${var.project_name}-${var.environment}-dbt-pipeline-failures"
    comparison_operator = "GreaterThanThreshold"
    evaluation_periods  = 1
    metric_name         = "ExecutionsFailed"
    namespace           = "AWS/States"
    period              = 300
    statistic           = "Sum"
    threshold           = 0
    alarm_description   = "dbt pipeline Step Function failed"
    alarm_actions       = [aws_sns_topic.dbt_alerts.arn]

    dimensions = {
      StateMachineArn = aws_sfn_state_machine.dbt_pipeline.arn
    }

    tags = {
      Project     = var.project_name
      Environment = var.environment
    }
  }
  ```

#### CloudWatch Dashboard

- [ ] **9.7** Create observability dashboard
  ```hcl
  # infra/modules/gold_dbt/dashboard.tf

  resource "aws_cloudwatch_dashboard" "dbt_gold" {
    dashboard_name = "${var.project_name}-${var.environment}-dbt-gold"

    dashboard_body = jsonencode({
      widgets = [
        # Row 1: Pipeline Health
        {
          type   = "metric"
          x      = 0
          y      = 0
          width  = 6
          height = 6
          properties = {
            title  = "Pipeline Executions"
            region = data.aws_region.current.name
            metrics = [
              ["AWS/States", "ExecutionsSucceeded", "StateMachineArn", aws_sfn_state_machine.dbt_pipeline.arn, { color = "#2ca02c" }],
              ["AWS/States", "ExecutionsFailed", "StateMachineArn", aws_sfn_state_machine.dbt_pipeline.arn, { color = "#d62728" }]
            ]
            period = 86400
            stat   = "Sum"
          }
        },
        {
          type   = "metric"
          x      = 6
          y      = 0
          width  = 6
          height = 6
          properties = {
            title  = "dbt Models Status"
            region = data.aws_region.current.name
            metrics = [
              ["dbt/gold", "ModelsSuccess", { color = "#2ca02c" }],
              ["dbt/gold", "ModelsError", { color = "#d62728" }]
            ]
            period = 86400
            stat   = "Sum"
          }
        },
        {
          type   = "metric"
          x      = 12
          y      = 0
          width  = 6
          height = 6
          properties = {
            title  = "dbt Tests Status"
            region = data.aws_region.current.name
            metrics = [
              ["dbt/gold", "TestsPassed", { color = "#2ca02c" }],
              ["dbt/gold", "TestsFailed", { color = "#d62728" }]
            ]
            period = 86400
            stat   = "Sum"
          }
        },
        {
          type   = "metric"
          x      = 18
          y      = 0
          width  = 6
          height = 6
          properties = {
            title  = "Run Duration (seconds)"
            region = data.aws_region.current.name
            metrics = [
              ["dbt/gold", "RunDuration"]
            ]
            period = 86400
            stat   = "Average"
          }
        },
        # Row 2: Redshift Metrics
        {
          type   = "metric"
          x      = 0
          y      = 6
          width  = 8
          height = 6
          properties = {
            title  = "Redshift Serverless RPU"
            region = data.aws_region.current.name
            metrics = [
              ["AWS/Redshift-Serverless", "ComputeCapacity", "Workgroup", aws_redshiftserverless_workgroup.gold.workgroup_name]
            ]
            period = 300
            stat   = "Average"
          }
        },
        {
          type   = "metric"
          x      = 8
          y      = 6
          width  = 8
          height = 6
          properties = {
            title  = "Redshift Query Duration"
            region = data.aws_region.current.name
            metrics = [
              ["AWS/Redshift-Serverless", "QueryDuration", "Workgroup", aws_redshiftserverless_workgroup.gold.workgroup_name]
            ]
            period = 300
            stat   = "Average"
          }
        },
        {
          type   = "metric"
          x      = 16
          y      = 6
          width  = 8
          height = 6
          properties = {
            title  = "Lambda Invocations & Errors"
            region = data.aws_region.current.name
            metrics = [
              ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.dbt_runner.function_name, { color = "#1f77b4" }],
              ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.dbt_runner.function_name, { color = "#d62728" }]
            ]
            period = 86400
            stat   = "Sum"
          }
        },
        # Row 3: Logs
        {
          type   = "log"
          x      = 0
          y      = 12
          width  = 24
          height = 6
          properties = {
            title  = "Recent dbt Errors"
            region = data.aws_region.current.name
            query  = "SOURCE '/aws/lambda/${aws_lambda_function.dbt_runner.function_name}' | filter level = 'ERROR' | sort @timestamp desc | limit 20"
          }
        }
      ]
    })
  }
  ```

#### Metric Filters (Log-based Metrics)

- [ ] **9.8** Create CloudWatch metric filters
  ```hcl
  # infra/modules/gold_dbt/metric_filters.tf

  # Metric filter for dbt errors in logs
  resource "aws_cloudwatch_log_metric_filter" "dbt_errors" {
    name           = "${var.project_name}-${var.environment}-dbt-errors"
    pattern        = "{ $.level = \"ERROR\" }"
    log_group_name = aws_cloudwatch_log_group.dbt_runner.name

    metric_transformation {
      name          = "DbtLogErrors"
      namespace     = "dbt/gold"
      value         = "1"
      default_value = "0"
    }
  }

  # Metric filter for dbt warnings
  resource "aws_cloudwatch_log_metric_filter" "dbt_warnings" {
    name           = "${var.project_name}-${var.environment}-dbt-warnings"
    pattern        = "{ $.level = \"WARNING\" }"
    log_group_name = aws_cloudwatch_log_group.dbt_runner.name

    metric_transformation {
      name          = "DbtLogWarnings"
      namespace     = "dbt/gold"
      value         = "1"
      default_value = "0"
    }
  }

  # Metric filter for model failures
  resource "aws_cloudwatch_log_metric_filter" "model_failures" {
    name           = "${var.project_name}-${var.environment}-model-failures"
    pattern        = "{ $.message = \"dbt_run_completed\" && $.models_error > 0 }"
    log_group_name = aws_cloudwatch_log_group.dbt_runner.name

    metric_transformation {
      name          = "ModelFailures"
      namespace     = "dbt/gold"
      value         = "$.models_error"
      default_value = "0"
    }
  }
  ```

#### Data Freshness Monitoring

- [ ] **9.9** Add dbt source freshness checks
  ```yaml
  # models/staging/sources.yml
  sources:
    - name: silver
      database: analytics
      schema: silver_external
      freshness:
        warn_after: {count: 24, period: hour}
        error_after: {count: 48, period: hour}
      loaded_at_field: scraped_at  # or partition date
      tables:
        - name: linkedin
          freshness:
            warn_after: {count: 12, period: hour}
            error_after: {count: 24, period: hour}
        - name: ai_enrichment
          freshness:
            warn_after: {count: 24, period: hour}
            error_after: {count: 48, period: hour}
  ```

- [ ] **9.10** Add freshness check to Step Functions
  ```json
  {
    "DbtSourceFreshness": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:dbt-runner",
      "Parameters": {"command": "source freshness"},
      "Next": "DbtSeed",
      "Catch": [{
        "ErrorEquals": ["States.ALL"],
        "Next": "NotifyStaleData"
      }]
    }
  }
  ```

#### SNS Notifications

- [ ] **9.11** Configure SNS subscriptions
  ```hcl
  # infra/modules/gold_dbt/notifications.tf

  variable "alert_email" {
    description = "Email for dbt alerts"
    type        = string
  }

  resource "aws_sns_topic_subscription" "email" {
    topic_arn = aws_sns_topic.dbt_alerts.arn
    protocol  = "email"
    endpoint  = var.alert_email
  }

  # Optional: Slack webhook via Lambda
  # resource "aws_sns_topic_subscription" "slack" {
  #   topic_arn = aws_sns_topic.dbt_alerts.arn
  #   protocol  = "lambda"
  #   endpoint  = aws_lambda_function.slack_notifier.arn
  # }
  ```

### Alerting Matrix

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| dbt Run Failed | ModelsError > 0 | HIGH | Email + Slack |
| dbt Tests Failed | TestsFailed > 0 | HIGH | Email + Slack |
| Long Running Job | Duration > 10 min | MEDIUM | Email |
| Lambda Error | Errors > 0 | HIGH | Email + Slack |
| RPU Spike | RPU > 32 | MEDIUM | Email |
| Pipeline Failed | ExecutionsFailed > 0 | CRITICAL | Email + Slack + PagerDuty |
| Stale Data | Freshness > 24h | HIGH | Email |

### Acceptance Criteria
- [ ] Structured JSON logging implemented
- [ ] CloudWatch Log Groups created with retention
- [ ] Custom dbt metrics published to CloudWatch
- [ ] 6 CloudWatch alarms configured
- [ ] Dashboard with pipeline health metrics
- [ ] SNS notifications configured
- [ ] Source freshness monitoring enabled

---

## Cost Estimate

| Component | Monthly Cost | Notes |
|-----------|--------------|-------|
| Redshift Serverless (RPU) | ~$20-40 | 8 RPU base × $0.36/hr × ~1-2hr/day usage |
| Lambda (dbt runner) | ~$1 | |
| Lambda Layers (storage) | ~$0.50 | |
| S3 (staging/temp) | ~$2 | Minimal - data lives in Redshift |
| S3 (dbt docs) | ~$0.10 | ~5MB static files |
| CloudFront (docs) | ~$1 | Low traffic, cached + Basic Auth |
| Step Functions | ~$0.50 | |
| CloudWatch (logs + metrics) | ~$3 | Logs, custom metrics, dashboard |
| CloudWatch Alarms | ~$0.50 | 6 alarms × $0.10/alarm |
| SNS (alerting) | ~$0.10 | Low volume notifications |
| Secrets Manager | ~$0.40 | 1 secret × $0.40/secret/month |
| VPC Endpoints | ~$14 | CloudWatch Logs + Secrets Manager (S3 Gateway is free) |
| **Total** | **~$43-63** | |

> **Note**: Redshift Serverless charges $0.36/RPU-hour. With 8 RPU minimum and
> ~1-2 hours of daily dbt runs, expect ~$20-40/month for compute.
> Idle time = $0 (unlike provisioned clusters).

> **VPC Note**: NAT Gateway (~$32/month) is NOT required. Lambda accesses:
> - Redshift: Same VPC (private subnet)
> - S3: Gateway Endpoint (free)
> - CloudWatch: Interface Endpoint (~$7/month)
> - Secrets Manager: Interface Endpoint (~$7/month) - REQUIRED for credentials
> - dbt packages: Pre-bundled in Lambda Layer (no runtime downloads)

---

## Timeline Estimate

| Phase | Effort | Dependency |
|-------|--------|------------|
| Phase 1: Project Setup | 1 day | - |
| Phase 2: Lambda Layer | 1-2 days | Phase 1 |
| Phase 3: Staging Models | 1 day | Phase 2 |
| Phase 4: Dimensions | 3-4 days | Phase 3 |
| Phase 5: Facts & Bridges | 2-3 days | Phase 4 |
| Phase 6: Aggregations | 1-2 days | Phase 5 |
| Phase 7: Orchestration | 1 day | Phase 6 |
| Phase 8: Documentation | 0.5 day | Phase 7 |
| Phase 9: Observability | 1 day | Phase 7 |
| **Total** | **~12-15 days** | |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Lambda 15 min timeout | High | Split into multiple invocations by tag |
| Redshift Serverless cost spike | Medium | Set usage limits, monitor RPU-hours |
| VPC connectivity issues | Medium | Proper security groups, VPC endpoints |
| Cold start delays | Low | Use provisioned concurrency if needed |
| dbt version conflicts | Medium | Pin versions in requirements |
| Spectrum query performance | Medium | Filter early, limit scanned data |
| Large dimension tables | Medium | Use incremental materialization |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Pipeline success rate | > 99% |
| Full run duration | < 10 min |
| Redshift RPU cost per run | < $1 (~2 RPU-hours) |
| Test coverage | 100% of models |

---

## References

- [gold-layer-modeling.md](./gold-layer-modeling.md) - Dimensional model specification
- [silver-layer-schema.md](./silver-layer-schema.md) - Source schema documentation
- [dbt-redshift setup](https://docs.getdbt.com/docs/core/connect-data-platform/redshift-setup) - Official adapter docs
- [Redshift Serverless](https://docs.aws.amazon.com/redshift/latest/mgmt/serverless-whatis.html) - AWS documentation
- [Redshift Spectrum](https://docs.aws.amazon.com/redshift/latest/dg/c-using-spectrum.html) - External tables (S3)
- [dbt best practices](https://docs.getdbt.com/best-practices)
