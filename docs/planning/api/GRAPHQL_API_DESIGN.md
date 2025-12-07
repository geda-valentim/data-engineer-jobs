# Plan: GraphQL API Serverless para Analytics do Silver AI

**Date:** 2025-12-07
**Status:** Planning

---

## User Request

Criar uma API GraphQL (AWS AppSync) para servir analytics dos dados enriquecidos (Silver AI), com suporte a teste local e arquitetura extensível para futura inclusão de dados Gold.

**Requisitos:**
1. Criar pasta `/api` para servir resultados dos reports do enrichment
2. Usar GraphQL com AWS AppSync
3. Pensar na melhor organização e permitir teste local
4. Por enquanto só analytics do Silver AI
5. Planejar para futura inclusão de dados Gold

**User Quote:**
> "cria uma pasta api e vamos com api servid os resultados dos reports do enrichment. depois vamos servir mais dados entao planeja ela bem. Pensa que vamos servir ela com GraphQL no Aws AppSync. Vamos pensar na melhor organizacao e permitir teste local. Pwnsa quw remos essa necesidade agora mas depois vamos servir os dados dongold tb... Por enquanfo só analytics do silver ai"

---

## Current State Analysis

### Silver AI Data Structure

**S3 Bucket:** `data-engineer-jobs-silver`
**Prefix:** `linkedin/`
**Partitioning:** Hive-style `year=YYYY/month=MM/day=DD/hour=HH/`
**Format:** Parquet with Snappy compression
**Total Columns:** 280 columns

**Column Categories:**
1. **Metadata (34 columns):**
   - job_posting_id, job_title, company_name, job_location
   - job_description_text, job_description_url
   - created_at, updated_at, data_source
   - enrichment metadata (model_id, timestamps, tokens, costs)

2. **Pass 1: Extraction (57 ext_* columns):**
   - Salary: ext_salary_min, ext_salary_max, ext_salary_currency
   - Experience: ext_years_experience_min/max/text
   - Skills: ext_must_have_hard_skills, ext_nice_to_have_hard_skills
   - Work model: ext_work_model_stated, ext_contract_type
   - Benefits: ext_equity_mentioned, ext_pto_policy

3. **Pass 2: Inference (100 inf_* columns):**
   - Each field has: value, confidence, evidence, source
   - Examples: inf_seniority_level, inf_management_role
   - Company attributes: inf_company_size, inf_industry
   - Tech stack: inf_tech_stack_primary

4. **Pass 3: Analysis (88 anl_* columns):**
   - Company maturity: anl_data_maturity_score/level
   - Red flags: anl_scope_creep_score, anl_overtime_risk_score
   - Culture: anl_work_life_balance_score, anl_growth_opportunities_score
   - Summary: anl_strengths, anl_concerns, anl_red_flags_to_probe
   - Recommendations: anl_recommendation_score, anl_overall_assessment

**Current Infrastructure:**
- ✅ S3 Parquet files (Bronze, Silver, Silver AI)
- ✅ Lambda functions for enrichment pipeline
- ✅ Bedrock integration for LLM processing
- ✅ Local test scripts with S3 data loading
- ❌ No API layer yet
- ❌ No Athena tables yet
- ❌ No GraphQL schema yet

---

## Proposed Architecture

### High-Level Flow

```
Client (Web/Mobile)
    ↓ GraphQL Query
AWS AppSync (GraphQL API)
    ↓ Resolver
AWS Lambda (Python 3.13)
    ↓ SQL Query
Amazon Athena
    ↓ Scan/Read
S3 Parquet (Silver AI)
    ↓ Results
Return formatted data
```

### Directory Structure

```
/api/
├── README.md                          # API documentation
├── schema.graphql                     # GraphQL schema (280 columns mapped)
├── serverless.yml                     # Serverless Framework config
├── package.json                       # Node.js dependencies (for local dev)
│
├── resolvers/                         # Lambda resolvers (Python 3.13)
│   ├── __init__.py
│   ├── jobs/
│   │   ├── __init__.py
│   │   ├── get_job.py                # Query: job(id: ID!)
│   │   ├── search_jobs.py            # Query: searchJobs(filter: JobFilter!)
│   │   └── list_jobs.py              # Query: listJobs(limit: Int, nextToken: String)
│   │
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── job_stats.py              # Query: jobStats(dateRange: DateRange!)
│   │   ├── trending_skills.py        # Query: trendingSkills(limit: Int)
│   │   ├── salary_ranges.py          # Query: salaryRanges(filters: SalaryFilter)
│   │   └── company_insights.py       # Query: companyInsights(companyName: String!)
│   │
│   └── shared/
│       ├── __init__.py
│       ├── athena_client.py          # Athena query wrapper
│       ├── filter_builder.py         # Build WHERE clauses from GraphQL filters
│       ├── formatters.py             # Format Athena results to GraphQL types
│       ├── validators.py             # Input validation
│       └── pagination.py             # Cursor-based pagination logic
│
├── athena/
│   ├── schema/
│   │   ├── create_linkedin_ai_table.sql     # DDL for all 280 columns
│   │   └── partition_projection_config.sql  # Partition projection setup
│   │
│   └── queries/
│       ├── search_jobs.sql.jinja2           # Parameterized SQL templates
│       ├── job_stats.sql.jinja2
│       ├── trending_skills.sql.jinja2
│       └── salary_ranges.sql.jinja2
│
├── local/                             # Local development environment
│   ├── server.py                      # Standalone GraphQL server (FastAPI + Strawberry)
│   ├── mock_data/
│   │   └── sample_jobs.json           # Mock data for local testing
│   ├── requirements.txt               # Python dependencies for local server
│   └── docker-compose.yml             # Optional: LocalStack for Athena emulation
│
├── terraform/                         # Infrastructure as Code
│   ├── main.tf
│   ├── appsync.tf                     # AppSync API + schema
│   ├── lambda.tf                      # Lambda resolvers
│   ├── athena.tf                      # Athena workgroup + Glue table
│   ├── iam.tf                         # IAM roles and policies
│   ├── s3.tf                          # S3 bucket for Athena results
│   └── variables.tf
│
└── tests/
    ├── integration/
    │   ├── test_get_job.py
    │   ├── test_search_jobs.py
    │   └── test_analytics.py
    └── unit/
        ├── test_filter_builder.py
        ├── test_formatters.py
        └── test_pagination.py
```

