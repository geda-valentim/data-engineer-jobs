# Skills Detection - Documentação

## 📋 Visão Geral

Este conjunto de documentos planeja a implementação de um script Python para detectar skills técnicas em vagas de Data/Software Engineers a partir de arquivos Parquet.

## 📚 Documentos Disponíveis

### 1. [skills_detection_plan.md](skills_detection_plan.md)
**Planejamento Completo do Script**

Conteúdo:
- ✅ Análise dos dados disponíveis (campos do Parquet)
- ✅ Estratégias de extração (Regex, NER, Híbrida)
- ✅ Arquitetura proposta (módulos, fluxo de dados)
- ✅ Formato de outputs (JSON, CSV, Matriz)
- ✅ Catálogo de skills em YAML
- ✅ Implementação faseada (MVP → Avançado)
- ✅ Métricas de sucesso
- ✅ Exemplo de uso

**Leia primeiro este documento para entender a arquitetura completa.**

### 2. [skills_detection_insights.md](skills_detection_insights.md)
**Análise do Dataset Atual**

Conteúdo:
- ✅ Top 25 skills identificadas no dataset atual
- ✅ Insights sobre demanda (Azure domina com 77%)
- ✅ Recomendações específicas baseadas em dados reais
- ✅ Skills ausentes/raras
- ✅ Perfil de vaga "típica"
- ✅ Métricas de validação

**Leia este documento para entender o contexto dos dados reais.**

## 🎯 Resumo Executivo

### Dados Disponíveis
- **36 vagas** de Data/Software Engineer
- **35 vagas completas** (97%) com descrições
- **Fonte**: LinkedIn (arquivos Parquet no `tmp/`)

### Skills Mais Demandadas (Top 10)
1. **Azure** - 77%
2. **Spark** - 74%
3. **ETL** - 71%
4. **Python** - 63%
5. **CI/CD** - 46%
6. **Databricks** - 43%
7. **SQL** - 40%
8. **AWS** - 40%
9. **GCP** - 40%
10. **DevOps** - 37%

### Abordagem Recomendada
**Híbrida (MVP = Regex)**
- Fase 1: Regex pattern matching (rápido, 50-100 skills)
- Fase 2: Normalização e agregação
- Fase 3: ML/NER para skills emergentes

### Estrutura do Script Proposto
```
src/skills_detection/
├── config/
│   └── skills_catalog.yaml      # 100+ skills categorizadas
├── extractors/
│   ├── regex_extractor.py       # MVP - extração por padrões
│   └── ner_extractor.py         # Fase 3 - ML
├── normalizers/
│   └── skill_normalizer.py      # "ADF" → "Azure Data Factory"
├── processors/
│   └── job_processor.py         # Processa cada vaga
└── main.py                       # CLI principal
```

### Outputs Esperados
1. **skills_detected.csv** - Tabela de skills por vaga
2. **skills_ranking.csv** - Frequência e percentuais
3. **skills_matrix.parquet** - Matriz vaga-skill (análise)

## 🚀 Próximos Passos

### Para Começar a Implementação

1. **Criar catálogo de skills**
   ```bash
   mkdir -p src/skills_detection/config
   # Criar skills_catalog.yaml com 100+ skills
   ```

2. **Implementar extrator regex (MVP)**
   ```bash
   # Criar regex_extractor.py
   # Testar com 5 vagas manualmente
   ```

3. **Script principal**
   ```bash
   python src/skills_detection/main.py \
     --input tmp/*.parquet \
     --output results/skills_detected.csv
   ```

4. **Validar resultados**
   - Verificar 10 vagas manualmente
   - Calcular precisão (falsos positivos < 5%)
   - Ajustar patterns conforme necessário

### Métricas de Sucesso - MVP
- ✓ Cobertura: >90% das vagas com skills detectadas
- ✓ Diversidade: >50 skills únicas identificadas
- ✓ Precisão: <5% falsos positivos (validação manual)

## 💡 Decisões de Design

### Por que Regex primeiro?
- ✅ Simples e rápido para validar conceito
- ✅ Não requer ML/modelos pesados
- ✅ Fácil de debugar e ajustar
- ✅ Suficiente para 80% dos casos

### Por que YAML para catálogo?
- ✅ Legível por humanos
- ✅ Fácil de expandir/manter
- ✅ Suporta hierarquia (Azure → sub-skills)
- ✅ Versionável no Git

### Por que múltiplos outputs?
- **CSV**: Para análise rápida em Excel/Pandas
- **JSON**: Para integração com APIs/apps
- **Parquet**: Para análise eficiente de grandes volumes

## 📊 Exemplo de Resultado Esperado

### skills_ranking.csv
```csv
skill,category,frequency,percentage
Azure,cloud_platform,27,77.1%
Spark,data_processing,26,74.3%
Python,programming_language,22,62.9%
SQL,query_language,14,40.0%
```

### skills_detected.json (amostra)
```json
{
  "job_posting_id": "4319177210",
  "job_title": "Azure Data Engineer - MS Fabric",
  "company": "Gravity Infosolutions",
  "skills": [
    {"name": "Azure Data Factory", "category": "cloud_tools"},
    {"name": "Python", "category": "programming_language"},
    {"name": "Spark", "category": "data_processing"}
  ],
  "skill_count": 15
}
```

## 🔗 Links Úteis

- Dataset: `tmp/part-00000-*.parquet`
- Planejamento: [skills_detection_plan.md](skills_detection_plan.md)
- Insights: [skills_detection_insights.md](skills_detection_insights.md)

## 📝 Notas

- **Dataset atual**: 36 vagas (amostra)
- **Viés**: 77% Azure-focused (pode não ser representativo do mercado geral)
- **Idioma**: Descrições em inglês (verificar se haverá PT-BR no futuro)

---

**Versão**: 1.0
**Data**: 2025-12-03
**Status**: 📝 Planejamento concluído, implementação pendente
