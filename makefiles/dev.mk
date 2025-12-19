# =============================================================================
# Dev Tools (Local)
# =============================================================================

JAVA_HOME ?= /usr/lib/jvm/java-17-openjdk-amd64

graphql: ## [Dev] Inicia GraphQL server local sobre Delta Lake
	PYTHONPATH=. JAVA_HOME=$(JAVA_HOME) python src/dev/graphql/server.py

delta-bronze-to-silver: ## [Dev] Processa Bronze -> Silver Delta Lake
	PYTHONPATH=. JAVA_HOME=$(JAVA_HOME) python src/dev/deltalake/bronze_to_silver_enriched_jobs.py