---

## GraphQL Schema Design

### Core Types

```graphql
# schema.graphql

# ============================================
# METADATA & BASE TYPES
# ============================================

type Job {
  # Metadata (34 fields)
  job_posting_id: ID!
  job_title: String!
  company_name: String!
  job_location: String
  job_description_text: String
  job_description_url: String
  created_at: String
  updated_at: String
  data_source: String

  # Enrichment metadata
  enrichment_model_id: String
  enrichment_timestamp: String
  enrichment_pass1_tokens: Int
  enrichment_pass2_tokens: Int
  enrichment_pass3_tokens: Int
  enrichment_total_cost: Float

  # Pass 1: Extraction (nested object)
  extraction: Extraction

  # Pass 2: Inference (nested object)
  inference: Inference

  # Pass 3: Analysis (nested object)
  analysis: Analysis
}

# ============================================
# PASS 1: EXTRACTION (57 fields)
# ============================================

type Extraction {
  # Salary
  salary_min: Float
  salary_max: Float
  salary_currency: String
  salary_period: String
  salary_text: String

  # Experience
  years_experience_min: Int
  years_experience_max: Int
  years_experience_text: String

  # Skills
  must_have_hard_skills: [String!]!
  nice_to_have_hard_skills: [String!]!
  must_have_soft_skills: [String!]!
  nice_to_have_soft_skills: [String!]!

  # Work Model
  work_model_stated: String
  work_locations: [String!]!
  relocation_assistance: Boolean

  # Contract
  contract_type: String
  visa_sponsorship_stated: String

  # Benefits
  equity_mentioned: Boolean
  pto_policy: String
  health_benefits: String
  retirement_benefits: String
  learning_budget: String

  # Education
  degree_required: String
  degree_preferred: String
  certifications_required: [String!]!

  # Team
  team_size_stated: String
  reporting_to: String

  # Other (total 57 fields)
  # ... remaining extraction fields
}

# ============================================
# PASS 2: INFERENCE (100 fields as nested objects)
# ============================================

type InferenceField {
  value: String
  confidence: Float!
  evidence: String
  source: String!
}

type InferenceFieldInt {
  value: Int
  confidence: Float!
  evidence: String
  source: String!
}

type InferenceFieldBoolean {
  value: Boolean
  confidence: Float!
  evidence: String
  source: String!
}

type InferenceFieldArray {
  value: [String!]!
  confidence: Float!
  evidence: String
  source: String!
}

type Inference {
  # Seniority & Role
  seniority_level: InferenceField
  management_role: InferenceFieldBoolean
  people_management: InferenceFieldBoolean

  # Company
  company_size: InferenceField
  company_stage: InferenceField
  industry: InferenceField

  # Tech Stack
  tech_stack_primary: InferenceFieldArray
  tech_stack_secondary: InferenceFieldArray

  # Work Environment
  work_model_inferred: InferenceField
  timezone_requirements: InferenceField

  # Growth
  career_growth_potential: InferenceField
  learning_opportunities: InferenceField

  # ... 25 total inference categories (100 fields with value/confidence/evidence/source)
}

# ============================================
# PASS 3: ANALYSIS (88 fields)
# ============================================

type Analysis {
  # Company Maturity
  company_maturity: CompanyMaturity

  # Red Flags
  red_flags: RedFlags

  # Stakeholders
  stakeholders: Stakeholders

  # Tech Culture
  tech_culture: TechCulture

  # Summary
  summary: AnalysisSummary
}

type CompanyMaturity {
  data_maturity_score: AnalysisField
  data_maturity_level: AnalysisField
  maturity_signals: AnalysisFieldArray
}

type RedFlags {
  scope_creep_score: AnalysisFieldFloat
  overtime_risk_score: AnalysisFieldFloat
  role_clarity: AnalysisField
  overall_red_flag_score: AnalysisFieldFloat
}

type Stakeholders {
  reporting_structure_clarity: AnalysisField
  manager_level_inferred: AnalysisField
  team_growth_velocity: AnalysisField
  team_composition: AnalysisFieldArray
  reporting_structure: AnalysisField
  cross_functional_embedded: AnalysisFieldBoolean
}

type TechCulture {
  work_life_balance_score: AnalysisFieldFloat
  growth_opportunities_score: AnalysisFieldFloat
  tech_culture_score: AnalysisFieldFloat
}

type AnalysisSummary {
  strengths: [String!]!
  concerns: [String!]!
  best_fit_for: [String!]!
  red_flags_to_probe: [String!]!
  negotiation_leverage: [String!]!
  overall_assessment: String!
  recommendation_score: AnalysisFieldFloat
  recommendation_confidence: AnalysisFieldFloat
}

type AnalysisField {
  value: String
  confidence: Float!
  evidence: String
  source: String!
}

type AnalysisFieldFloat {
  value: Float
  confidence: Float!
  evidence: String
  source: String!
}

type AnalysisFieldBoolean {
  value: Boolean
  confidence: Float!
  evidence: String
  source: String!
}

type AnalysisFieldArray {
  value: [String!]!
  confidence: Float!
  evidence: String
  source: String!
}

# ============================================
# QUERY ROOT
# ============================================

type Query {
  # Job queries
  job(id: ID!): Job
  searchJobs(filter: JobFilter, limit: Int = 20, nextToken: String): JobConnection!
  listJobs(limit: Int = 20, nextToken: String): JobConnection!

  # Analytics queries
  jobStats(dateRange: DateRange!): JobStats!
  trendingSkills(limit: Int = 10): [SkillTrend!]!
  salaryRanges(filter: SalaryFilter): [SalaryRange!]!
  companyInsights(companyName: String!): CompanyInsights
}

# ============================================
# INPUT TYPES (Filters)
# ============================================

input JobFilter {
  # Metadata filters
  company_name: StringFilter
  job_location: StringFilter
  job_title: StringFilter

  # Extraction filters
  salary_min_gte: Float
  salary_max_lte: Float
  years_experience_min_gte: Int
  years_experience_max_lte: Int
  must_have_skills: [String!]
  work_model: String
  contract_type: String

  # Inference filters
  seniority_level: String
  company_size: String

  # Analysis filters
  recommendation_score_gte: Float
  data_maturity_score_gte: Int

  # Date filters
  created_after: String
  created_before: String

  # Partition filters
  partition_date: String  # YYYY-MM-DD
  partition_hour: Int
}

input StringFilter {
  eq: String
  contains: String
  startsWith: String
}

input DateRange {
  start: String!  # YYYY-MM-DD
  end: String!    # YYYY-MM-DD
}

input SalaryFilter {
  currency: String = "USD"
  seniority_level: String
  location: String
}

# ============================================
# PAGINATION
# ============================================

type JobConnection {
  jobs: [Job!]!
  nextToken: String
  totalCount: Int
}

# ============================================
# ANALYTICS TYPES
# ============================================

type JobStats {
  total_jobs: Int!
  avg_salary_min: Float
  avg_salary_max: Float
  top_companies: [CompanyCount!]!
  top_locations: [LocationCount!]!
  work_model_distribution: [WorkModelCount!]!
}

type CompanyCount {
  company_name: String!
  count: Int!
}

type LocationCount {
  location: String!
  count: Int!
}

type WorkModelCount {
  work_model: String!
  count: Int!
}

type SkillTrend {
  skill: String!
  count: Int!
  avg_salary: Float
  demand_trend: String  # "rising", "stable", "falling"
}

type SalaryRange {
  percentile_10: Float
  percentile_25: Float
  median: Float
  percentile_75: Float
  percentile_90: Float
  sample_size: Int!
}

type CompanyInsights {
  company_name: String!
  total_jobs: Int!
  avg_salary: Float
  common_tech_stack: [String!]!
  avg_data_maturity_score: Float
  avg_recommendation_score: Float
}
```

