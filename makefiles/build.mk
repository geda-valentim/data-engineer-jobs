# =============================================================================
# Build & Package
# =============================================================================

layer: ## [Build] Cria Lambda Layer com dependências Python
	@echo "🔨 Building Lambda Layer..."
	@bash infra/scripts/build-layer.sh

skills-catalog: ## [Build] Converte skills_catalog.yaml para JSON e cria zip para Glue
	@bash infra/scripts/build-skills.sh

clean: ## [Build] Remove arquivos gerados (layer, skills json, zip)
	@echo "🧹 Cleaning up..."
	rm -rf infra/layers/python-deps/layer.zip
	rm -rf infra/layers/python-deps/python/
	rm -f src/skills_detection/config/skills_catalog.json
	rm -f infra/modules/ingestion/skills_detection.zip
