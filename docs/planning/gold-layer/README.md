# Gold Layer Implementation

## Overview

Implementation of the Gold Layer (dimensional model) using dbt + Redshift Serverless.

## Sprint Structure

| Sprint | Focus | Tables | Status |
|--------|-------|--------|--------|
| [Sprint 0](./sprint-00-infrastructure.md) | Infrastructure | VPC, Redshift, Lambda, dbt setup | Planned |
| [Sprint 1](./sprint-01-dimensions.md) | Dimensions | 55 dimension tables | Planned |
| [Sprint 2](./sprint-02-fact-table.md) | Fact Table | fact_job_posting | Planned |
| [Sprint 3](./sprint-03-bridges.md) | Bridge Tables | 16 bridge tables | Planned |
| [Sprint 4](./sprint-04-aggregations.md) | Aggregations & Quality | 8 aggs + tests | Planned |

## Reference Documents

| Document | Description |
|----------|-------------|
| [Data Modeling](../gold-layer-modeling.md) | Star schema, table definitions, lineage |
| [Data Strategy](../gold-layer-data-strategy.md) | Volume analysis, refresh strategy |
| [dbt Implementation](../gold-layer-dbt-implementation.md) | Full Terraform + dbt implementation |
| [Risks Addressed](./risks-addressed.md) | Lambda size, cold starts, costs (summary) |

## Architecture

```
Silver (S3/Parquet)
       │
       ▼
┌─────────────────────────────────────────────────────┐
│              Redshift Serverless                    │
│  ┌─────────────┐    ┌─────────────────────────────┐│
│  │  Spectrum   │───→│  Gold Schema (dbt models)   ││
│  │  (external) │    │  - Dimensions               ││
│  └─────────────┘    │  - Facts                    ││
│        ↑            │  - Bridges                  ││
│        │            │  - Aggregations             ││
│   Glue Catalog      └─────────────────────────────┘│
└─────────────────────────────────────────────────────┘
       │
       ▼
    Website API
```

## Quick Stats

| Metric | Value |
|--------|-------|
| Total Tables | 81 |
| Dimensions | 55 (11 core + 3 snowflake + 27 AI + 14 bridge support) |
| Fact Tables | 1 |
| Bridge Tables | 16 |
| Aggregations | 8 |
| Estimated Cost | ~$37-47/month |
