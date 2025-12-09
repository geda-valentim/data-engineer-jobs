# Data Engineer Jobs Pipeline

> **Using data engineering to find jobs for data engineers** 🔄

A fully automated data pipeline that scrapes, processes, and analyzes Data Engineer job postings from LinkedIn to provide insights on skills, salaries, seniority levels, and geographic trends.

## 📖 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Usage](#usage)
- [Data Pipeline](#data-pipeline)
  - [Ingestion Flow](#ingestion-flow-bronze)
  - [Transformation](#transformation-silver)
  - [AI Enrichment](#ai-enrichment-silver-ai)
- [Documentation](#documentation)
- [Roadmap](#roadmap)
- [Contributing](#contributing)

## Overview

This project implements a complete data engineering pipeline to analyze the Data Engineer job market using real-time data from LinkedIn. The goal is to understand:

- **Skills demand**: Which technologies and tools are most requested
- **Salary trends**: Compensation distributions by seniority and location
- **Geographic patterns**: Where the best opportunities are located
- **Career pathways**: How skills and requirements vary across seniority levels

### What's Currently Running

✅ **Automated hourly ingestion** via EventBridge + SQS

✅ **Bronze layer**: Raw JSONL data partitioned by date/hour in S3

✅ **Silver layer**: Cleaned Parquet data with normalized schema

✅ **Skills Detection**: Automatic extraction of 150+ tech skills from job descriptions

✅ **AI Enrichment**: LLM-powered metadata extraction (salary inference, seniority, visa sponsorship, red flags)

✅ **Multi-Model Validation**: Consensus-based quality assurance across 6+ LLM models

✅ **Glue ETL**: PySpark job for Bronze → Silver transformation

✅ **Backfill Support**: Fan-out Lambda for bulk region/work-type ingestion

✅ **Infrastructure as Code**: Complete Terraform setup for AWS

## Architecture

The pipeline follows the **Medallion Architecture** pattern:

```
┌─────────────────┐     ┌─────────────────┐
│   LinkedIn      │     │  Backfill       │
│  (Bright Data)  │     │  Fan-out Lambda │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐      ┌──────────────────┐
│  EventBridge    │─────▶│      SQS         │◀── Manual triggers
│  (Hourly Cron)  │      │  Ingestion Queue │
└─────────────────┘      └────────┬─────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐      ┌──────────────────┐
│   Dispatcher    │─────▶│  Queue Consumer  │
│    Lambda       │      │     Lambda       │
└─────────────────┘      └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  Step Functions  │
                         │   Orchestration  │
                         └────────┬─────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              ┌──────────┐  ┌──────────┐  ┌──────────┐
              │ Lambda 1 │  │ Lambda 2 │  │ Lambda 3 │
              │ Trigger  │  │  Check   │  │  Save    │
              │ Snapshot │  │  Status  │  │  to S3   │
              └──────────┘  └──────────┘  └────┬─────┘
                                               │
                                               ▼
                                         ┌──────────┐
                                         │  Bronze  │
                                         │   (S3)   │
                                         │   JSONL  │
                                         └────┬─────┘
                                              │
                            AWS Glue ETL (PySpark + Skills Detection)
                                              │
                                              ▼
                                         ┌──────────┐
                                         │  Silver  │
                                         │   (S3)   │
                                         │  Parquet │
                                         └────┬─────┘
                                              │
                            Lambda + Bedrock (LLM Enrichment)
                              Pass 1 → Pass 2 → Pass 3
                                              │
                                              ▼
                                       ┌────────────┐
                                       │ Silver-AI  │
                                       │    (S3)    │
                                       │  +141 cols │
                                       └─────┬──────┘
                                             │
                                    [Planned] Glue ETL
                                             │
                                             ▼
                                         ┌──────────┐
                                         │   Gold   │
                                         │   (S3)   │
                                         │ Analytics│
                                         └──────────┘
```

### Data Layers

| Layer | Format | Description | Partitioning |
|-------|--------|-------------|--------------|
| **Bronze** | JSONL | Raw data from LinkedIn API | `year/month/day/hour/` |
| **Silver** | Parquet | Cleaned, typed, normalized | `year/month/day/hour/` |
| **Silver-AI** | Parquet | LLM-enriched with 141 new columns | `year/month/day/hour/` |
| **Gold** | Parquet | Analytics tables, aggregations | Business-specific |

## Tech Stack

### Infrastructure
- **AWS S3**: Data lake storage (Bronze, Silver, Silver-AI, Gold layers)
- **AWS SQS**: Message queue for ingestion throttling and backfill
- **AWS Glue**: Serverless ETL (PySpark 4.0)
- **AWS Lambda**: Ingestion orchestration (Python 3.12)
- **AWS Bedrock**: LLM inference (6+ models for AI enrichment)
- **AWS EventBridge**: Scheduling and event routing
- **AWS Step Functions**: Workflow orchestration
- **AWS DynamoDB**: Ingestion sources configuration
- **AWS IAM**: Access control and security
- **Terraform**: Infrastructure as Code

### Data Processing
- **PySpark**: Distributed data transformation
- **Pandas**: Data manipulation in Lambdas
- **Bright Data**: LinkedIn scraping API

### Development
- **Python 3.13**: Primary programming language
- **Git**: Version control

## Project Structure

```
data-engineer-jobs/
├── infra/                          # Terraform infrastructure
│   ├── environments/
│   │   └── dev/                   # Development environment
│   │       ├── main.tf            # Module composition
│   │       ├── lambda_layer.tf    # Python dependencies layer
│   │       └── iam.tf             # IAM roles and policies
│   └── modules/
│       ├── storage/               # S3 buckets (Bronze/Silver/Gold)
│       ├── ingestion/             # Lambdas, Glue, EventBridge
│       ├── api-gateway/           # [Planned] REST API
│       └── monitoring/            # [Planned] CloudWatch dashboards
│
├── src/
│   ├── lambdas/
│   │   ├── data_extractor/
│   │   │   └── linkedin/
│   │   │       ├── config/
│   │   │       │   └── linkedin_geo_ids_flat.json  # Region configs
│   │   │       └── job_listing/
│   │   │           └── bright_data/
│   │   │               ├── trigger.py       # Trigger snapshot
│   │   │               ├── check_status.py  # Check completion
│   │   │               └── save_to_s3.py    # Save to Bronze
│   │   ├── queue_consumer/
│   │   │   └── handler.py           # SQS → Step Functions
│   │   └── backfill_fanout/
│   │       └── handler.py           # Bulk region ingestion
│   │
│   ├── glue_jobs/
│   │   ├── bronze_to_silver.py    # Bronze → Silver ETL
│   │   └── silver_to_gold.py      # [Planned] Silver → Gold
│   │
│   ├── lambdas/ai_enrichment/
│   │   └── enrich_partition/
│   │       ├── handler.py         # Main Lambda handler
│   │       ├── bedrock_client.py  # AWS Bedrock wrapper
│   │       ├── prompts/           # Pass 1/2/3 prompt templates
│   │       ├── flatteners/        # JSON → flat columns
│   │       └── parsers/           # JSON parsing & validation
│   │
│   ├── evaluation/                # Multi-model consensus evaluation
│   │   ├── evaluator.py           # Model comparison logic
│   │   ├── consensus.py           # Inter-model agreement
│   │   └── report.py              # Markdown report generation
│   │
│   ├── skills_detection/
│   │   ├── config/
│   │   │   ├── skills_catalog.yaml  # 150+ skills with variations
│   │   │   └── families/            # Skill families (17 files)
│   │   └── detector.py              # Skills extraction logic
│   │
│   ├── scheduler/
│   │   └── ingestion_dispatcher.py # DynamoDB → SQS dispatcher
│   │
│   └── shared/                     # Common utilities
│
├── docs/
│   ├── silver_schema.md           # Silver layer data schema
│   ├── gold_features_metrics.md   # Gold layer design
│   ├── bright-data.md             # Bright Data integration
│   ├── skills_detection_plan.md   # Skills extraction strategy
│   ├── ai-enrichment-architecture.md  # AI pipeline architecture
│   └── planning/ai-enrichment/    # AI enrichment specs & schemas
│
├── scripts/ai-enrichment/         # AI enrichment testing scripts
│   ├── test_pass1.py              # Pass 1 extraction tests
│   ├── test_pass2.py              # Pass 2 inference tests
│   ├── test_pass3.py              # Pass 3 analysis tests
│   └── test_multiple_models.py    # Multi-model comparison
│
├── reports/                       # Model evaluation reports
│
└── README.md
```

## Prerequisites

- **AWS Account** with appropriate permissions
- **Terraform** >= 1.0
- **AWS CLI** configured with credentials
- **Bright Data Account** with API access
- **Python** 3.13+ (for local development)

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/geda-valentim/data-engineer-jobs.git
cd data-engineer-jobs
```

### 2. Configure AWS Credentials

```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, and default region
```

### 3. Store Bright Data API Key in AWS SSM

```bash
aws ssm put-parameter \
  --name "/data-engineer-jobs/dev/brightdata/api-key" \
  --value "YOUR_BRIGHTDATA_API_KEY" \
  --type "SecureString" \
  --region us-east-1
```

### 4. Initialize Terraform

```bash
cd infra/environments/dev
terraform init
```

### 5. Review and Apply Infrastructure

```bash
# Review the execution plan
terraform plan

# Apply the infrastructure
terraform apply
```

This will create:
- 5 S3 buckets (Bronze, Silver, Gold, Glue temp, Glue scripts)
- 6 Lambda functions with Python dependencies layer
- 1 SQS queue + DLQ for ingestion throttling
- 1 DynamoDB table for ingestion sources
- 1 Glue ETL job (Bronze → Silver with Skills Detection)
- EventBridge rule for hourly execution
- Step Functions state machine
- IAM roles and policies
- CloudWatch Log Groups

### 6. Verify Deployment

```bash
# Check S3 buckets
aws s3 ls | grep data-engineer-jobs

# Check Lambda functions
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `data-engineer-jobs`)].FunctionName'

# Check Glue jobs
aws glue list-jobs --query 'JobNames[?starts_with(@, `data-engineer-jobs`)]'
```

## Usage

### Manual Trigger

To manually trigger the ingestion pipeline:

**Option 1: EventBridge Console**
1. Go to AWS EventBridge Console
2. Select "Rules" → `data-engineer-jobs-ingestion-hourly`
3. Click "Send test event"

**Option 2: AWS CLI**
```bash
aws lambda invoke \
  --function-name data-engineer-jobs-trigger-snapshot \
  --payload '{}' \
  response.json
```

### View Logs

**Lambda Logs:**
```bash
aws logs tail /aws/lambda/data-engineer-jobs-trigger-snapshot --follow
```

**Glue Job Logs:**
```bash
aws logs tail /aws-glue/jobs/output --follow
```

### Query Data

**Bronze Layer (Raw JSON):**
```bash
aws s3 ls s3://data-engineer-jobs-bronze/linkedin/jobs/
aws s3 cp s3://data-engineer-jobs-bronze/linkedin/jobs/year=2024/month=12/day=03/hour=10/snapshot_123.jsonl -
```

**Silver Layer (Parquet):**
```bash
aws s3 ls s3://data-engineer-jobs-silver/job_postings/
```

Use AWS Athena, Spark, or any Parquet-compatible tool to query:
```python
import pandas as pd

# Read Silver data
df = pd.read_parquet('s3://data-engineer-jobs-silver/job_postings/')
print(df.head())
```

## Data Pipeline

### Ingestion Flow (Bronze)

1. **EventBridge** triggers Dispatcher Lambda hourly (`cron(0 * * * ? *)`)
2. **Dispatcher** reads enabled sources from DynamoDB and sends to SQS
3. **Queue Consumer** Lambda picks messages from SQS (batch_size=1)
4. **Step Functions** orchestrates the ingestion workflow:
   - **Lambda 1** (`trigger.py`): Initiates Bright Data snapshot
   - **Lambda 2** (`check_status.py`): Polls until snapshot completes
   - **Lambda 3** (`save_to_s3.py`): Downloads and saves JSONL to Bronze S3
5. Path: `s3://bronze/linkedin/jobs/year=YYYY/month=MM/day=DD/hour=HH/`

#### Backfill Support

For bulk ingestion of multiple regions/work-types:

```bash
aws lambda invoke \
  --function-name data-engineer-jobs-backfill-fanout \
  --payload '{"region_groups": ["usa_states", "latin_america"]}' \
  response.json
```

The fan-out Lambda reads `linkedin_geo_ids_flat.json` and sends messages to SQS for each location × work_type combination, respecting throttling via SQS visibility timeout.

### Transformation (Silver)

AWS Glue Job (`bronze_to_silver.py`) runs PySpark to:

- ✅ **Load** raw JSONL from Bronze
- ✅ **Clean** and cast data types
- ✅ **Normalize** dates, salaries, locations
- ✅ **Extract** plain text from HTML descriptions
- ✅ **Detect Skills** from job descriptions (150+ technologies)
- ✅ **Remove** duplicates (planned)
- ✅ **Write** Parquet to Silver with Snappy compression
- ✅ **Partition** by `year/month/day/hour`

#### Skills Detection

The pipeline automatically extracts technical skills from job descriptions using a curated catalog of 150+ technologies organized in 17 families:

| Family | Examples |
|--------|----------|
| Cloud Platforms | AWS, Azure, GCP, Databricks |
| Programming | Python, SQL, Scala, Java |
| Data Processing | Spark, Kafka, Airflow |
| Databases | PostgreSQL, MongoDB, Redis |
| BI Tools | Power BI, Tableau, Looker |
| DevOps | Docker, Kubernetes, Terraform |

Skills are matched using canonical names and variations (e.g., "AWS" matches "Amazon Web Services", "aws", "Amazon AWS").

### AI Enrichment (Silver-AI)

The pipeline uses **LLMs via AWS Bedrock** to extract structured metadata from job descriptions using a **3-pass cascading context architecture**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Silver (Parquet) ──► Pass 1 ──► Pass 2 ──► Pass 3 ──► Silver-AI (Parquet)  │
│                       Extract    Infer      Analyze                          │
│                       Facts      Context    Signals                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Three-Pass Architecture

| Pass | Purpose | Examples | Confidence |
|------|---------|----------|------------|
| **Pass 1: Extraction** | Extract explicit facts from text | Salary, visa text, work model, skills mentioned | N/A (facts) |
| **Pass 2: Inference** | Normalize and infer based on Pass 1 | Seniority level, primary cloud, geo restriction, H1B friendly | 0.0-1.0 |
| **Pass 3: Analysis** | Complex analysis using Pass 1+2 | Data maturity, scope creep score, red flags, tech culture | 0.0-1.0 |

#### Available Models (AWS Bedrock)

| Model | Bedrock ID | Input/1M | Output/1M |
|-------|------------|----------|-----------|
| OpenAI GPT-OSS 120B | `openai.gpt-oss-120b-1:0` | $0.15 | $0.60 |
| MiniMax-M2 | `minimax.minimax-m2` | $0.30 | $1.20 |
| Qwen3 235B | `qwen.qwen3-vl-235b-a22b` | $0.22 | $0.88 |
| Gemma 3 27B | `google.gemma-3-27b-it` | $0.23 | $0.38 |
| DeepSeek R1 | `deepseek.r1-v1:0` | $1.35 | $5.40 |
| Mistral Large 3 | `mistral.mistral-large-3-675b-instruct` | $2.00 | $6.00 |

#### Multi-Model Consensus Validation

Before promoting data to Gold, the pipeline validates enrichment quality using **inter-model consensus**:

```bash
# Run multi-model evaluation
python scripts/evaluate_models.py <job_id> --output reports/
```

**Consensus Results (10 jobs sample):**
- Pass 1 (Extraction): **88.1%** consensus
- Pass 2 (Inference): **93.2%** consensus
- Pass 3 (Analysis): **62.8%** consensus (subjective by nature)

#### Output Schema (141 new columns)

| Category | Prefix | Columns | Examples |
|----------|--------|---------|----------|
| Extraction | `ext_` | 57 | `ext_salary_disclosed`, `ext_visa_sponsorship_stated` |
| Inference | `inf_` | 36 | `inf_seniority_level`, `inf_primary_cloud`, `inf_h1b_friendly` |
| Analysis | `anl_` | 48 | `anl_data_maturity_level`, `anl_scope_creep_score`, `anl_red_flags` |

#### Local Testing

```bash
# Test individual passes
python scripts/ai-enrichment/test_enrichment_local.py --pass1
python scripts/ai-enrichment/test_enrichment_local.py --pass2
python scripts/ai-enrichment/test_enrichment_local.py --pass3

# Test with multiple models
python scripts/ai-enrichment/test_multiple_models.py --use-s3 --limit 5 --models minimax openai
```

#### Cost Estimation

| Scenario | Jobs | Estimated Cost |
|----------|------|----------------|
| Initial load | 20,000 | ~$25 |
| Weekly batch | 5,000 | ~$6 |
| Monthly | 20,000 | ~$25 |

See [docs/ai-enrichment-architecture.md](docs/ai-enrichment-architecture.md) for complete implementation details.

### Analytics (Gold - Planned)

Planned transformations:
- Star schema (fact_job_postings + dimensions)
- Skills extraction and normalization
- Salary benchmarking by location/seniority
- Time-series aggregations
- ML feature engineering

See [docs/gold_features_metrics.md](docs/gold_features_metrics.md) for complete design.

## Documentation

| Document | Description |
|----------|-------------|
| [docs/silver_schema.md](docs/silver_schema.md) | Complete Silver layer schema with all fields |
| [docs/gold_features_metrics.md](docs/gold_features_metrics.md) | Gold layer design with analytics tables |
| [docs/bright-data.md](docs/bright-data.md) | Bright Data API integration guide |
| [docs/skills_detection_plan.md](docs/skills_detection_plan.md) | Skills extraction strategy |
| [docs/ai-enrichment-architecture.md](docs/ai-enrichment-architecture.md) | AI Enrichment pipeline architecture |
| [scripts/ai-enrichment/README.md](scripts/ai-enrichment/README.md) | AI Enrichment testing scripts |

## Roadmap

### ✅ Phase 1: Foundation (Completed)
- [x] Infrastructure setup with Terraform
- [x] Bronze layer ingestion (LinkedIn → S3)
- [x] Silver layer transformation (Glue PySpark)
- [x] Hourly automated execution
- [x] CloudWatch logging

### ✅ Phase 2: Skills & Scale (Completed)
- [x] Skills detection from job descriptions (150+ technologies)
- [x] SQS-based ingestion with throttling
- [x] Backfill support for bulk region ingestion
- [x] Multi-region/work-type configuration
- [x] Glue concurrent execution (max 10 parallel jobs)

### ✅ Phase 3: AI Enrichment (Completed)
- [x] 3-pass LLM enrichment architecture (Extract → Infer → Analyze)
- [x] AWS Bedrock integration with 6+ models
- [x] Multi-model consensus validation framework
- [x] 141 new enrichment columns (ext_, inf_, anl_)
- [x] Local testing scripts with S3 integration
- [x] Evaluation reports with inter-model agreement metrics

### 🚧 Phase 4: Analytics Layer (In Progress)
- [ ] Implement deduplication in Silver
- [ ] Create Gold layer transformations
- [ ] Build star schema (fact + dimensions)
- [ ] Salary normalization and benchmarking

### 📋 Phase 5: Insights & Visualization (Planned)
- [ ] Athena/Presto queries for ad-hoc analysis
- [ ] Metabase/Looker dashboards
- [ ] Salary trends by location/seniority
- [ ] Skills demand analysis
- [ ] Geographic heat maps

### 🚀 Phase 6: Advanced Features (Future)
- [ ] Real-time alerting for matching jobs
- [ ] ML-based job recommendations
- [ ] Career path analysis
- [ ] Company insights and ratings
- [ ] Public API for job data

## Contributing

This is a personal learning project, but contributions are welcome!

### How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run tests
pytest

# Format code
black src/
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **Bright Data** for providing LinkedIn scraping API
- **AWS** for the serverless infrastructure
- **Data Engineering community** for inspiration and best practices

## Contact

For questions, suggestions, or collaboration opportunities:

- **Email**: gedalias@gmail.com
- **GitHub**: @geda-valentim

---

**Built with ❤️ using Data Engineering to understand Data Engineering jobs**

If you find this project interesting or useful, please give it a ⭐!
