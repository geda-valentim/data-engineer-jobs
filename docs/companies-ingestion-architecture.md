# Companies Ingestion Architecture

## Visao Geral

Fluxo assincrono para coletar informacoes de empresas do LinkedIn via Bright Data Companies Information API. O fluxo e acionado automaticamente quando vagas sao salvas no Bronze, com controle de deduplicacao via DynamoDB para evitar chamadas desnecessarias a API.

---

## Arquitetura

```
                                    +------------------------+
                                    |    Step Functions      |
                                    |   (Jobs Ingestion)     |
                                    +------------------------+
                                              |
                                              v
+------------------+              +------------------------+
|   Bright Data    |  snapshot   |   Lambda save_to_s3    |
|   Jobs API       | ----------> |   (existing)           |
+------------------+              +------------------------+
                                              |
                                    1. Salva job no Bronze
                                    2. Extrai company_id/url
                                              |
                                              v
                                  +------------------------+
                                  |   SQS companies-queue  |
                                  +------------------------+
                                              |
                                              v
                                  +------------------------+
                                  | Lambda companies_fetcher|
                                  +------------------------+
                                              |
                          +-------------------+-------------------+
                          |                                       |
                          v                                       v
              +------------------------+              +------------------------+
              |   DynamoDB             |              |   Bright Data          |
              |   companies-status     |              |   Companies API        |
              +------------------------+              +------------------------+
                          |                                       |
                          |  Check: ja buscou?                    |
                          |  - Sim + recente -> SKIP              |
                          |  - Nao/expirado  -> FETCH             |
                          |                                       v
                          |                           +------------------------+
                          +-------------------------->|   S3 Bronze            |
                            Update status             |   linkedin_companies/  |
                                                      +------------------------+
```

---

## Recursos AWS

### 1. SQS - Fila de Companies

**Queue Principal**: `{project_name}-companies-to-fetch`
- Visibility Timeout: 300s (5 min)
- Message Retention: 86400s (1 dia)
- Long Polling: 20s

**Dead Letter Queue**: `{project_name}-companies-to-fetch-dlq`
- Message Retention: 1209600s (14 dias)
- Redrive Policy: maxReceiveCount = 3

### 2. DynamoDB - Controle de Status

**Tabela**: `{project_name}-companies-status`
- Billing Mode: PAY_PER_REQUEST
- Partition Key: `company_id` (String)

**Schema**:

| Atributo | Tipo | Descricao |
|----------|------|-----------|
| `company_id` | S | PK - ID unico da empresa no LinkedIn |
| `company_url` | S | URL do perfil da empresa |
| `company_name` | S | Nome da empresa |
| `status` | S | "success", "failed", "pending" |
| `last_fetched_at` | S | ISO timestamp da ultima busca |
| `next_refresh_after` | S | ISO timestamp para proxima busca |
| `created_at` | S | Timestamp de criacao do registro |
| `updated_at` | S | Timestamp da ultima atualizacao |
| `last_error` | S | Mensagem de erro (se status=failed) |

### 3. Lambda - companies_fetcher

- **Runtime**: Python 3.12
- **Handler**: handler.handler
- **Timeout**: 120s
- **Memory**: 256MB
- **Reserved Concurrency**: 5 (rate limiting)
- **Trigger**: SQS (batch_size=1)

---

## Contratos de Dados

### Mensagem SQS (save_to_s3 -> companies_fetcher)

```json
{
  "company_id": "2209560",
  "company_url": "https://www.linkedin.com/company/m3bi",
  "company_name": "M3BI - A Zensar Company",
  "source": "job_ingestion",
  "first_seen_at": "2025-12-05T18:21:13Z"
}
```

### Registro DynamoDB

**Apos busca com sucesso**:
```json
{
  "company_id": "2209560",
  "company_url": "https://www.linkedin.com/company/m3bi",
  "company_name": "M3BI - A Zensar Company",
  "status": "success",
  "last_fetched_at": "2025-12-05T18:21:13Z",
  "next_refresh_after": "2026-06-03T18:21:13Z",
  "created_at": "2025-12-05T18:21:13Z",
  "updated_at": "2025-12-05T18:21:13Z",
  "last_error": null
}
```

**Apos falha**:
```json
{
  "company_id": "2209560",
  "status": "failed",
  "last_fetched_at": "2025-12-05T18:21:13Z",
  "next_refresh_after": "2025-12-06T18:21:13Z",
  "last_error": "HTTP 500 from Companies API",
  "updated_at": "2025-12-05T18:21:13Z"
}
```

### Response Bright Data Companies API

