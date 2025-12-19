# =============================================================================
# Lambda ETL Testing (Local)
# =============================================================================

test-etl: ## [ETL Local] Testa Lambda ETL localmente (uso: make test-etl y=2025 m=12 d=15 h=10)
	PYTHONPATH=src python scripts/test_lambda_etl_local.py --year $(y) --month $(m) --day $(d) --hour $(h) --dry-run

test-etl-run: ## [ETL Local] Executa Lambda ETL (escreve no Silver!) (uso: make test-etl-run y=2025 m=12 d=15 h=10)
	PYTHONPATH=src python scripts/test_lambda_etl_local.py --year $(y) --month $(m) --day $(d) --hour $(h)

test-etl-list: ## [ETL Local] Lista partições Bronze disponíveis
	PYTHONPATH=src python scripts/test_lambda_etl_local.py --list-partitions

# =============================================================================
# Bronze to Silver Backfill (AWS Lambda)
# =============================================================================

b2s-backfill-auto: ## [Bronze→Silver] Backfill automático: detecta partições faltantes (uso: make b2s-backfill-auto limit=50)
	aws lambda invoke --function-name data-engineer-jobs-bronze-to-silver-backfill \
		--payload '{"mode": "auto", "limit": $(or $(limit),50)}' \
		--cli-binary-format raw-in-base64-out \
		--cli-read-timeout 900 \
		/dev/stdout | jq

b2s-backfill-range: ## [Bronze→Silver] Backfill range de datas (uso: make b2s-backfill-range start=2025-12-01 end=2025-12-15)
	aws lambda invoke --function-name data-engineer-jobs-bronze-to-silver-backfill \
		--payload '{"start_date": "$(start)", "end_date": "$(end)"}' \
		--cli-binary-format raw-in-base64-out \
		--cli-read-timeout 900 \
		/dev/stdout | jq

b2s-backfill-partition: ## [Bronze→Silver] Backfill partição específica (uso: make b2s-backfill-partition p=2025/12/15/10)
	aws lambda invoke --function-name data-engineer-jobs-bronze-to-silver-backfill \
		--payload '{"partitions": ["$(p)"]}' \
		--cli-binary-format raw-in-base64-out \
		--cli-read-timeout 900 \
		/dev/stdout | jq

b2s-backfill-batch: ## [Bronze→Silver] Backfill em batch dia a dia (uso: make b2s-backfill-batch start=2025-11-01 end=2025-12-14)
	@echo "🚀 [Bronze→Silver] Starting batch backfill from $(start) to $(end)..."
	@current="$(start)"; \
	while [ "$$current" != "$$(date -d "$(end) + 1 day" +%Y-%m-%d)" ]; do \
		echo ""; \
		echo "========================================"; \
		echo "📅 Processing: $$current"; \
		echo "========================================"; \
		aws lambda invoke --function-name data-engineer-jobs-bronze-to-silver-backfill \
			--payload "{\"start_date\": \"$$current\", \"end_date\": \"$$current\"}" \
			--cli-binary-format raw-in-base64-out \
			--cli-read-timeout 900 \
			/dev/stdout | jq -c '{status, total_partitions, success, errors, total_records, duration_ms}'; \
		current=$$(date -d "$$current + 1 day" +%Y-%m-%d); \
		sleep 2; \
	done
	@echo ""
	@echo "✅ [Bronze→Silver] Batch backfill completed!"
