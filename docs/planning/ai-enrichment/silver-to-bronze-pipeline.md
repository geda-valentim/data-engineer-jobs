# Plano: AI Enrichment Pipeline (Silver → Bronze)

> **Data**: 2025-12-12
> **Status**: ✅ IMPLEMENTAÇÃO CONCLUÍDA
> **Sprint**: 6 - Orquestração
> **Última Atualização**: 2025-12-12
> **Próximos passos**: `terraform init && terraform plan` no ambiente dev

## Objetivo

Pipeline que lê jobs do Silver, executa pass1/pass2/pass3 de AI enrichment via Bedrock, e salva resultados no Bronze com controle de concorrência e tracking granular.

## Decisões de Arquitetura

### Controle de Concorrência
- **Implementação**: Step Function gerencia locks via DynamoDB (AcquireLock/ReleaseLock states)
- **Motivo**: Evita duplicação de lógica e garante release mesmo em falhas
- **InvokeEnrichment**: Apenas inicia Step Functions, sem gerenciar locks

### Invocação por Pass
- **EnrichPartition**: Invocado 3x por job (uma para cada pass)
- **Input format**: `{pass_name: "pass1|pass2|pass3", job_data: {...}, pass1_result?: {...}, pass2_result?: {...}}`
- **Output format**: `{statusCode, extraction|inference|analysis, raw_response, model_id, success}`

### Caching Bronze
- **Implementação**: Cada pass verifica se resultado já existe no Bronze antes de chamar Bedrock
- **Funções**: `check_job_processed()` verifica existência, `read_bronze_result()` lê resultado cached
- **Resposta cached**: Inclui `cached: true` no output para tracking
- **Benefício**: Evita reprocessamento e custos desnecessários de Bedrock

## Progresso de Implementação

| Fase | Status | Descrição |
|------|--------|-----------|
| Fase 1 | ✅ CONCLUÍDA | Completar Handler Existente (Pass 2/3) |
| Fase 2 | ✅ CONCLUÍDA | Output Bronze |
| Fase 3 | ✅ CONCLUÍDA | DynamoDB Utils |
| Fase 4 | ✅ CONCLUÍDA | Orquestração (SQS, Invoke, Cleanup) |
| Fase 5 | ✅ CONCLUÍDA | Step Function ASL |
| Fase 6 | ✅ CONCLUÍDA | Terraform |

## Arquitetura Final

```
EventBridge ─────────────────────────────────────────────────────────────────────┐
(rate 1h)                                                                        │
    │                                                                            │
    ▼                                                                            │
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────────┐
│ Discover    │────▶│    SQS      │────▶│   Invoke    │────▶│        Step Function            │
│ Partitions  │     │  (FIFO+DLQ) │     │ Enrichment  │     │                                 │
└─────────────┘     └─────────────┘     └─────────────┘     │  AcquireLock (DynamoDB)         │
      │                                       │             │         │                       │
      ▼                                       │             │         ▼                       │
 ┌─────────┐                                  │             │  GetJobStatus → EvaluatePasses  │
 │ Silver  │                                  │             │         │                       │
 │(Parquet)│                                  │             │    ┌────┴────────┐              │
 └─────────┘                                  │             │    ▼             ▼              │
                                              │             │  Pass1 → Pass2 → Pass3          │
                                              │             │    │       │       │            │
                                              │             │    └───────┴───────┘            │
EventBridge ──────────────────────────────────┤             │         │                       │
(rate 15min)                                  │             │         ▼                       │
    │                                         │             │   ReleaseLock → Success         │
    ▼                                         │             └─────────────────────────────────┘
┌─────────────┐                               │                       │
│  Cleanup    │◀──────────────────────────────┘                       ▼
│   Locks     │  (on SF failure/timeout)              ┌──────────────────────────┐
└─────────────┘                                       │    Bronze (S3 JSON)      │
      │                                               │  ai_enrichment/{job_id}/ │
      ▼                                               │    ├── pass1-*.json      │
┌─────────────┐                                       │    ├── pass2-*.json      │
│  DynamoDB   │                                       │    └── pass3-*.json      │
│ (Semaphore) │                                       └──────────────────────────┘
└─────────────┘
```

## Arquivos Implementados

### Lambdas (`src/lambdas/ai_enrichment/`)

| Lambda | Arquivo | Descrição | Timeout |
|--------|---------|-----------|---------|
| DiscoverPartitions | `discover_partitions/handler.py` | Lista Silver, publica jobs no SQS | 60s |
| InvokeEnrichment | `invoke_enrichment/handler.py` | Recebe SQS, inicia Step Function (sem lock mgmt) | 30s |
| EnrichPartition | `enrich_partition/handler.py` | Executa pass individual via Bedrock, salva Bronze | 180s |
| CleanupLocks | `cleanup_locks/handler.py` | Remove locks órfãos | 30s |

