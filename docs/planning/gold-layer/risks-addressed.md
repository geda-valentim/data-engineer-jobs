# Implementation Risks Addressed

Common concerns raised about dbt + Redshift Serverless architecture, analyzed and validated.

---

## Summary

| Risk | Status | Resolution |
|------|--------|------------|
| Lambda Layer Size | **VALIDATED** | 75 MB actual, not 300 MB |
| dbt Package Downloads | **MITIGATED** | Avoid external packages |
| Cold Start Cascade | **ACCEPTABLE** | ~2 min realistic, not 3-5 min |
| VPC Endpoint Cost | **CORRECTED** | Single-AZ = $15, not $44 |
| Spectrum Re-scan Cost | **NOT CRITICAL** | ~$0.36/month at current scale |
| Incremental Duplicates | **ADDRESSED** | delete+insert strategy |

---

## Lambda Layer Size Limit (dbt + Redshift)

> **Common Concern**: dbt dependencies estimated at ~300 MB, exceeding the 250 MB Lambda layer limit.
>
> **Status**: **VALIDATED** - Layer fits comfortably within limits.

**Actual measurement (tested 2025-12):**

| Version | Unzipped | Zipped | Status |
|---------|----------|--------|--------|
| Original (all deps) | 173 MB | 59 MB | Under 250 MB limit |
| Optimized (no tests/cache) | 112 MB | 39 MB | Under 50 MB direct upload |
| **Minimal (recommended)** | **75 MB** | **29 MB** | **Best option** |

**Key insight**: dbt-redshift uses `redshift_connector` (not psycopg2), which is much lighter.

**Optimization removals for minimal layer:**
- `__pycache__`, `*.pyc`, `*.dist-info` (~10 MB)
- `psycopg2` (~11 MB) - not used by dbt-redshift
- `setuptools` (~10 MB) - not needed at runtime
- `babel` (~33 MB) - i18n only
- `networkx` (~18 MB) - lineage graph only (run locally with `dbt docs`)

**Verified packages in minimal layer:**
- dbt-core + dbt-redshift
- redshift_connector
- boto3, botocore
- jinja2, pydantic

**Conclusion**: Lambda is viable. No need for ECS/Fargate containers.

---

## dbt Package Downloads in VPC Lambda

> **Common Concern**: `dbt deps` downloads packages at runtime, failing in VPC Lambda without internet.
>
> **Status**: **MITIGATED** - Pre-install packages in layer OR avoid external packages.

**The problem:**
```
Lambda (VPC) → No Internet → dbt deps fails silently or times out
```

**Solution 1 - Pre-install packages (if needed):**
```bash
# build-dbt-layer.sh (CI/CD time, not runtime)
cd dbt_gold && dbt deps      # Download packages locally
zip -r dbt-project-layer.zip dbt_gold/  # Includes dbt_packages/
```

**Solution 2 - Avoid external packages (recommended):**

| Instead of | Use |
|------------|-----|
| `dbt_utils.surrogate_key()` | Custom 5-line macro |
| `dbt_utils.date_spine()` | Pre-populated dim_date seed |
| `dbt_expectations` | Built-in dbt tests |

**Handler rule:**
```python
# NEVER in Lambda
subprocess.run(['dbt', 'deps'])

# Packages already in layer
subprocess.run(['dbt', 'run', '--select', model])
```

**Conclusion**: Valid concern. Use Solution 2 (no external packages) for simplicity.

---

## Cold Start Cascade (Lambda VPC + Redshift Serverless)

> **Common Concern**: Combined cold starts could reach 3-5 minutes before first model runs.
>
> **Status**: **ACCEPTABLE** - Realistic worst case ~2 min, acceptable for 4-hour batch cycle.

**Cold start breakdown:**

| Component | Time | Notes |
|-----------|------|-------|
| Lambda VPC cold start | 10-30s | Includes ENI via Hyperplane (since 2019) |
| Redshift wake from idle | 30-90s | Longer if idle 8+ hours |
| First query compilation | 15-30s | Redshift query planning |
| **Realistic worst case** | **~90-150s** | Not 3-5 min as sometimes estimated |

**Hidden issue**: If Redshift idle 8+ hours, warmup step (180s timeout) may be insufficient.

**Solution**: Increase warmup timeout to 300s (simple) or accept delay (4-hour batch tolerates this).

