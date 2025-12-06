# AI Enrichment Pipeline - Sprint Overview

> **Project:** Data Engineer Jobs Intelligence
> **Epic:** AI-Powered Job Enrichment
> **Created:** 2025-12-05
> **Architecture Reference:** [docs/ai-enrichment-architecture.md](../../ai-enrichment-architecture.md)

---

## Executive Summary

Implement a serverless AI enrichment pipeline using **Amazon Bedrock** to add structured metadata to LinkedIn job postings. The pipeline uses a **3-pass cascading context architecture** where each pass builds on the previous results.

**Primary Model:** `openai.gpt-oss-120b-1:0` - A 120B parameter open-source model available via Bedrock at extremely competitive pricing.

### Pipeline Flow

```
Silver (Parquet) → Pass 1 → Pass 2 → Pass 3 → Silver-AI (Parquet)
                   ↓         ↓         ↓
               Extraction  Inference  Analysis
               (factual)   (with      (complex,
                          confidence) red flags)
```

---

## Critical Constraint: No Budget for Reprocessing

> ⚠️ **CRITICAL:** O pipeline deve ser **tolerante a falhas por registro**, não por partição.
> Não há verba para reprocessamento massivo. Se 1 registro falhar, os demais **devem** continuar.

### Fault-Tolerance Design

```
┌──────────────────────────────────────────────────────────────┐
│                    REGRA DE OURO                              │
│                                                               │
│  ❌ Falha de 1 registro = Falha da partição inteira          │
│  ✅ Falha de 1 registro = Registro marcado, demais continuam  │
└──────────────────────────────────────────────────────────────┘
```

**Comportamento esperado:**
- **100 jobs na partição, 3 falham:** 97 enriquecidos + 3 com `pass{1,2,3}_success=False`
- **Partição sempre escrita:** Mesmo com falhas, Silver-AI recebe o arquivo
- **Retry individual:** Apenas registros com `pass1_success=False` podem ser reprocessados depois
- **Tracking de erros:** Coluna `enrichment_errors` guarda detalhes para debug

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Fault Tolerance** | **Per-record** | **No budget for reprocessing; failures marked individually** |
| State Management | S3 partition diff | Avoid DynamoDB; idempotent reprocessing |
| Orchestration | Step Functions + Lambda | Consistent with existing ingestion pipeline |
| Model | Configurable per pass | Flexibility for cost/quality trade-offs |
| IaC | Terraform modules | Existing pattern, reusable |
| Processing | Per-partition Lambda | Matches Silver hourly partitioning |
| Parquet Library | AWS SDK for Pandas | AWS managed layer, native S3 support |
| Testing | Live Bedrock | Local first with 1-3 rows per sprint |

### Bedrock Model Configuration

**Default: openai.gpt-oss-120b-1:0** (absurdly cheap for a 120B parameter model!)

| Model | Input | Output | Use Case |
|-------|-------|--------|----------|
| `openai.gpt-oss-120b-1:0` | $0.00015/1K | $0.0003/1K | **Primary** - All passes |
| `claude-3-haiku` | $0.00025/1K | $0.00125/1K | Fallback if needed |

```
BEDROCK_MODEL_PASS1 = "openai.gpt-oss-120b-1:0"   # Fast, extremely cheap
BEDROCK_MODEL_PASS2 = "openai.gpt-oss-120b-1:0"   # Inference
BEDROCK_MODEL_PASS3 = "openai.gpt-oss-120b-1:0"   # Analysis (120B params handles complex tasks)
```

---

## Sprint Overview

| Sprint | Focus | Deliverable | Duration |
|--------|-------|-------------|----------|
| 0 | Planning | Sprint documentation | 0.5 day |
| 1 | Foundation | Terraform, Lambda skeletons, Bedrock IAM | 2-3 days |
| 2 | Pass 1 | Factual extraction | 2-3 days |
| 3 | Pass 2 | Inference with cascading context | 2-3 days |
| 4 | Pass 3 | Complex analysis, full pipeline | 2-3 days |
| 5 | Integration | Step Functions, EventBridge, deploy | 3-4 days |

**Total: 12-16 days**

---

## Architecture Overview

### New Components

```
src/lambdas/ai_enrichment/
├── discover_partitions/    # Find unprocessed partitions
│   └── handler.py
├── enrich_partition/       # Process single partition
│   ├── handler.py
│   ├── bedrock_client.py   # Model invocation
│   ├── prompts/            # Pass 1, 2, 3 templates
│   ├── parsers/            # JSON parsing, validation
│   └── flatteners/         # Nested → flat columns
└── shared/
    └── s3_utils.py         # Parquet I/O

infra/modules/ai_enrichment/
├── lambda_*.tf             # Lambda resources
├── step_functions.tf       # Orchestration
├── eventbridge.tf          # Daily trigger
└── lambda.iam.tf           # Bedrock permissions
```