---

## Resolver Implementation

### Example: `resolvers/jobs/search_jobs.py`

```python
"""
Search jobs resolver with Athena integration.
"""
import json
import os
from typing import Dict, Any, List, Optional
from resolvers.shared.athena_client import AthenaClient
from resolvers.shared.filter_builder import build_where_clause
from resolvers.shared.formatters import format_job_result
from resolvers.shared.pagination import encode_cursor, decode_cursor


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for searchJobs GraphQL query.

    GraphQL Query:
        searchJobs(filter: JobFilter, limit: Int, nextToken: String): JobConnection!

    Args:
        event: AppSync resolver event with arguments
        context: Lambda context

    Returns:
        JobConnection with jobs array and pagination
    """
    # Extract arguments from AppSync event
    arguments = event.get('arguments', {})
    filter_input = arguments.get('filter', {})
    limit = arguments.get('limit', 20)
    next_token = arguments.get('nextToken')

    # Decode pagination cursor
    offset = 0
    if next_token:
        offset = decode_cursor(next_token)

    # Build WHERE clause from filter
    where_clause, params = build_where_clause(filter_input)

    # Build SQL query
    sql = f"""
    SELECT
        -- Metadata (34 columns)
        job_posting_id,
        job_title,
        company_name,
        job_location,
        job_description_text,
        -- ... all 280 columns

        -- Pass 1: Extraction (57 columns with ext_ prefix)
        ext_salary_min,
        ext_salary_max,
        ext_salary_currency,
        ext_years_experience_min,
        ext_years_experience_max,
        ext_must_have_hard_skills,
        -- ... remaining ext_ columns

        -- Pass 2: Inference (100 columns with inf_ prefix)
        inf_seniority_level_value,
        inf_seniority_level_confidence,
        inf_seniority_level_evidence,
        inf_seniority_level_source,
        -- ... remaining inf_ columns

        -- Pass 3: Analysis (88 columns with anl_ prefix)
        anl_data_maturity_score_value,
        anl_data_maturity_score_confidence,
        anl_recommendation_score_value,
        -- ... remaining anl_ columns

    FROM linkedin_jobs_ai
    WHERE {where_clause}
    ORDER BY created_at DESC
    LIMIT {limit + 1}
    OFFSET {offset}
    """

    # Execute Athena query
    athena = AthenaClient()
    results = athena.execute_query(sql, params)

    # Check if more results available
    has_next = len(results) > limit
    if has_next:
        results = results[:limit]

    # Format results to GraphQL Job type
    jobs = [format_job_result(row) for row in results]

    # Encode next token
    next_token_response = None
    if has_next:
        next_token_response = encode_cursor(offset + limit)

    return {
        'jobs': jobs,
        'nextToken': next_token_response,
        'totalCount': None  # Optional: run COUNT(*) query
    }
```

### Example: `resolvers/shared/athena_client.py`

