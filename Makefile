TF_DIR=infra/environments/dev

# =============================================================================
# Modular Makefiles
# =============================================================================
include makefiles/build.mk
include makefiles/infra.mk
include makefiles/dev.mk
include makefiles/etl.mk
include makefiles/ai.mk

.PHONY: help secrets push up

# =============================================================================
# Core
# =============================================================================

help: ## Mostra este help
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

secrets: ## [Config] Sobe/atualiza segredos no SSM (env=dev por default)
	@bash infra/scripts/sync-ssm-secrets.sh dev

push: ## [Git] Add, commit e push (uso: make push m="mensagem")
	git add -A
	git commit -m "$(m)"
	git push

up: ## [Deploy] Sobe tudo: secrets + layer + skills-catalog + terraform
	make secrets
	make layer
	make skills-catalog
	cd $(TF_DIR) && terraform init
	cd $(TF_DIR) && terraform validate
	cd $(TF_DIR) && terraform apply
