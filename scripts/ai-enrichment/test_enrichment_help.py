"""
Test Enrichment Help - Exemplos de Uso
Documentação completa para o script de teste de AI Enrichment.
"""

HELP_TEXT = """
═══════════════════════════════════════════════════════════════════════════════
                    AI ENRICHMENT TEST - GUIA DE USO
═══════════════════════════════════════════════════════════════════════════════

TESTES DISPONÍVEIS
──────────────────────────────────────────────────────────────────────────────

1. --pass1           Testa Pass 1 (extração de dados explícitos)
2. --pass2           Testa Pass 2 (inferência e normalização)
3. --compare         Compara Pass 1 com múltiplos jobs
4. --bedrock-only    Testa apenas conectividade Bedrock
5. --s3-only         Testa apenas acesso S3

OPÇÕES GERAIS
──────────────────────────────────────────────────────────────────────────────

--s3-source          Usa jobs reais do S3 bucket (em vez de mocks)
--date YYYY-MM-DD    Especifica partição (pega última hora do dia)
--limit N            Número de jobs a processar (padrão: 5)
--cache              Habilita cache em níveis (Pass 1 + Pass 2)

═══════════════════════════════════════════════════════════════════════════════
                            EXEMPLOS DE USO
═══════════════════════════════════════════════════════════════════════════════

📌 EXEMPLO 1: Testar Pass 1 com job de exemplo
──────────────────────────────────────────────────────────────────────────────
  python scripts/ai-enrichment/test_enrichment_local.py --pass1

  O que faz:
  • Executa Pass 1 com job hardcoded de exemplo
  • Mostra campos extraídos (ext_*)
  • Exibe tokens usados e custo (~$0.0012/job)

  Output esperado:
  • ext_must_have_hard_skills: ["Python", "SQL", "AWS", ...]
  • ext_salary_min: 180000
  • ext_years_experience_min: 5
  • Total cost: $0.001234

──────────────────────────────────────────────────────────────────────────────

📌 EXEMPLO 2: Testar Pass 1 com jobs reais do S3 + Cache
──────────────────────────────────────────────────────────────────────────────
  python scripts/ai-enrichment/test_enrichment_local.py \
    --compare \
    --s3-source \
    --date=2025-12-05 \
    --limit=10 \
    --cache

  O que faz:
  • Carrega 10 jobs da partição 2025-12-05 (hora mais recente)
  • Executa Pass 1 para cada job
  • Salva resultados no cache (.cache/enrichment/)
  • Mostra tabela comparativa de extração

  Output esperado:
  • Tabela comparando os 10 jobs lado a lado
  • Cache Hits: 0, Cache Misses: 10 (primeira execução)
  • Total Cost: ~$0.012 (10 jobs × $0.0012)

  Segunda execução (com cache):
  • Cache Hits: 10, Cache Misses: 0
  • Total Cost: $0.00 (tudo do cache!)

──────────────────────────────────────────────────────────────────────────────

📌 EXEMPLO 3: Testar Pass 2 (Inferência) com Cache
──────────────────────────────────────────────────────────────────────────────
  python scripts/ai-enrichment/test_enrichment_local.py \
    --pass2 \
    --s3-source \
    --date=2025-12-05 \
    --limit=5 \
    --cache

  O que faz:
  • Carrega 5 jobs da partição 2025-12-05
  • Tenta carregar Pass 1 do cache (se disponível)
  • Executa Pass 2 usando Pass 1 como input
  • Salva Pass 2 no cache
  • Mostra JSON RAW campo a campo + view formatada

  Output esperado:
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  RAW JSON EXTRACTION - Campo a Campo
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ### SENIORITY AND ROLE ###
    seniority_level:
      {
        "value": "senior",
        "confidence": 0.95,
        "evidence": "Title + 5-8 years experience",
        "source": "combined"
      }
    ...

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FORMATTED VIEW
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  --- Seniority and Role ---
    seniority_level: senior (conf: 0.95)
      Evidence: Title + 5-8 years experience

  Estatísticas:
  • Pass 1 Cache Hit Rate: 100% (5/5 do cache)
  • Pass 2 Cache Hit Rate: 0% (primeira execução)
  • Pass 2 Cost: ~$0.0018/job

──────────────────────────────────────────────────────────────────────────────

📌 EXEMPLO 4: Segunda execução Pass 2 (tudo do cache)
──────────────────────────────────────────────────────────────────────────────
  # Execute o mesmo comando novamente
  python scripts/ai-enrichment/test_enrichment_local.py \
    --pass2 \
    --s3-source \
    --date=2025-12-05 \
    --limit=5 \
    --cache

  O que faz:
  • Carrega Pass 1 do cache (instantâneo)
  • Carrega Pass 2 do cache (instantâneo)
  • Custo ZERO - tudo do cache!

  Output esperado:
  • Pass 1 Cache Hit Rate: 100% (5/5)
  • Pass 2 Cache Hit Rate: 100% (5/5)
  • Total Cost: $0.000000
  • Execução instantânea

──────────────────────────────────────────────────────────────────────────────

📌 EXEMPLO 5: Testar partição mais recente (sem especificar data)
──────────────────────────────────────────────────────────────────────────────
  python scripts/ai-enrichment/test_enrichment_local.py \
    --pass2 \
    --s3-source \
    --limit=3 \
    --cache

  O que faz:
  • Busca automaticamente a partição mais recente no S3
  • Carrega 3 jobs dessa partição
  • Executa Pass 1 + Pass 2

  Output esperado:
  • "Using most recent partition"
  • "Partition: 2025-12-06 Hour 14"

──────────────────────────────────────────────────────────────────────────────

📌 EXEMPLO 6: Teste de conectividade
──────────────────────────────────────────────────────────────────────────────
  # Testar apenas Bedrock
  python scripts/ai-enrichment/test_enrichment_local.py --bedrock-only

  # Testar apenas S3
  python scripts/ai-enrichment/test_enrichment_local.py --s3-only

  # Testar ambos (padrão quando nenhum teste é especificado)
  python scripts/ai-enrichment/test_enrichment_local.py

═══════════════════════════════════════════════════════════════════════════════
                          ENTENDENDO O CACHE
═══════════════════════════════════════════════════════════════════════════════

ESTRUTURA DO CACHE
──────────────────────────────────────────────────────────────────────────────
Diretório: scripts/ai-enrichment/.cache/enrichment/
Arquivo:   {job_posting_id}.json

Estrutura do arquivo:
{
  // Pass 1 fields
  "pass1_success": true,
  "ext_must_have_hard_skills": [...],
  "ext_salary_min": 180000,
  "total_tokens_used": 4523,
  ...

  // Pass 2 fields (adicionados quando Pass 2 é executado)
  "pass2_success": true,
  "pass2_result_raw": {
    "seniority_and_role": {...},
    "stack_and_cloud": {...},
    ...
  },
  "pass2_tokens": 8953,
  "pass2_input_tokens": 6234,
  "pass2_output_tokens": 2719,
  "pass2_cost": 0.001733
}

COMPORTAMENTO DO CACHE
──────────────────────────────────────────────────────────────────────────────
• Pass 1: Salva após execução bem-sucedida
• Pass 2: Salva no MESMO arquivo, fazendo merge com Pass 1
• Preservação: Ao salvar Pass 2, preserva Pass 1 existente
• Atualização: Ao salvar Pass 1, preserva Pass 2 existente (se houver)

BENEFÍCIOS DO CACHE EM NÍVEIS
──────────────────────────────────────────────────────────────────────────────
1. Economia de custo
   • Pass 1: ~$0.0012/job → $0.00 quando em cache
   • Pass 2: ~$0.0018/job → $0.00 quando em cache
   • Economia total: ~$0.003/job por re-execução

2. Velocidade
   • Execução LLM: 2-3 segundos/job
   • Leitura cache: <0.01 segundos/job
   • Speedup: ~200-300x

3. Iteração rápida
   • Teste Pass 2 múltiplas vezes sem re-executar Pass 1
   • Ajuste prompts sem custo adicional
   • Debug sem gastar tokens

LIMPEZA DE CACHE
──────────────────────────────────────────────────────────────────────────────
  # Limpar todo o cache
  rm -rf scripts/ai-enrichment/.cache/enrichment/*

  # Limpar cache de um job específico
  rm scripts/ai-enrichment/.cache/enrichment/{job_posting_id}.json

═══════════════════════════════════════════════════════════════════════════════
                          CUSTOS ESPERADOS
═══════════════════════════════════════════════════════════════════════════════

MODELO: openai.gpt-oss-120b-1:0 (via Amazon Bedrock)
──────────────────────────────────────────────────────────────────────────────

Pass 1 (Extração):
  Input:  ~3,500 tokens  → $0.0007
  Output: ~1,000 tokens  → $0.0005
  Total:  ~4,500 tokens  → $0.0012/job

Pass 2 (Inferência):
  Input:  ~6,200 tokens  → $0.0012
  Output: ~2,700 tokens  → $0.0006
  Total:  ~8,900 tokens  → $0.0018/job

Pass 1 + Pass 2:
  Total: ~13,400 tokens  → $0.0030/job

EXEMPLOS DE CUSTO TOTAL
──────────────────────────────────────────────────────────────────────────────
  5 jobs (Pass 1 + Pass 2):    ~$0.015
  10 jobs (Pass 1 + Pass 2):   ~$0.030
  100 jobs (Pass 1 + Pass 2):  ~$0.300
  1000 jobs (Pass 1 + Pass 2): ~$3.00

Com cache (re-execuções):     $0.00

═══════════════════════════════════════════════════════════════════════════════
                        FIELDS EXTRAÍDOS/INFERIDOS
═══════════════════════════════════════════════════════════════════════════════

PASS 1 - EXTRACTION (campos ext_*)
──────────────────────────────────────────────────────────────────────────────
Skills:
  • ext_must_have_hard_skills
  • ext_nice_to_have_hard_skills
  • ext_must_have_soft_skills
  • ext_nice_to_have_soft_skills
  • ext_certifications_mentioned

Experience:
  • ext_years_experience_min
  • ext_years_experience_max
  • ext_years_experience_text
  • ext_education_stated

Compensation:
  • ext_salary_disclosed
  • ext_salary_min, ext_salary_max
  • ext_salary_currency, ext_salary_period
  • ext_equity_mentioned
  • ext_benefits (array)

Work Model:
  • ext_work_model_stated
  • ext_employment_type_stated
  • ext_visa_sponsorship_stated

PASS 2 - INFERENCE (campos inf_*)
──────────────────────────────────────────────────────────────────────────────
Cada campo tem 4 metadados:
  • inf_{field}              → Valor inferido
  • inf_{field}_confidence   → Score 0.0-1.0
  • inf_{field}_evidence     → Justificativa
  • inf_{field}_source       → pass1_derived | inferred | combined

Seniority and Role (4 campos):
  • inf_seniority_level (senior, mid, junior, ...)
  • inf_job_family (data_engineer, analytics_engineer, ...)
  • inf_sub_specialty (batch_etl, streaming_realtime, ...)
  • inf_leadership_expectation (ic, tech_lead_ic, ...)

Stack and Cloud (5 campos):
  • inf_primary_cloud (aws, azure, gcp, ...)
  • inf_secondary_clouds (array)
  • inf_processing_paradigm (batch, streaming, hybrid)
  • inf_orchestrator_category (airflow_like, dagster_prefect, ...)
  • inf_storage_layer (warehouse, lake, lakehouse, ...)

Geo and Work Model (3 campos):
  • inf_remote_restriction (same_country, anywhere, ...)
  • inf_timezone_focus (americas, europe, apac, ...)
  • inf_relocation_required (boolean)

Visa and Authorization (3 campos):
  • inf_h1b_friendly (boolean)
  • inf_opt_cpt_friendly (boolean)
  • inf_citizenship_required (work_auth_only, us_citizen_only, ...)

Contract and Compensation (2 campos):
  • inf_w2_vs_1099 (w2, c2c, 1099, ...)
  • inf_benefits_level (comprehensive, standard, basic, ...)

Career Development (5 campos):
  • inf_growth_path_clarity (explicit, implied, vague, ...)
  • inf_mentorship_signals (explicit_yes, implied, ...)
  • inf_promotion_path_mentioned (boolean)
  • inf_internal_mobility_mentioned (boolean)
  • inf_career_tracks_available (array)

Requirements Classification (3 campos):
  • inf_requirement_strictness (low, medium, high)
  • inf_scope_definition (clear, vague, multi_role)
  • inf_skill_inflation_detected (boolean)

TOTAL: 25 inference fields × 4 metadata = 100 inf_* columns

═══════════════════════════════════════════════════════════════════════════════
                            TROUBLESHOOTING
═══════════════════════════════════════════════════════════════════════════════

ERRO: "No AWS credentials found"
──────────────────────────────────────────────────────────────────────────────
Solução:
  export AWS_REGION=us-east-1
  export AWS_PROFILE=your-profile
  # ou configure aws cli: aws configure

──────────────────────────────────────────────────────────────────────────────

ERRO: "No partitions found in S3 bucket"
──────────────────────────────────────────────────────────────────────────────
Solução:
  • Verifique se o bucket existe: data-engineer-jobs-silver
  • Verifique permissões S3
  • Liste manualmente: aws s3 ls s3://data-engineer-jobs-silver/linkedin/

──────────────────────────────────────────────────────────────────────────────

ERRO: "JSON parse error"
──────────────────────────────────────────────────────────────────────────────
Causa: LLM retornou texto antes/depois do JSON (ex: <reasoning>...</reasoning>)
Solução:
  • O parser tenta limpar automaticamente
  • Se persistir, verifique logs do LLM
  • Bug conhecido: algumas vezes o LLM adiciona tags XML

──────────────────────────────────────────────────────────────────────────────

ERRO: "Validation warnings"
──────────────────────────────────────────────────────────────────────────────
Causa: LLM não retornou todos os campos esperados
Solução:
  • Warnings não são fatais - o job ainda é processado
  • Campos faltantes ficam como None
  • Se muitos warnings, ajuste o prompt

═══════════════════════════════════════════════════════════════════════════════

Para mais informações:
  • Docs: docs/planning/ai-enrichment/
  • Schema: docs/planning/ai-enrichment/job-ai-enriched.json
  • Issues: https://github.com/your-repo/issues

═══════════════════════════════════════════════════════════════════════════════
"""


def show_help():
    """Print help text."""
    print(HELP_TEXT)


def show_quick_help():
    """Print quick help summary."""
    print("""
AI Enrichment Test - Quick Help
================================

Testes disponíveis:
  --pass1          Testa Pass 1 (extração)
  --pass2          Testa Pass 2 (inferência)
  --compare        Compara múltiplos jobs Pass 1

Opções:
  --s3-source      Usa jobs do S3 (em vez de mocks)
  --date DATE      Partição (YYYY-MM-DD)
  --limit N        Número de jobs (padrão: 5)
  --cache          Habilita cache em níveis

Exemplos:
  # Pass 1 com job de exemplo
  python scripts/ai-enrichment/test_enrichment_local.py --pass1

  # Pass 2 com 5 jobs do S3 + cache
  python scripts/ai-enrichment/test_enrichment_local.py --pass2 --s3-source --limit=5 --cache

Para ajuda completa:
  python scripts/ai-enrichment/test_enrichment_local.py --help
""")


if __name__ == "__main__":
    show_help()