```python
"""
Amazon Athena client wrapper for executing SQL queries.
"""
import boto3
import time
import os
from typing import List, Dict, Any


class AthenaClient:
    """Wrapper for Amazon Athena queries."""

    def __init__(self):
        self.client = boto3.client('athena')
        self.database = os.environ['ATHENA_DATABASE']
        self.workgroup = os.environ['ATHENA_WORKGROUP']
        self.output_location = os.environ['ATHENA_OUTPUT_LOCATION']

    def execute_query(self, sql: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Execute Athena query and return results.

        Args:
            sql: SQL query string
            params: Optional parameters for parameterized query

        Returns:
            List of result rows as dictionaries
        """
        # Start query execution
        response = self.client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={'Database': self.database},
            ResultConfiguration={'OutputLocation': self.output_location},
            WorkGroup=self.workgroup
        )

        query_execution_id = response['QueryExecutionId']

        # Wait for query to complete
        status = self._wait_for_query(query_execution_id)

        if status != 'SUCCEEDED':
            raise Exception(f"Query failed with status: {status}")

        # Get query results
        results = self._get_query_results(query_execution_id)

        return results

    def _wait_for_query(self, query_execution_id: str, max_wait_seconds: int = 30) -> str:
        """Wait for Athena query to complete."""
        elapsed = 0
        while elapsed < max_wait_seconds:
            response = self.client.get_query_execution(
                QueryExecutionId=query_execution_id
            )
            status = response['QueryExecution']['Status']['State']

            if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
                return status

            time.sleep(1)
            elapsed += 1

        raise TimeoutError(f"Query timed out after {max_wait_seconds}s")

    def _get_query_results(self, query_execution_id: str) -> List[Dict[str, Any]]:
        """Fetch and parse query results."""
        results = []
        next_token = None

        while True:
            kwargs = {'QueryExecutionId': query_execution_id}
            if next_token:
                kwargs['NextToken'] = next_token

            response = self.client.get_query_results(**kwargs)

            # Parse results
            rows = response['ResultSet']['Rows']
            if not results:  # First page - skip header row
                rows = rows[1:]

            # Extract column names from metadata
            columns = [col['Label'] for col in response['ResultSet']['ResultSetMetadata']['ColumnInfo']]

            # Convert rows to dictionaries
            for row in rows:
                values = [field.get('VarCharValue') for field in row['Data']]
                results.append(dict(zip(columns, values)))

            # Check for more pages
            next_token = response.get('NextToken')
            if not next_token:
                break

        return results
```

### Example: `resolvers/shared/filter_builder.py`

```python
"""
Build SQL WHERE clauses from GraphQL filter inputs.
"""
from typing import Dict, Any, Tuple, List


def build_where_clause(filter_input: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Build SQL WHERE clause from GraphQL JobFilter input.

    Args:
        filter_input: GraphQL filter arguments

    Returns:
        Tuple of (where_clause_string, parameters_dict)
    """
    conditions = []
    params = {}

    # String filters
    if 'company_name' in filter_input:
        string_filter = filter_input['company_name']
        if 'eq' in string_filter:
            conditions.append("company_name = :company_name")
            params['company_name'] = string_filter['eq']
        elif 'contains' in string_filter:
            conditions.append("company_name LIKE :company_name")
            params['company_name'] = f"%{string_filter['contains']}%"
        elif 'startsWith' in string_filter:
            conditions.append("company_name LIKE :company_name")
            params['company_name'] = f"{string_filter['startsWith']}%"

    if 'job_title' in filter_input:
        string_filter = filter_input['job_title']
        if 'contains' in string_filter:
            conditions.append("job_title LIKE :job_title")
            params['job_title'] = f"%{string_filter['contains']}%"

    # Numeric filters
    if 'salary_min_gte' in filter_input:
        conditions.append("ext_salary_min >= :salary_min_gte")
        params['salary_min_gte'] = filter_input['salary_min_gte']

    if 'salary_max_lte' in filter_input:
        conditions.append("ext_salary_max <= :salary_max_lte")
        params['salary_max_lte'] = filter_input['salary_max_lte']

    if 'years_experience_min_gte' in filter_input:
        conditions.append("ext_years_experience_min >= :years_exp_min")
        params['years_exp_min'] = filter_input['years_experience_min_gte']

    # Array filters (skills)
    if 'must_have_skills' in filter_input:
        # Check if any of the required skills are in must_have_hard_skills array
        skill_conditions = []
        for i, skill in enumerate(filter_input['must_have_skills']):
            param_name = f'skill_{i}'
            skill_conditions.append(f"contains(ext_must_have_hard_skills, :{param_name})")
            params[param_name] = skill

        if skill_conditions:
            conditions.append(f"({' AND '.join(skill_conditions)})")

    # Enum filters
    if 'work_model' in filter_input:
        conditions.append("ext_work_model_stated = :work_model")
        params['work_model'] = filter_input['work_model']

    if 'contract_type' in filter_input:
        conditions.append("ext_contract_type = :contract_type")
        params['contract_type'] = filter_input['contract_type']

    if 'seniority_level' in filter_input:
        conditions.append("inf_seniority_level_value = :seniority")
        params['seniority'] = filter_input['seniority_level']

    # Score filters
    if 'recommendation_score_gte' in filter_input:
        conditions.append("anl_recommendation_score_value >= :rec_score")
        params['rec_score'] = filter_input['recommendation_score_gte']

    if 'data_maturity_score_gte' in filter_input:
        conditions.append("anl_data_maturity_score_value >= :maturity")
        params['maturity'] = filter_input['data_maturity_score_gte']

    # Date filters
    if 'created_after' in filter_input:
        conditions.append("created_at >= :created_after")
        params['created_after'] = filter_input['created_after']

    if 'created_before' in filter_input:
        conditions.append("created_at <= :created_before")
        params['created_before'] = filter_input['created_before']

    # Partition filters (for performance optimization)
    if 'partition_date' in filter_input:
        date_parts = filter_input['partition_date'].split('-')
        conditions.append(f"year = '{date_parts[0]}'")
        conditions.append(f"month = '{date_parts[1]}'")
        conditions.append(f"day = '{date_parts[2]}'")

    if 'partition_hour' in filter_input:
        conditions.append(f"hour = '{filter_input['partition_hour']:02d}'")

    # Default: always filter to valid enriched jobs
    conditions.append("enrichment_pass1_success = true")

    # Combine conditions
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    return where_clause, params
```

---

## Athena Table Schema

### DDL: `athena/schema/create_linkedin_ai_table.sql`