```json
{
  "id": "m3bi",
  "name": "M3BI - A Zensar Company",
  "company_id": "2209560",
  "country_code": "US,IN",
  "locations": ["7336 E Deer Valley Rd Suite 100 Scottsdale, AZ 85255, US"],
  "followers": 53156,
  "employees_in_linkedin": 370,
  "about": "M3bi is a next generation IT Services Company...",
  "specialties": "Testing Services, Program and Project Management...",
  "company_size": "501-1,000 employees",
  "organization_type": "Privately Held",
  "industries": "Information Technology & Services",
  "website": "https://www.m3bi.com/",
  "founded": 2010,
  "headquarters": "Scottsdale, AZ",
  "logo": "https://media.licdn.com/...",
  "similar": [...],
  "employees": [...],
  "timestamp": "2025-12-05T18:21:13.009Z"
}
```

---

## Estrutura S3 Bronze

```
s3://data-engineer-jobs-bronze/
  linkedin_companies/
    company_id=2209560/
      snapshot_2025-12-05.json
      snapshot_2026-06-05.json  (refresh apos 6 meses)
    company_id=90502798/
      snapshot_2025-12-05.json
```

---

## Regras de Refresh

| Condicao | Acao |
|----------|------|
| Registro nao existe | FETCH |
| status="success" E now < next_refresh_after | SKIP |
| status="success" E now >= next_refresh_after | FETCH (refresh 6 meses) |
| status="failed" | RETRY via SQS DLQ/reprocessamento |

**Periodo de refresh**: 180 dias (6 meses)

---

## Variaveis de Ambiente

### Lambda save_to_s3 (modificada)

| Variavel | Descricao |
|----------|-----------|
| `COMPANIES_QUEUE_URL` | URL da fila SQS companies |

### Lambda companies_fetcher (nova)

| Variavel | Descricao |
|----------|-----------|
| `COMPANIES_STATUS_TABLE` | Nome da tabela DynamoDB |
| `BRONZE_BUCKET_NAME` | Bucket Bronze para salvar |
| `BRIGHTDATA_API_KEY_PARAM` | SSM Parameter da API key |
| `BRIGHTDATA_COMPANIES_DATASET_ID` | `gd_l1vikfnt1wgvvqz95w` |
| `REFRESH_DAYS` | Dias ate proximo refresh (default: 180) |

---

## Observabilidade

### CloudWatch Metrics

| Metrica | Namespace | Descricao |
|---------|-----------|-----------|
| `CompanyFetchSuccess` | LinkedInCompanies | Empresas buscadas com sucesso |
| `CompanyFetchSkipped` | LinkedInCompanies | Empresas puladas (cache hit) |
| `CompanyFetchFailed` | LinkedInCompanies | Falhas na busca |

### Logs

- Lambda logs em `/aws/lambda/{function_name}`
- Structured logging com company_id, status, latency

---

## IAM Permissions

### Lambda companies_fetcher

```json
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:UpdateItem"
  ],
  "Resource": "arn:aws:dynamodb:*:*:table/{project}-companies-status"
}

{
  "Effect": "Allow",
  "Action": ["s3:PutObject"],
  "Resource": "arn:aws:s3:::{bronze-bucket}/linkedin_companies/*"
}

{
  "Effect": "Allow",
  "Action": ["ssm:GetParameter"],
  "Resource": "arn:aws:ssm:*:*:parameter/brightdata/*"
}

{
  "Effect": "Allow",
  "Action": [
    "sqs:ReceiveMessage",
    "sqs:DeleteMessage",
    "sqs:GetQueueAttributes"
  ],
  "Resource": "arn:aws:sqs:*:*:{project}-companies-to-fetch"
}
```

---

## Fluxo Detalhado

1. **save_to_s3** recebe snapshot de jobs da Bright Data
2. Salva jobs no Bronze (comportamento existente)
3. Para cada job no snapshot:
   - Extrai `company_id`, `company_url`, `company_name`
   - Se tem `company_id` OU `company_url`, envia mensagem SQS
4. **companies_fetcher** recebe mensagem SQS
5. Consulta DynamoDB pelo `company_id`
6. Se nao existe OU expirado:
   - Chama Bright Data Companies API
   - Salva JSON bruto no Bronze
   - Atualiza DynamoDB com status e proximo refresh
7. Se existe e nao expirado:
   - Skip (nao chama API)
   - Log para metricas

---

## Consideracoes FinOps

- **DynamoDB PAY_PER_REQUEST**: Custo proporcional ao uso
- **Reserved Concurrency = 5**: Limita chamadas paralelas a API
- **Refresh de 6 meses**: Reduz chamadas desnecessarias
- **Skip em cache**: Maioria das mensagens nao chama API externa