### Shared Utilities (`src/lambdas/ai_enrichment/shared/`)

| Arquivo | Funções |
|---------|---------|
| `s3_utils.py` | `read_partition()`, `write_bronze_result()`, `check_job_processed()`, `read_bronze_result()`, `list_bronze_jobs()` |
| `dynamo_utils.py` | `acquire_lock()`, `release_lock()`, `get_job_status()`, `mark_pass_completed()`, etc. |
| `__init__.py` | Exporta todas as funções para import simplificado |

### Terraform (`infra/modules/ai_enrichment/`)

| Arquivo | Recursos |
|---------|----------|
| `dynamodb.tf` | Tabelas `Semaphore` + `Status` com GSI |
| `sqs.tf` | FIFO Queue + DLQ + CloudWatch Alarm |
| `step_function.tf` | State Machine + IAM Role |
| `step_function_definition.json` | ASL com 15 states |
| `eventbridge.tf` | Schedule discover (1h) + cleanup (15min) + SF failure |
| `lambdas.tf` | 4 Lambda functions + SQS trigger |
| `lambda_code.tf` | ZIP packaging de todos os handlers |
| `lambda.iam.tf` | Policies: S3, DynamoDB, SQS, Bedrock, Step Functions |
| `variables.tf` | 15 variáveis configuráveis |
| `outputs.tf` | ARNs e URLs dos recursos |

## DynamoDB Tables

### `AIEnrichmentSemaphore`
Controle de concorrência global (max N execuções simultâneas)

```json
{
  "LockName": "ProcessingLock",
  "currentlockcount": 3,
  "maxlockcount": 5,
  "job-123-abc": "2025-12-12T10:00:00Z",
  "job-456-def": "2025-12-12T10:01:00Z"
}
```

### `AIEnrichmentStatus`
Tracking de status por job com GSI `status-index`

```json
{
  "job_posting_id": "4325757965",
  "pass1": {"status": "COMPLETED", "completedAt": "...", "model": "mistral-large"},
  "pass2": {"status": "COMPLETED", "completedAt": "...", "model": "mistral-large"},
  "pass3": {"status": "COMPLETED", "completedAt": "...", "model": "mistral-large"},
  "overallStatus": "COMPLETED",
  "createdAt": "2025-12-12T10:00:00Z",
  "updatedAt": "2025-12-12T10:06:00Z"
}
```

## Step Function States

```
AcquireLock ──▶ GetJobStatus ──▶ EvaluatePasses
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
        AlreadyCompleted    CreateOrUpdateJobStatus    ExecutePass2/3
                                      │
                                      ▼
                               ExecutePass1 ──▶ UpdatePass1Status ──▶ ExecutePass2
                                      │                                    │
                                      ▼                                    ▼
                               MarkPass1Failed              UpdatePass2Status ──▶ ExecutePass3
                                      │                                              │
                                      ▼                                              ▼
                               ReleaseLockOnError                    UpdatePass3Status ──▶ ReleaseLock ──▶ Success
```

## S3 Output (Bronze)

```
s3://{BRONZE_BUCKET}/ai_enrichment/
├── {job_posting_id}/
│   ├── pass1-mistral-mistral-large-2407-v1-raw.txt
│   ├── pass1-mistral-mistral-large-2407-v1.json
│   ├── pass2-mistral-mistral-large-2407-v1-raw.txt
│   ├── pass2-mistral-mistral-large-2407-v1.json
│   ├── pass3-mistral-mistral-large-2407-v1-raw.txt
│   └── pass3-mistral-mistral-large-2407-v1.json
```

## Variáveis Terraform

| Variável | Default | Descrição |
|----------|---------|-----------|
| `max_concurrent_executions` | 5 | Limite do semáforo (ver Performance Tuning) |
| `sqs_batch_size` | 5 | Messages por invocação do InvokeEnrichment |
| `enrich_partition_timeout` | 180 | Timeout em segundos para cada pass |
| `max_partitions_per_run` | 10 | Partições por execução discover |
| `max_jobs_per_partition` | 100 | Jobs por partição |
| `discover_schedule_expression` | `rate(1 hour)` | Schedule do discover |
| `lock_timeout_minutes` | 30 | Timeout para lock órfão |
| `bedrock_model_pass1/2/3` | `openai.gpt-oss-120b-1:0` | Modelos Bedrock |

## Performance Tuning

### Throughput Estimado

| max_concurrent_executions | Jobs/min | Jobs/hora | 10k jobs em |
|---------------------------|----------|-----------|-------------|
| 5 (default) | ~0.5 | ~33 | ~300 horas |
| 10 | ~1.1 | ~66 | ~150 horas |
| 20 | ~2.2 | ~133 | ~75 horas |
| 50 | ~5.5 | ~333 | ~30 horas |