### Data Flow

```
EventBridge (daily)
       ↓
Step Functions
       ↓
DiscoverPartitions Lambda
       ↓
   [pending partitions]
       ↓
Map (MaxConcurrency=5)
       ↓
EnrichPartition Lambda
   ├─ Read Silver Parquet
   ├─ For each job:
   │    ├─ Pass 1: Extract facts
   │    ├─ Pass 2: Infer with context
   │    └─ Pass 3: Analyze with full context
   ├─ Merge columns
   └─ Write Silver-AI Parquet
```

---

## Output Schema

### Pass 1: Extraction (`ext_*` columns)
- Salary, visa, work model, skills, benefits
- Factual only - no inference

### Pass 2: Inference (`inf_*` columns)
- Seniority, cloud, geo, contract type
- Each field has `_confidence` and `_evidence`

### Pass 3: Analysis (`anl_*` columns)
- Data maturity, red flags, culture signals
- Summary with strengths/concerns/fit_for

### Metadata
- `enriched_at`, `enrichment_version`, `enrichment_cost_usd`
- `pass{1,2,3}_success`, `avg_confidence_pass{2,3}`

---

## Cost Estimates

### Model Pricing Comparison

| Model | Input/1K | Output/1K | 7K tokens/job |
|-------|----------|-----------|---------------|
| **openai.gpt-oss-120b-1:0** | **$0.00015** | **$0.0003** | **~$0.0006** |
| claude-3-haiku | $0.00025 | $0.00125 | ~$0.0035 |
| claude-3-sonnet | $0.003 | $0.015 | ~$0.045 |

**openai.gpt-oss-120b-1:0 is ~6x cheaper than Haiku and ~75x cheaper than Sonnet!**

### Per Job (openai.gpt-oss-120b-1:0)
| Pass | Input Tokens | Output Tokens | Cost |
|------|--------------|---------------|------|
| Pass 1 | ~1,200 | ~400 | ~$0.00030 |
| Pass 2 | ~1,800 | ~600 | ~$0.00045 |
| Pass 3 | ~2,200 | ~500 | ~$0.00048 |
| **Total** | ~5,200 | ~1,500 | **~$0.0012** |

### Monthly Projection (openai.gpt-oss-120b-1:0)
| Scenario | Jobs | Cost | vs Haiku |
|----------|------|------|----------|
| Dev testing | 100 | **~$0.12** | $0.35 |
| Backfill 20K | 20,000 | **~$24** | $70 |
| Weekly 5K | 5,000 | **~$6** | $18 |
| Monthly 20K | 20,000 | **~$24** | $70 |

---

## Sprint Documentation

- [Sprint 1: Foundation](sprint-1-foundation.md)
- [Sprint 2: Pass 1 - Extraction](sprint-2-pass1.md)
- [Sprint 3: Pass 2 - Inference](sprint-3-pass2.md)
- [Sprint 4: Pass 3 - Analysis](sprint-4-pass3.md)
- [Sprint 5: Integration](sprint-5-integration.md)

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Pass success rate | > 95% |
| Avg confidence (Pass 2) | > 0.70 |
| Avg confidence (Pass 3) | > 0.60 |
| Cost per job | < $0.002 (target ~$0.0012 with openai.gpt-oss-120b-1:0) |
| Partition processing | < 15 min |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Record failure stops partition** | **Per-record try/catch, always write partition** |
| Bedrock throttling | Exponential backoff, MaxConcurrency=5 |
| LLM hallucination | Anti-hallucination rules, `null` > guess |
| JSON parse errors | Robust parser, mark record as failed, continue |
| Cost overrun | Token tracking, CloudWatch alarms |
| Lambda timeout | 15min max, smaller partitions |
| **Reprocessing budget** | **None - fault tolerance is mandatory** |

### Fault-Tolerance Columns

| Column | Type | Purpose |
|--------|------|---------|
| `pass1_success` | bool | Pass 1 completed successfully |
| `pass2_success` | bool | Pass 2 completed successfully |
| `pass3_success` | bool | Pass 3 completed successfully |
| `enrichment_errors` | string | Error details for debugging |

**Query para identificar falhas:**
```sql
SELECT job_posting_id, enrichment_errors
FROM silver_ai
WHERE pass1_success = false
   OR pass2_success = false
   OR pass3_success = false
```