```sql
CREATE EXTERNAL TABLE IF NOT EXISTS linkedin_jobs_ai (
    -- ============================================
    -- METADATA (34 columns)
    -- ============================================
    job_posting_id STRING,
    job_title STRING,
    company_name STRING,
    job_location STRING,
    job_description_text STRING,
    job_description_url STRING,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    data_source STRING,

    -- Enrichment metadata
    enrichment_model_id STRING,
    enrichment_timestamp TIMESTAMP,
    enrichment_pass1_success BOOLEAN,
    enrichment_pass1_tokens INT,
    enrichment_pass1_input_tokens INT,
    enrichment_pass1_output_tokens INT,
    enrichment_pass1_cost DOUBLE,
    enrichment_pass2_success BOOLEAN,
    enrichment_pass2_tokens INT,
    enrichment_pass2_input_tokens INT,
    enrichment_pass2_output_tokens INT,
    enrichment_pass2_cost DOUBLE,
    enrichment_pass3_success BOOLEAN,
    enrichment_pass3_tokens INT,
    enrichment_pass3_input_tokens INT,
    enrichment_pass3_output_tokens INT,
    enrichment_pass3_cost DOUBLE,
    enrichment_total_tokens INT,
    enrichment_total_cost DOUBLE,

    -- ============================================
    -- PASS 1: EXTRACTION (57 columns with ext_ prefix)
    -- ============================================

    -- Salary
    ext_salary_min DOUBLE,
    ext_salary_max DOUBLE,
    ext_salary_currency STRING,
    ext_salary_period STRING,
    ext_salary_text STRING,

    -- Experience
    ext_years_experience_min INT,
    ext_years_experience_max INT,
    ext_years_experience_text STRING,

    -- Skills
    ext_must_have_hard_skills ARRAY<STRING>,
    ext_nice_to_have_hard_skills ARRAY<STRING>,
    ext_must_have_soft_skills ARRAY<STRING>,
    ext_nice_to_have_soft_skills ARRAY<STRING>,

    -- Work Model
    ext_work_model_stated STRING,
    ext_work_locations ARRAY<STRING>,
    ext_relocation_assistance BOOLEAN,

    -- Contract
    ext_contract_type STRING,
    ext_visa_sponsorship_stated STRING,

    -- Benefits
    ext_equity_mentioned BOOLEAN,
    ext_pto_policy STRING,
    ext_health_benefits STRING,
    ext_retirement_benefits STRING,
    ext_learning_budget STRING,

    -- ... (remaining 37 ext_ columns)

    -- ============================================
    -- PASS 2: INFERENCE (100 columns with inf_ prefix)
    -- Each field has: _value, _confidence, _evidence, _source
    -- ============================================

    -- Seniority & Role (4 fields = 16 columns)
    inf_seniority_level_value STRING,
    inf_seniority_level_confidence DOUBLE,
    inf_seniority_level_evidence STRING,
    inf_seniority_level_source STRING,

    inf_management_role_value BOOLEAN,
    inf_management_role_confidence DOUBLE,
    inf_management_role_evidence STRING,
    inf_management_role_source STRING,

    -- ... (remaining 96 inf_ columns for 24 more inference fields)

    -- ============================================
    -- PASS 3: ANALYSIS (88 columns with anl_ prefix)
    -- ============================================

    -- Company Maturity (3 fields)
    anl_data_maturity_score_value INT,
    anl_data_maturity_score_confidence DOUBLE,
    anl_data_maturity_score_evidence STRING,
    anl_data_maturity_score_source STRING,

    anl_data_maturity_level_value STRING,
    anl_data_maturity_level_confidence DOUBLE,
    anl_data_maturity_level_evidence STRING,
    anl_data_maturity_level_source STRING,

    anl_maturity_signals_value ARRAY<STRING>,
    anl_maturity_signals_confidence DOUBLE,
    anl_maturity_signals_evidence STRING,
    anl_maturity_signals_source STRING,

    -- Red Flags (4 fields = 16 columns)
    anl_scope_creep_score_value DOUBLE,
    anl_scope_creep_score_confidence DOUBLE,
    anl_scope_creep_score_evidence STRING,
    anl_scope_creep_score_source STRING,

    -- ... (remaining 72 anl_ columns for 18 more analysis fields)

    -- Summary (7 fields)
    anl_strengths ARRAY<STRING>,
    anl_concerns ARRAY<STRING>,
    anl_best_fit_for ARRAY<STRING>,
    anl_red_flags_to_probe ARRAY<STRING>,
    anl_negotiation_leverage ARRAY<STRING>,
    anl_overall_assessment STRING,

    anl_recommendation_score_value DOUBLE,
    anl_recommendation_score_confidence DOUBLE,
    anl_recommendation_confidence_value DOUBLE,
    anl_recommendation_confidence_confidence DOUBLE
)
PARTITIONED BY (
    year STRING,
    month STRING,
    day STRING,
    hour STRING
)
STORED AS PARQUET
LOCATION 's3://data-engineer-jobs-silver/linkedin/'
TBLPROPERTIES (
    'projection.enabled' = 'true',
    'projection.year.type' = 'integer',
    'projection.year.range' = '2024,2030',
    'projection.month.type' = 'integer',
    'projection.month.range' = '01,12',
    'projection.month.digits' = '2',
    'projection.day.type' = 'integer',
    'projection.day.range' = '01,31',
    'projection.day.digits' = '2',
    'projection.hour.type' = 'integer',
    'projection.hour.range' = '00,23',
    'projection.hour.digits' = '2',
    'storage.location.template' = 's3://data-engineer-jobs-silver/linkedin/year=${year}/month=${month}/day=${day}/hour=${hour}',
    'parquet.compression' = 'SNAPPY'
);
```

---

## Local Testing Setup

### Local GraphQL Server: `local/server.py`