### Configuração Recomendada por Ambiente

```hcl
# DEV - conservador, baixo custo
max_concurrent_executions = 5
sqs_batch_size            = 1
enrich_partition_timeout  = 180

# STAGING - balanceado
max_concurrent_executions = 20
sqs_batch_size            = 5
enrich_partition_timeout  = 180

# PROD - alta throughput
max_concurrent_executions = 50
sqs_batch_size            = 10
enrich_partition_timeout  = 300
```

### Bedrock Quota

Antes de aumentar `max_concurrent_executions`, verifique o quota do Bedrock:
- Default: 100 RPM (requests per minute) para maioria dos modelos
- Cada job = 3 calls (pass1 + pass2 + pass3)
- Fórmula: `max_concurrent_executions <= bedrock_quota_rpm / 3`

### Retry Strategy (AcquireLock)

Step Function usa retry otimizado para lock acquisition:
- `IntervalSeconds: 1` - retry rápido inicial
- `MaxAttempts: 20` - múltiplas tentativas
- `BackoffRate: 1.2` - crescimento moderado
- `JitterStrategy: FULL` - evita thundering herd

### Circuit Breaker (Bedrock)

Proteção contra throttling em cascata:
- `circuit_breaker_failure_threshold: 5` - abre após 5 falhas consecutivas
- `circuit_breaker_recovery_timeout: 60` - tenta recuperar após 60s

Estados:
- **CLOSED**: operação normal, tracking de falhas
- **OPEN**: serviço indisponível, rejeita requests imediatamente
- **HALF_OPEN**: permite 1 request para testar recuperação

## Monitoramento

### CloudWatch Alarms

| Alarm | Threshold | Descrição |
|-------|-----------|-----------|
| DLQ Messages | > 10 | Jobs falharam e foram para DLQ |
| Error Rate | > 5% | Taxa de erro do EnrichPartition |
| Latency P99 | > 120s | Latência alta em Bedrock calls |
| SF Failures | > 5 (5min) | Step Function executions falhando |

### Dashboard

CloudWatch Dashboard criado automaticamente com:
- Invocations & Errors do EnrichPartition
- Duration P50/P99
- Step Function Executions (Started/Succeeded/Failed)
- SQS Queue depth e DLQ messages

### Configuração de Alertas

```hcl
# Habilitar notificações via SNS
alarm_sns_topic_arn = "arn:aws:sns:us-east-1:123456789:alerts"

# Customizar thresholds
dlq_alarm_threshold      = 10
error_rate_threshold     = 5
latency_p99_threshold_ms = 120000
```

## Custo Estimado

| Item | Custo |
|------|-------|
| Bedrock Pass1 | ~$0.007/job |
| Bedrock Pass2 | ~$0.008/job |
| Bedrock Pass3 | ~$0.015/job |
| DynamoDB | ~$0.0001/job |
| Step Function | ~$0.000025/execution |
| SQS | ~$0.0000004/message |
| Lambda | ~$0.0002/job |
| **Total** | **~$0.031/job** |

## Deploy

```bash
cd infra/environments/dev
terraform init
terraform plan -target=module.ai_enrichment
terraform apply -target=module.ai_enrichment
```

## Testes Locais

```bash
# Testar discover_partitions
cd src/lambdas/ai_enrichment
SILVER_BUCKET=data-engineer-jobs-silver python -c "from discover_partitions.handler import handler; print(handler({}, None))"

# Testar enrich_partition Pass 1 (requer Bedrock)
cd src/lambdas/ai_enrichment
PYTHONPATH=. python -c "
from enrich_partition.handler import handler
import json
event = {
    'pass_name': 'pass1',
    'job_data': {
        'job_posting_id': 'test-123',
        'job_title': 'Data Engineer',
        'company_name': 'Test Corp',
        'job_location': 'Remote',
        'job_description': 'We need a Data Engineer...'
    },
    'execution_id': 'test-exec-001'
}
result = handler(event, None)
print(json.dumps(result, indent=2, default=str))
"
```

## Event Formats

### EnrichPartition Input (from Step Function)

```json
{
    "pass_name": "pass1",
    "job_data": {
        "job_posting_id": "4325757965",
        "job_title": "Data Engineer",
        "company_name": "Acme Corp",
        "job_location": "Remote",
        "job_description": "..."
    },
    "pass1_result": {},
    "pass2_result": {},
    "execution_id": "job-4325757965-abc123"
}
```

### EnrichPartition Output (to Step Function)

```json
{
    "statusCode": 200,
    "success": true,
    "extraction": {"skills": [...], "experience": {...}},
    "raw_response": "...",
    "model_id": "openai.gpt-oss-120b-1:0",
    "tokens": {"input": 1500, "output": 800},
    "cost_usd": 0.00045
}
```