```json
"WarmupRedshift": {
  "TimeoutSeconds": 300,
  "Retry": [{"MaxAttempts": 2, "BackoffRate": 2}]
}
```

**Why NOT use separate warmup Lambda 5 min before?**
- Over-engineering for a batch job
- 2-3 min delay is ~1% of 4-hour cycle
- Retries handle edge cases

**Conclusion**: Increase timeout to 300s. Don't over-engineer.

---

## VPC Endpoint Cost (Per-AZ Pricing)

> **Common Concern**: Interface endpoints are charged per-AZ, actual cost ~$44/month not ~$14.
>
> **Status**: **CORRECTED** - Use single-AZ for cost optimization.

**Pricing reality:**

| Configuration | Calculation | Monthly Cost |
|---------------|-------------|--------------|
| 3 AZs (full HA) | 2 endpoints × 3 AZs × $7.30 | **$43.80** |
| **1 AZ (recommended)** | 2 endpoints × 1 AZ × $7.30 | **$14.60** |
| NAT Gateway | $32 + data transfer | $35-50+ |

**Single-AZ tradeoff:**
- If endpoint's AZ fails → Lambda can't log or authenticate
- Impact: Job fails, retries next 4-hour cycle
- Acceptable for batch workload (not real-time)

**Terraform fix:**
```hcl
resource "aws_vpc_endpoint" "logs" {
  subnet_ids = [var.private_subnet_ids[0]]  # Single AZ only
}

resource "aws_vpc_endpoint" "secretsmanager" {
  subnet_ids = [var.private_subnet_ids[0]]  # Same AZ as logs
}
```

**Updated cost estimate:**

| Component | Monthly Cost |
|-----------|--------------|
| Redshift Serverless (8 RPU base) | $19-29 |
| VPC Endpoints (single-AZ) | ~$15 |
| Lambda | ~$1 |
| S3/Glue | ~$2 |
| **Total** | **~$37-47/month** |

**Conclusion**: Use single-AZ endpoints. Full HA not needed for 4-hour batch.

---

## Redshift Spectrum Re-scan Cost

> **Common Concern**: Spectrum re-scans Silver data for each dbt model, multiplying costs.
>
> **Status**: **NOT CRITICAL** - Current data size makes this negligible.

**Current Silver layer size**: ~364 MB total

**With partition pruning** (4-hour incremental windows):
- Scan per model: ~5-10 MB (filtered by `ingestion_timestamp`)
- 81 models × $5/TB = **~$0.002 per run**
- 6 runs/day × 30 days = **~$0.36/month**

**Even without partition pruning** (full scan):
- 81 models × 364 MB × $5/TB = **~$0.15 per run**
- 6 runs/day × 30 days = **~$27/month**

**Conclusion**: Not worth optimizing until Silver exceeds 10 GB.

---

## Incremental Model Duplicates

> **Common Concern**: Default dbt incremental strategy (`append`) creates duplicates on re-runs.
>
> **Status**: **ADDRESSED** - Using `delete+insert` strategy with predicates.

**Solution implemented:**
```sql
{{ config(
    materialized='incremental',
    unique_key='job_posting_id',
    incremental_strategy='delete+insert',
    incremental_predicates=[
        "DBT_INTERNAL_DEST.posted_at >= (SELECT MIN(posted_at) FROM DBT_INTERNAL_SOURCE)"
    ]
) }}
```

This deletes matching records before inserting, preventing duplicates while maintaining partition efficiency.

---

## VPC Endpoints: What's Actually Required?

| Endpoint | Type | Required? | Why |
|----------|------|-----------|-----|
| **S3** | Gateway | YES (FREE) | dbt reads Silver data via Spectrum |
| **CloudWatch Logs** | Interface | YES (~$7) | Lambda logging in VPC |
| **Secrets Manager** | Interface | OPTIONAL | Only if NOT using IAM auth |
| **Glue Catalog** | NOT NEEDED | - | Redshift Spectrum uses AWS internal network |

**Key insight**: Redshift Spectrum connects to Glue/S3 through AWS's internal network, not through your VPC. No Glue VPC endpoint required.

---

## Cost Summary

| Component | Monthly Cost |
|-----------|--------------|
| Redshift Serverless (8 RPU, ~1-2hr/day) | $19-29 |
| VPC Endpoints (single-AZ) | ~$7-15 |
| Lambda | ~$1 |
| S3/Glue/Spectrum | ~$2-3 |
| **Total** | **~$29-48/month** |