```python
"""
Local GraphQL server for testing API without AWS.
Uses FastAPI + Strawberry GraphQL.
"""
import json
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI
import strawberry
from strawberry.fastapi import GraphQLRouter


# Load mock data
MOCK_DATA_PATH = Path(__file__).parent / "mock_data" / "sample_jobs.json"

def load_mock_jobs():
    """Load sample jobs from local JSON file."""
    if MOCK_DATA_PATH.exists():
        with open(MOCK_DATA_PATH, 'r') as f:
            return json.load(f)
    return []


# GraphQL types (simplified for local testing)
@strawberry.type
class Job:
    job_posting_id: str
    job_title: str
    company_name: str
    job_location: Optional[str]
    ext_salary_min: Optional[float]
    ext_salary_max: Optional[float]
    ext_years_experience_min: Optional[int]
    anl_recommendation_score_value: Optional[float]


@strawberry.input
class JobFilter:
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    salary_min_gte: Optional[float] = None


@strawberry.type
class JobConnection:
    jobs: List[Job]
    total_count: int


# Resolvers
@strawberry.type
class Query:
    @strawberry.field
    def job(self, id: str) -> Optional[Job]:
        """Get single job by ID."""
        jobs = load_mock_jobs()
        for job_data in jobs:
            if job_data.get('job_posting_id') == id:
                return Job(**job_data)
        return None

    @strawberry.field
    def search_jobs(
        self,
        filter: Optional[JobFilter] = None,
        limit: int = 20
    ) -> JobConnection:
        """Search jobs with filters."""
        jobs = load_mock_jobs()

        # Apply filters
        if filter:
            if filter.company_name:
                jobs = [j for j in jobs if filter.company_name.lower() in j.get('company_name', '').lower()]
            if filter.job_title:
                jobs = [j for j in jobs if filter.job_title.lower() in j.get('job_title', '').lower()]
            if filter.salary_min_gte:
                jobs = [j for j in jobs if j.get('ext_salary_min', 0) >= filter.salary_min_gte]

        # Limit results
        jobs = jobs[:limit]

        # Convert to Job objects
        job_objects = [Job(**j) for j in jobs]

        return JobConnection(jobs=job_objects, total_count=len(jobs))


# Create FastAPI app
schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(schema)

app = FastAPI()
app.include_router(graphql_app, prefix="/graphql")


@app.get("/")
def root():
    return {"message": "LinkedIn Jobs AI Analytics API - Local Server", "graphql_endpoint": "/graphql"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Usage:

```bash
# Install dependencies
cd api/local
pip install -r requirements.txt

# Start local server
python server.py

# Server runs on http://localhost:8000
# GraphQL endpoint: http://localhost:8000/graphql
# GraphQL Playground: http://localhost:8000/graphql (interactive)

# Example query:
# {
#   searchJobs(filter: {company_name: "Amazon"}, limit: 5) {
#     jobs {
#       job_title
#       company_name
#       ext_salary_min
#       ext_salary_max
#     }
#     total_count
#   }
# }
```

---

## Terraform Infrastructure

### Main Config: `terraform/appsync.tf`

```hcl
# AWS AppSync GraphQL API
resource "aws_appsync_graphql_api" "linkedin_jobs_api" {
  name                = "linkedin-jobs-ai-analytics"
  authentication_type = "API_KEY"

  schema = file("${path.module}/../schema.graphql")

  log_config {
    cloudwatch_logs_role_arn = aws_iam_role.appsync_logs.arn
    field_log_level          = "ERROR"
  }

  tags = {
    Environment = var.environment
    Project     = "data-engineer-jobs"
    Layer       = "api"
  }
}

# API Key (temporary - migrate to Cognito later)
resource "aws_appsync_api_key" "main" {
  api_id  = aws_appsync_graphql_api.linkedin_jobs_api.id
  expires = timeadd(timestamp(), "365d")
}

# Data source: Lambda
resource "aws_appsync_datasource" "lambda" {
  for_each = toset([
    "get_job",
    "search_jobs",
    "list_jobs",
    "job_stats",
    "trending_skills",
    "salary_ranges",
    "company_insights"
  ])

  api_id           = aws_appsync_graphql_api.linkedin_jobs_api.id
  name             = "lambda_${each.key}"
  service_role_arn = aws_iam_role.appsync_lambda.arn
  type             = "AWS_LAMBDA"

  lambda_config {
    function_arn = aws_lambda_function.resolvers[each.key].arn
  }
}

# Resolvers
resource "aws_appsync_resolver" "query_job" {
  api_id      = aws_appsync_graphql_api.linkedin_jobs_api.id
  type        = "Query"
  field       = "job"
  data_source = aws_appsync_datasource.lambda["get_job"].name
}

resource "aws_appsync_resolver" "query_search_jobs" {
  api_id      = aws_appsync_graphql_api.linkedin_jobs_api.id
  type        = "Query"
  field       = "searchJobs"
  data_source = aws_appsync_datasource.lambda["search_jobs"].name
}

# ... (repeat for each query)
```

### Lambda Config: `terraform/lambda.tf`

```hcl
# Lambda function for each resolver
resource "aws_lambda_function" "resolvers" {
  for_each = toset([
    "get_job",
    "search_jobs",
    "list_jobs",
    "job_stats",
    "trending_skills",
    "salary_ranges",
    "company_insights"
  ])

  function_name = "linkedin-jobs-api-${each.key}"
  handler       = "${each.key}.handler"
  runtime       = "python3.13"
  role          = aws_iam_role.lambda_resolver.arn

  filename         = data.archive_file.resolver_zip[each.key].output_path
  source_code_hash = data.archive_file.resolver_zip[each.key].output_base64sha256

  timeout     = 30
  memory_size = 512

  environment {
    variables = {
      ATHENA_DATABASE        = aws_glue_catalog_database.linkedin_jobs.name
      ATHENA_WORKGROUP       = aws_athena_workgroup.api.name
      ATHENA_OUTPUT_LOCATION = "s3://${aws_s3_bucket.athena_results.bucket}/query-results/"
    }
  }

  tags = {
    Environment = var.environment
    Resolver    = each.key
  }
}

# Package Lambda code
data "archive_file" "resolver_zip" {
  for_each = toset([
    "get_job",
    "search_jobs",
    "list_jobs",
    "job_stats",
    "trending_skills",
    "salary_ranges",
    "company_insights"
  ])

  type        = "zip"
  source_dir  = "${path.module}/../resolvers/${each.key}"
  output_path = "${path.module}/.terraform/lambda/${each.key}.zip"
}
```

### Athena Config: `terraform/athena.tf`

```hcl
# Glue Database
resource "aws_glue_catalog_database" "linkedin_jobs" {
  name = "linkedin_jobs_db"
}

