TF_DIR=infra/environments/dev

.PHONY: help secrets layer init validate plan apply deploy clean destroy up

help: ## Mostra este help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

secrets: ## Sobe/atualiza segredos no SSM (env=dev por default)
	@bash infra/scripts/sync-ssm-secrets.sh dev

layer: ## Cria Lambda Layer com dependências Python
	@echo "🔨 Building Lambda Layer..."
	@bash infra/scripts/build-layer.sh

init: ## Inicializa Terraform
	cd $(TF_DIR) && terraform init

validate: ## Valida configuração Terraform
	cd $(TF_DIR) && terraform validate

plan: layer ## Roda terraform plan (com layer atualizado)
	cd $(TF_DIR) && terraform plan

apply: layer ## Aplica mudanças (com layer atualizado)
	cd $(TF_DIR) && terraform apply

deploy: apply ## Alias pra apply
	@true

clean: ## Remove arquivos gerados (layer)
	@echo "🧹 Cleaning up..."
	rm -rf infra/layers/python-deps/layer.zip
	rm -rf infra/layers/python-deps/python/

destroy: ## Destroi toda infraestrutura
	cd $(TF_DIR) && terraform destroy

up: ## Sobe tudo: secrets + layer + terraform init/validate/apply
	make secrets
	make layer
	cd $(TF_DIR) && terraform init
	cd $(TF_DIR) && terraform validate
	cd $(TF_DIR) && terraform apply
