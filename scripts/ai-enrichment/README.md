# AI Enrichment Scripts

Scripts para testar e analisar o pipeline de AI enrichment de job postings.

## 📁 Estrutura

```
scripts/
├── ai-enrichment/          ← Scripts de AI enrichment
│   ├── test_enrichment_local.py         # Testa passes localmente
│   ├── analyze_extraction_details.py    # Analisa detalhes de extração
│   ├── analyze_test_results.md          # Resultados de análises
│   └── demo_comparison.py               # Comparação de versões
└── deploy.sh / test_api.sh  ← Scripts gerais de infra
```

## 🧪 Scripts Disponíveis

### test_enrichment_local.py
**Descrição**: Testa o pipeline de enrichment localmente sem usar AWS.

**Uso**:
```bash
# Testar Pass 1 (extraction)
python scripts/ai-enrichment/test_enrichment_local.py --pass1

# Testar Pass 2 (inference)
python scripts/ai-enrichment/test_enrichment_local.py --pass2

# Testar Pass 3 (analysis)
python scripts/ai-enrichment/test_enrichment_local.py --pass3
```

**O que verifica**:
- ✅ JSON válido retornado pelo LLM
- ✅ Campos obrigatórios presentes
- ✅ Enums com valores válidos
- ✅ Confidence scores entre 0.0-1.0
- ✅ Novos campos v3.3 (llm_genai_mentioned, career_development, etc.)

### analyze_extraction_details.py
**Descrição**: Analisa resultados de extração em detalhes.

**Uso**:
```bash
python scripts/ai-enrichment/analyze_extraction_details.py <result_file.json>
```

**Features**:
- Estatísticas de campos extraídos vs null
- Distribuição de valores enum
- Análise de confidence scores
- Identificação de padrões

### demo_comparison.py
**Descrição**: Compara diferentes versões do schema ou prompts.

**Uso**:
```bash
python scripts/ai-enrichment/demo_comparison.py --v1 result_v3.2.json --v2 result_v3.3.json
```

**Mostra**:
- Campos novos/removidos
- Diferenças em extrações
- Métricas de qualidade

### analyze_test_results.md
**Descrição**: Documentação de análises e resultados de testes anteriores.

## 📊 Schema v3.3 - Novos Campos

### Pass 1 (+2 campos AI/ML)
- `ext_llm_genai_mentioned` - Detecção de LLMs/GenAI
- `ext_feature_store_mentioned` - Detecção de feature stores

### Pass 2 (+5 campos career_development)
- `inf_growth_path_clarity` - Clareza do caminho de crescimento
- `inf_mentorship_signals` - Sinais de mentoria
- `inf_promotion_path_mentioned` - Menção a promoções
- `inf_internal_mobility_mentioned` - Mobilidade interna
- `inf_career_tracks_available` - Trilhas de carreira

### Pass 3 (+12 campos)
**tech_culture_assessment** (4):
- `anl_tech_culture_signals` - OSS, blogs, conferences
- `anl_dev_practices_mentioned` - Code review, CI/CD, etc.
- `anl_innovation_signals` - Nível de inovação
- `anl_tech_debt_awareness` - Consciência de tech debt

**stakeholders_and_leadership** (+3):
- `anl_team_composition` - Composição do time
- `anl_reporting_structure` - Estrutura de reporte
- `anl_cross_functional_embedded` - Time cross-functional

**company_context** (5):
- `anl_company_stage_inferred` - Estágio da empresa
- `anl_hiring_velocity` - Velocidade de contratação
- `anl_team_size_signals` - Tamanho do time
- `anl_funding_stage_signals` - Estágio de funding
- `anl_role_creation_type` - Tipo de criação da vaga

## 🔧 Desenvolvimento

Para adicionar novos scripts de enrichment, coloque-os nesta pasta e documente aqui.

### Convenções
- Use nomes descritivos: `test_*.py`, `analyze_*.py`, `compare_*.py`
- Adicione `--help` flag para mostrar uso
- Documente no topo do arquivo o que o script faz
- Atualize este README

### Flatteners e Validators (v3.3)

**Flatteners** convertem JSON nested → colunas flat:
- `extraction.py` - Pass 1: `ext_*` (57 colunas)
- `inference.py` - Pass 2: `inf_*` (36 colunas = 9 campos × 4 metadados)
- `analysis.py` - Pass 3: `anl_*` (48 colunas = 12 campos × 4 metadados)

**Validators** validam schema e confidence scores:
- `validate_extraction_response()` - Pass 1: enums, tipos, ranges
- `validate_inference_response()` - Pass 2: v3.3 structure (seniority_and_role + career_development)
- `validate_analysis_response()` - Pass 3: v3.3 structure (tech_culture_assessment + stakeholders_and_leadership + company_context)

## 📚 Referências

- Schema: [docs/planning/ai-enrichment/job-ai-enriched.json](../../docs/planning/ai-enrichment/job-ai-enriched.json)
- Prompts: [src/lambdas/ai_enrichment/enrich_partition/prompts/](../../src/lambdas/ai_enrichment/enrich_partition/prompts/)
- Changelog: Ver `changelog` no schema JSON
