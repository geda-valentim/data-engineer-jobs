TF_DIR=infra/environments/dev

.PHONY: help secrets layer skills-catalog init validate plan apply deploy clean destroy up graphql delta-bronze-to-silver

help: ## Mostra este help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

secrets: ## Sobe/atualiza segredos no SSM (env=dev por default)
	@bash infra/scripts/sync-ssm-secrets.sh dev

layer: ## Cria Lambda Layer com dependências Python
	@echo "🔨 Building Lambda Layer..."
	@bash infra/scripts/build-layer.sh

skills-catalog: ## Converte skills_catalog.yaml para JSON e cria zip para Glue
	@bash infra/scripts/build-skills.sh

init: ## Inicializa Terraform
	cd $(TF_DIR) && terraform init

validate: ## Valida configuração Terraform
	cd $(TF_DIR) && terraform validate

plan: layer skills-catalog ## Roda terraform plan (com layer atualizado)
	cd $(TF_DIR) && terraform plan

apply: layer skills-catalog ## Aplica mudanças (com layer atualizado)
	cd $(TF_DIR) && terraform apply

deploy: apply ## Alias pra apply
	@true

clean: ## Remove arquivos gerados (layer, skills json, zip)
	@echo "🧹 Cleaning up..."
	rm -rf infra/layers/python-deps/layer.zip
	rm -rf infra/layers/python-deps/python/
	rm -f src/skills_detection/config/skills_catalog.json
	rm -f infra/modules/ingestion/skills_detection.zip

destroy: ## Destroi toda infraestrutura
	cd $(TF_DIR) && terraform destroy

up: ## Sobe tudo: secrets + layer + skills-catalog + terraform init/validate/apply
	make secrets
	make layer
	make skills-catalog
	cd $(TF_DIR) && terraform init
	cd $(TF_DIR) && terraform validate
	cd $(TF_DIR) && terraform apply

# =============================================================================
# Dev Tools
# =============================================================================

JAVA_HOME ?= /usr/lib/jvm/java-17-openjdk-amd64

graphql: ## Inicia GraphQL server local sobre Delta Lake
	PYTHONPATH=. JAVA_HOME=$(JAVA_HOME) poetry run python src/dev/graphql/server.py

delta-bronze-to-silver: ## Processa Bronze -> Silver Delta Lake
	PYTHONPATH=. JAVA_HOME=$(JAVA_HOME) poetry run python src/dev/deltalake/bronze_to_silver_enriched_jobs.py
