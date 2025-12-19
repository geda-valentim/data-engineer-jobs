# =============================================================================
# Terraform Infrastructure
# =============================================================================

init: ## [Infra] Inicializa Terraform
	cd $(TF_DIR) && terraform init

validate: ## [Infra] Valida configuração Terraform
	cd $(TF_DIR) && terraform validate

plan: layer skills-catalog ## [Infra] Roda terraform plan (com layer atualizado)
	cd $(TF_DIR) && terraform plan

apply: layer skills-catalog ## [Infra] Aplica mudanças (com layer atualizado)
	cd $(TF_DIR) && terraform apply

deploy: apply ## [Infra] Alias pra apply
	@true

destroy: ## [Infra] Destroi toda infraestrutura
	cd $(TF_DIR) && terraform destroy