# Glue Table (using partition projection)
resource "aws_glue_catalog_table" "linkedin_jobs_ai" {
  database_name = aws_glue_catalog_database.linkedin_jobs.name
  name          = "linkedin_jobs_ai"

  table_type = "EXTERNAL_TABLE"

  storage_descriptor {
    location      = "s3://data-engineer-jobs-silver/linkedin/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "job_posting_id"
      type = "string"
    }

    # ... (all 280 columns defined)
  }

  partition_keys {
    name = "year"
    type = "string"
  }
  partition_keys {
    name = "month"
    type = "string"
  }
  partition_keys {
    name = "day"
    type = "string"
  }
  partition_keys {
    name = "hour"
    type = "string"
  }

  parameters = {
    "projection.enabled"                 = "true"
    "projection.year.type"               = "integer"
    "projection.year.range"              = "2024,2030"
    "projection.month.type"              = "integer"
    "projection.month.range"             = "01,12"
    "projection.month.digits"            = "2"
    "projection.day.type"                = "integer"
    "projection.day.range"               = "01,31"
    "projection.day.digits"              = "2"
    "projection.hour.type"               = "integer"
    "projection.hour.range"              = "00,23"
    "projection.hour.digits"             = "2"
    "storage.location.template"          = "s3://data-engineer-jobs-silver/linkedin/year=$${year}/month=$${month}/day=$${day}/hour=$${hour}"
    "parquet.compression"                = "SNAPPY"
  }
}

# Athena Workgroup
resource "aws_athena_workgroup" "api" {
  name = "linkedin-jobs-api"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_results.bucket}/query-results/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }

  tags = {
    Environment = var.environment
  }
}

# S3 bucket for Athena query results
resource "aws_s3_bucket" "athena_results" {
  bucket = "linkedin-jobs-athena-results-${var.environment}"

  tags = {
    Environment = var.environment
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    id     = "delete-old-results"
    status = "Enabled"

    expiration {
      days = 7
    }
  }
}
```

---

## Future Roadmap: Gold Layer Integration

### Gold Layer Data (Planned)

**New Gold Tables to Add:**
1. **Company Profiles** (aggregated company insights)
2. **Skills Taxonomy** (normalized skill names with synonyms)
3. **Salary Benchmarks** (aggregated salary data by role/location/seniority)
4. **Market Trends** (time-series analytics)
5. **Job Recommendations** (personalized matching scores)

### Schema Extension (Gold Layer)

```graphql
# Future: Gold Layer Types

type Company {
  company_name: String!
  total_jobs_posted: Int!
  avg_data_maturity_score: Float
  avg_recommendation_score: Float
  common_tech_stack: [String!]!
  avg_salary_range: SalaryRange
  company_size_inferred: String
  industry_inferred: String
  hiring_velocity: String  # "high", "medium", "low"
  culture_signals: [String!]!
}

type SkillTaxonomy {
  canonical_skill_name: String!
  synonyms: [String!]!
  category: String!  # "language", "framework", "tool", "cloud", etc.
  demand_score: Float!
  avg_salary_premium: Float
  trending: Boolean!
}

type SalaryBenchmark {
  role_category: String!
  seniority_level: String!
  location: String!
  currency: String!
  percentile_10: Float
  percentile_25: Float
  median: Float
  percentile_75: Float
  percentile_90: Float
  sample_size: Int!
  last_updated: String!
}

type MarketTrend {
  metric: String!  # "avg_salary", "job_count", "skill_demand"
  time_period: String!  # "2025-12"
  value: Float!
  change_pct: Float
  trend_direction: String  # "up", "down", "stable"
}

# New Queries (Gold Layer)
extend type Query {
  # Company analytics
  company(name: String!): Company
  topCompanies(limit: Int = 10, sortBy: String = "total_jobs"): [Company!]!

  # Skills taxonomy
  skill(name: String!): SkillTaxonomy
  searchSkills(category: String, trending: Boolean): [SkillTaxonomy!]!

  # Salary benchmarks
  salaryBenchmark(
    role: String!
    seniority: String!
    location: String
  ): SalaryBenchmark

  # Market trends
  marketTrends(
    metric: String!
    startDate: String!
    endDate: String!
  ): [MarketTrend!]!

  # Personalized recommendations
  recommendJobs(
    user_skills: [String!]!
    user_preferences: UserPreferences
    limit: Int = 20
  ): [JobRecommendation!]!
}
```

### Gold Layer Resolvers (Planned)

New resolver directory structure:
```
/api/resolvers/gold/
├── companies/
│   ├── get_company.py
│   ├── top_companies.py
├── skills/
│   ├── get_skill.py
│   ├── search_skills.py
├── benchmarks/
│   ├── salary_benchmark.py
├── trends/
│   ├── market_trends.py
└── recommendations/
    └── recommend_jobs.py
```

---

## Performance Optimization

### Athena Query Optimization

1. **Partition Projection:** Enabled (no MSCK REPAIR TABLE needed)
2. **Columnar Reads:** Parquet allows reading only requested columns
3. **Predicate Pushdown:** WHERE clauses applied at S3 scan time
4. **Partition Pruning:** Always filter by year/month/day/hour when possible
5. **Result Caching:** Athena caches identical queries for 1 hour

### Cost Estimates

**Athena Pricing:**
- $5 per TB scanned
- Average query scans ~500 KB (with partition filtering)
- Cost per query: ~$0.0000025 (negligible)

**Lambda Pricing:**
- 512 MB memory, 1 second avg duration
- $0.0000083 per request
- 1 million requests/month = $8.30

**AppSync Pricing:**
- $4 per million queries
- $0.08 per million minutes of real-time connection

**Expected Monthly Cost:**
- 1M API calls: ~$25-30
- 10M API calls: ~$100-150

### Caching Strategy

1. **Client-side caching:** Cache results in browser/mobile app
2. **API Gateway caching:** Enable AppSync caching (TTL: 5 minutes)
3. **Lambda caching:** Reuse Athena client connections
4. **Athena result caching:** Automatic 1-hour cache for identical queries

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_filter_builder.py

def test_build_where_clause_company_name():
    filter_input = {
        'company_name': {'eq': 'Amazon'}
    }
    where, params = build_where_clause(filter_input)

    assert 'company_name = :company_name' in where
    assert params['company_name'] == 'Amazon'

def test_build_where_clause_salary_range():
    filter_input = {
        'salary_min_gte': 100000,
        'salary_max_lte': 200000
    }
    where, params = build_where_clause(filter_input)

    assert 'ext_salary_min >= :salary_min_gte' in where
    assert 'ext_salary_max <= :salary_max_lte' in where
```

