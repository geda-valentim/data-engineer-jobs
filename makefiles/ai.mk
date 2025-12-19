# =============================================================================
# AI Enrichment Local Testing
# =============================================================================

# Helper for comma in Make conditionals
comma := ,

test-ai: ## [AI Local] Roda testes locais do AI Enrichment pipeline
	cd tests/ai_enrichment && python test_local.py

test-ai-circuit: ## [AI Local] Testa Circuit Breaker
	cd tests/ai_enrichment && python test_local.py TestCircuitBreaker

test-ai-dynamo: ## [AI Local] Testa DynamoDB Utils
	cd tests/ai_enrichment && python test_local.py TestDynamoUtils

test-ai-discover: ## [AI Local] Testa Discover Partitions
	cd tests/ai_enrichment && python test_local.py TestDiscoverPartitions

test-ai-enrich: ## [AI Local] Testa Enrich Partition Handler
	cd tests/ai_enrichment && python test_local.py TestEnrichPartitionHandler

test-ai-integration: ## [AI Local] Testa fluxo completo de integração
	cd tests/ai_enrichment && python test_local.py TestIntegrationFlow

# =============================================================================
# AI Enrichment AWS (Lambda Invocation)
# =============================================================================

ai-list-jobs: ## [AI AWS] Lista job IDs disponíveis para teste (uso: make ai-list-jobs n=10)
	@echo "📋 [AI Enrichment] Listing sample job IDs from Silver..."
	@python3 -c "\
import awswrangler as wr; \
import re; \
bucket = 'data-engineer-jobs-silver'; \
files = wr.s3.list_objects(f's3://{bucket}/linkedin/', suffix='.parquet')[:1]; \
partition = '/'.join(re.findall(r'(year=\d+|month=\d+|day=\d+|hour=\d+)', files[0])) if files else ''; \
df = wr.s3.read_parquet(files[0], columns=['job_posting_id', 'job_title', 'company_name', 'url']) if files else None; \
n = $(or $(n),10); \
print(f'\\n📁 Partition: {partition}') if partition else None; \
print(f'🔍 Found {len(df)} jobs. Showing {n}:\\n') if df is not None else print('No data'); \
[print(f\"  {row['job_posting_id']}  {row['company_name'][:25]:<25}  {row['job_title'][:35]:<35}  {row['url']}\") for _, row in df.head(n).iterrows()] if df is not None else None; \
print(f'\\n💡 Usage: make ai-enrich-job id={df.iloc[0][\"job_posting_id\"]}') if df is not None and len(df) > 0 else None; \
"

ai-discover: ## [AI AWS] Descobre partições pendentes de enrichment (uso: make ai-discover)
	@echo "🔍 [AI Enrichment] Discovering pending partitions..."
	aws lambda invoke --function-name data-engineer-jobs-dev-discover-partitions \
		--payload '{}' \
		--cli-binary-format raw-in-base64-out \
		--cli-read-timeout 120 \
		/dev/stdout | jq

ai-discover-dry: ## [AI AWS] Descobre partições SEM publicar no SQS (uso: make ai-discover-dry)
	@echo "🔍 [AI Enrichment] Discovering partitions (dry-run, no SQS)..."
	aws lambda invoke --function-name data-engineer-jobs-dev-discover-partitions \
		--payload '{"dry_run": true}' \
		--cli-binary-format raw-in-base64-out \
		--cli-read-timeout 120 \
		/dev/stdout | jq

ai-enrich-job: ## [AI AWS] Enriche um job via Step Function (uso: make ai-enrich-job id=4325757965 [force=true])
	@python3 scripts/fetch_and_enrich.py $(id) $(if $(filter true,$(force)),--force,)

ai-enrich-pass: ## [AI AWS] Executa um pass específico (uso: make ai-enrich-pass id=4325757965 pass=pass1 [force=true])
	@python3 scripts/fetch_and_enrich.py $(id) --pass $(pass) $(if $(filter true,$(force)),--force,)

ai-cleanup: ## [AI AWS] Limpa locks órfãos no DynamoDB (uso: make ai-cleanup)
	@echo "🧹 [AI Enrichment] Cleaning up stale locks..."
	aws lambda invoke --function-name data-engineer-jobs-dev-cleanup-locks \
		--payload '{}' \
		--cli-binary-format raw-in-base64-out \
		/dev/stdout | jq

ai-queue-status: ## [AI AWS] Mostra status da fila SQS de enrichment
	@echo "📊 [AI Enrichment] SQS Queue Status..."
	@aws sqs get-queue-attributes \
		--queue-url $$(aws sqs list-queues --query "QueueUrls[?contains(@,'ai-enrichment')] | [0]" --output text) \
		--attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible ApproximateNumberOfMessagesDelayed \
		| jq '.Attributes | {pending: .ApproximateNumberOfMessages, in_flight: .ApproximateNumberOfMessagesNotVisible, delayed: .ApproximateNumberOfMessagesDelayed}'

ai-executions: ## [AI AWS] Lista execuções recentes do Step Function (uso: make ai-executions status=RUNNING|SUCCEEDED|FAILED)
	@echo "📋 [AI Enrichment] Recent Step Function executions..."
	@aws stepfunctions list-executions \
		--state-machine-arn $$(aws stepfunctions list-state-machines --query "stateMachines[?contains(name,'ai-enrichment')].stateMachineArn" --output text) \
		--status-filter $(or $(status),RUNNING) \
		--max-results 20 \
		--query 'executions[].{name: name, status: status, startDate: startDate}' \
		| jq