### Integration Tests

```python
# tests/integration/test_search_jobs.py

import boto3
import json

def test_search_jobs_graphql():
    """Test searchJobs query against deployed AppSync API."""
    appsync = boto3.client('appsync')

    query = """
    query SearchJobs($filter: JobFilter!) {
      searchJobs(filter: $filter, limit: 5) {
        jobs {
          job_posting_id
          job_title
          company_name
          extraction {
            salary_min
            salary_max
          }
        }
        totalCount
      }
    }
    """

    variables = {
        'filter': {
            'company_name': {'contains': 'Amazon'},
            'salary_min_gte': 150000
        }
    }

    response = appsync.evaluate_code(
        runtime={'name': 'APPSYNC_JS', 'runtimeVersion': '1.0.0'},
        code=query,
        context=json.dumps(variables)
    )

    assert response['evaluationResult']
    data = json.loads(response['evaluationResult'])
    assert 'searchJobs' in data
    assert len(data['searchJobs']['jobs']) <= 5
```

---

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1-2)

**Tasks:**
1. ✅ Create `/api` directory structure
2. ✅ Define GraphQL schema (all 280 columns)
3. ✅ Create Athena table DDL with partition projection
4. ✅ Implement basic resolvers: `get_job`, `search_jobs`
5. ✅ Implement shared utilities: `athena_client.py`, `filter_builder.py`
6. ✅ Set up Terraform for AppSync + Lambda + Athena
7. ✅ Deploy to dev environment

**Deliverables:**
- Working GraphQL API with basic job queries
- Athena table querying S3 Parquet files
- Local testing environment

**Estimated Effort:** 40 hours

---

### Phase 2: Analytics Queries (Week 3)

**Tasks:**
1. ✅ Implement `jobStats` resolver
2. ✅ Implement `trendingSkills` resolver
3. ✅ Implement `salaryRanges` resolver
4. ✅ Implement `companyInsights` resolver
5. ✅ Add SQL query templates (Jinja2)
6. ✅ Write unit tests for all resolvers
7. ✅ Add integration tests

**Deliverables:**
- Complete analytics queries
- SQL templates for reusability
- Test coverage >80%

**Estimated Effort:** 24 hours

---

### Phase 3: Local Development (Week 4)

**Tasks:**
1. ✅ Implement local GraphQL server (FastAPI + Strawberry)
2. ✅ Create mock data loader from `/data/local/`
3. ✅ Add Docker Compose for local environment
4. ✅ Write local testing guide
5. ✅ Add GraphQL Playground UI

**Deliverables:**
- Fully functional local API server
- Mock data for testing
- Developer documentation

**Estimated Effort:** 16 hours

---

### Phase 4: Production Readiness (Week 5)

**Tasks:**
1. ✅ Add CloudWatch logging and metrics
2. ✅ Implement error handling and retries
3. ✅ Add request validation
4. ✅ Set up CI/CD pipeline
5. ✅ Performance testing (load testing with Artillery)
6. ✅ Security review (IAM policies, API key rotation)
7. ✅ Documentation (README, API guide, runbook)

**Deliverables:**
- Production-ready API
- Monitoring and alerting
- Complete documentation

**Estimated Effort:** 32 hours

---

### Total Effort Estimate

| Phase | Effort | Calendar Time |
|-------|--------|---------------|
| Phase 1: Core Infrastructure | 40 hours | 2 weeks |
| Phase 2: Analytics Queries | 24 hours | 1 week |
| Phase 3: Local Development | 16 hours | 1 week |
| Phase 4: Production Readiness | 32 hours | 1 week |
| **Total** | **112 hours** | **~5 weeks** |

---

## Success Criteria

✅ **GraphQL API deployed to AWS AppSync**
✅ **All 280 columns accessible via GraphQL queries**
✅ **Athena integration working with partition projection**
✅ **Local testing environment functional**
✅ **Performance: <2s for typical queries**
✅ **Cost: <$50/month for 1M requests**
✅ **Test coverage: >80%**
✅ **Documentation complete**
✅ **Extensible architecture for Gold layer**

---

## Risk Assessment

### Low Risk
- ✅ Athena partition projection (proven technology)
- ✅ GraphQL schema design (well-understood patterns)
- ✅ Lambda resolvers (simple query logic)

### Medium Risk
- ⚠️ **Athena query performance** - Need to test with large datasets
- ⚠️ **Cold start latency** - Lambda may have 1-2s cold starts
- ⚠️ **Schema evolution** - Adding Gold layer may require schema versioning

### Mitigation Strategies
- **Performance:** Use partition pruning, columnar reads, result caching
- **Cold starts:** Use provisioned concurrency for critical resolvers
- **Schema evolution:** Use GraphQL interfaces and unions for extensibility

---

## Next Steps

After approval:

1. ✅ Create `/api` directory structure
2. ✅ Copy `schema.graphql` to `/api/schema.graphql`
3. ✅ Implement `athena_client.py` in `/api/resolvers/shared/`
4. ✅ Implement `search_jobs.py` resolver
5. ✅ Create Athena table DDL
6. ✅ Set up local testing environment
7. ✅ Test with real S3 data
8. ✅ Deploy to dev environment
