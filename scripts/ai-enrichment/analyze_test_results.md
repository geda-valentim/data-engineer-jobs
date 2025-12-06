# Análise Detalhada Pass 1 Extraction - Schema v3.3

**Data:** 2025-12-06
**Model:** openai.gpt-oss-120b-1:0
**Success Rate:** 5/5 (100.0%)
**Average Cost:** $0.001163 per job

---

## 1. Precision Technologies - Data Engineer (Cloud, ETL, Big Data, AI/ML Pipelines)

### Extração Realizada
```
✅ Success: True
📊 Compensation:
   - salary_min/max: None (not disclosed)
   - equity_mentioned: False

🛂 Work Authorization:
   - visa_sponsorship: not_mentioned ❌ ERRO
   - Texto original: "All immigration statuses accepted (No restrictions)"
   - **Deveria ser:** Algo mais preciso, não "not_mentioned"

🏢 Work Model:
   - work_model_stated: remote ✅
   - employment_type: not_mentioned

📝 Contract:
   - contract_type: permanent ✅

🛠️ Skills Classification:
   - must_have_hard_skills: 23 ❌ PROBLEMA
   - nice_to_have_hard_skills: 0
   - must_have_soft_skills: 0
   - nice_to_have_soft_skills: 0

💰 Benefits:
   - pto_policy: not_mentioned
```

### Avaliação
**Problemas Identificados:**
1. ❌ **Visa sponsorship:** Job diz "All immigration statuses accepted (No restrictions)" mas foi classificado como "not_mentioned". Deveria reconhecer como "will_sponsor" ou criar nova categoria "no_restrictions"
2. ❌ **Skills over-extraction:** Classificou **TODOS os 23 skills como must-have**, não fez distinção porque o job não tem seções explícitas de "Required" vs "Preferred"
3. ✅ **Work model e contract_type:** Extraiu corretamente

**Explicação:**
Job lista responsabilidades sem distinguir must-have vs nice-to-have. É esperado que tudo seja classificado como must-have, mas 23 skills é muito - deveria filtrar apenas as ferramentas principais.

---

## 2. IntagHire - Senior Python Data Engineer - GIS/Mapping

### Extração Realizada
```
✅ Success: True
📊 Compensation:
   - salary_min/max: None

🛂 Work Authorization:
   - visa_sponsorship: will_not_sponsor ✅ CORRETO
   - Texto: "unable to consider visa sponsorship or C2C"

🏢 Work Model:
   - work_model_stated: onsite ✅
   - Location: "100% onsite"

📝 Contract:
   - contract_type: not_mentioned ❌
   - Texto original diz "Full-time"

🛠️ Skills Classification:
   - must_have_hard_skills: 4 ✅ PERFEITO
   - nice_to_have_hard_skills: 10 ✅ PERFEITO
   - must_have_soft_skills: 0
   - nice_to_have_soft_skills: 0
```

### Avaliação
**✅ EXCELENTE - Melhor resultado dos 5 jobs!**

**Acertos:**
1. ✅ Visa sponsorship: Corretamente identificou "will_not_sponsor"
2. ✅ Work model: onsite detectado
3. ✅ **Skills classification PERFEITA:** Job tem seções explícitas:
   - "Must Have Skills" → 4 skills corretamente extraídos
   - "Good Skills to Have" → 10 skills corretamente extraídos

**Problema menor:**
- ❌ contract_type deveria ser "permanent" (job diz "Full-time")

---

## 3. Eames Consulting - Senior Data Engineer 🚨 CASO CRÍTICO

### Extração Realizada
```
✅ Success: True
📊 Compensation:
   - salary_min: $165,000 ✅
   - salary_max: $185,000 ✅
   - equity_mentioned: False

🛂 Work Authorization:
   - visa_sponsorship: not_mentioned

🏢 Work Model:
   - work_model_stated: remote ✅
   - Texto: "100% REMOTE"

📝 Contract:
   - contract_type: not_mentioned

🛠️ Skills Classification:
   - must_have_hard_skills: 0 ❌❌❌ TOTALMENTE ERRADO
   - nice_to_have_hard_skills: 29 ❌❌❌ TUDO CLASSIFICADO COMO NICE-TO-HAVE
   - must_have_soft_skills: 0 ❌
   - nice_to_have_soft_skills: 3 ✅ (Communication, Team Collaboration, Empathy)

📈 Experience:
   - years_experience_min: 6 ✅
   - years_experience_max: 8 ✅

💰 Benefits:
   - pto_policy: unlimited ✅
```

### Avaliação
**❌ FALHOU COMPLETAMENTE na classificação de skills!**

**O Problema:**
A seção se chama **"Preferred Qualifications"** mas contém qualificadores internos **FORTES**:

#### Texto Original vs Classificação Atual:
```
"Preferred Qualifications:
- Strong proficiency in SQL and Python         → DEVERIA SER: must_have
- Proven experience building pipelines          → DEVERIA SER: must_have
- Strong foundation in data modeling            → DEVERIA SER: must_have
- Hands-on experience with dbt                  → DEVERIA SER: must_have
- Experience implementing CI/CD                 → DEVERIA SER: must_have
- Familiarity with monitoring, alerting        → OK como nice_to_have
- Functional understanding of AI/automation    → OK como nice_to_have
- Strong communication and collaboration       → DEVERIA SER: must_have_soft_skills
```

**Classificação ATUAL (ERRADA):**
- must_have_hard: 0
- nice_to_have_hard: 29 (TUDO)

**Classificação ESPERADA:**
- must_have_hard: ~15-18 skills (todos com "strong", "proven", "hands-on", "experience")
- nice_to_have_hard: ~8-10 skills (apenas "familiarity", "functional understanding")

**Root Cause:**
O LLM está priorizando o título da seção **"Preferred Qualifications"** ao invés de analisar os **qualificadores internos** ("strong", "proven", "hands-on").

---

## 4. Amazon - Data Engineer III, ITA

### Extração Realizada
```
✅ Success: True
📊 Compensation:
   - salary_min: $139,100 ✅
   - salary_max: $240,500 ✅

🛂 Work Authorization:
   - visa_sponsorship: not_mentioned

🏢 Work Model:
   - work_model_stated: not_mentioned ❌
   - Location: Seattle, WA (deveria inferir "onsite" ou "hybrid")

📝 Contract:
   - contract_type: not_mentioned

🛠️ Skills Classification:
   - must_have_hard_skills: 9 ✅ CORRETO
   - nice_to_have_hard_skills: 4 ✅ CORRETO
   - must_have_soft_skills: 3 ✅ (Leadership, Mentoring, Team Collaboration)
   - nice_to_have_soft_skills: 0

📈 Experience:
   - years_experience_min: 5 ✅
   - years_experience_max: None
```

### Avaliação
**✅ BOM - Skills classification funcionou bem!**

**Acertos:**
1. ✅ Salary extraction perfeita
2. ✅ **Skills bem classificados:**
   - "Basic Qualifications" → must_have (9 skills)
   - "Preferred Qualifications" → nice_to_have (4 skills)
3. ✅ **Soft skills extraídos corretamente:** "Mentor junior engineers" → Leadership, Mentoring

**Problemas:**
- ❌ work_model deveria ser inferido do location (Seattle, WA)
- ❌ contract_type deveria ser "permanent" (job permanente na Amazon)

---

## 5. Microsoft - Member of Technical Staff - Data Engineer

### Extração Realizada
```
✅ Success: True
📊 Compensation:
   - salary_min: $139,900 ✅
   - salary_max: $304,200 ✅

🛂 Work Authorization:
   - visa_sponsorship: not_mentioned

🏢 Work Model:
   - work_model_stated: hybrid ✅
   - Texto: "4 days a week in office"

📝 Contract:
   - contract_type: not_mentioned (deveria ser "permanent")

🛠️ Skills Classification:
   - must_have_hard_skills: 5 ⚠️ PARCIALMENTE CORRETO
   - nice_to_have_hard_skills: 14 ⚠️ ALGUNS DEVERIAM SER MUST-HAVE
   - must_have_soft_skills: 0
   - nice_to_have_soft_skills: 0

📈 Experience:
   - years_experience_min: 6 ✅
   - years_experience_max: None
```

### Avaliação
**⚠️ PARCIAL - Skills classification com problemas**

**Problemas:**
1. ⚠️ "Required Qualifications" tem mais skills do que os 5 extraídos
2. ⚠️ "Preferred Qualifications" tem alguns skills que deveriam ser must-have:
   - "4+ years experience with Python, Java, Spark, SQL" → deveria ser must_have
   - "Experience with data governance" → deveria ser must_have

---

## Resumo Comparativo por Campo

| Campo | Precision | IntagHire | Eames | Amazon | Microsoft |
|-------|-----------|-----------|-------|--------|-----------|
| **Salary extraction** | ⚠️ No salary | ⚠️ No salary | ✅ Perfect | ✅ Perfect | ✅ Perfect |
| **Visa sponsorship** | ❌ Wrong | ✅ Correct | ⚠️ Not mentioned | ⚠️ Not mentioned | ⚠️ Not mentioned |
| **Work model** | ✅ Remote | ✅ Onsite | ✅ Remote | ❌ Missing | ✅ Hybrid |
| **Contract type** | ✅ Permanent | ❌ Missing | ❌ Missing | ❌ Missing | ❌ Missing |
| **Skills classification** | ❌ All must-have | ✅ PERFECT | ❌ FAILED | ✅ Good | ⚠️ Partial |
| **Soft skills** | ❌ None | ❌ None | ✅ Extracted | ✅ Extracted | ❌ None |
| **Years experience** | ❌ Missing | ❌ Missing | ✅ 6-8 | ✅ 5+ | ✅ 6+ |
| **Benefits/PTO** | ❌ Missing | ❌ Missing | ✅ Unlimited | ❌ Missing | ❌ Missing |

---

## Problemas Críticos Identificados

### 1. ❌ EAMES CONSULTING - Skills Classification FAILED
**Severidade:** CRÍTICA
**Problema:** LLM ignora qualificadores internos fortes quando seção se chama "Preferred"
**Impacto:** 29 skills classificados como nice-to-have quando 15-18 deveriam ser must-have

**Fix Required:**
As regras já estão no prompt mas não estão sendo seguidas:
```python
# REGRA NO PROMPT (lines 56-77):
**CRITICAL: Prioritize internal qualifiers over section titles!**
- "Strong proficiency in X" → must_have (MESMO em seção "Preferred"!)
```

**Possível causa:**
1. Prompt pode estar muito longo, LLM perdendo atenção
2. Ordem das instruções - talvez colocar CRITICAL no início do prompt
3. Adicionar exemplos EXATOS com "Preferred Qualifications" no prompt

### 2. ❌ Visa Sponsorship Ambígua
**Severidade:** MÉDIA
**Problema:** "All immigration statuses accepted" classificado como "not_mentioned"
**Sugestão:** Adicionar categoria `all_accepted` ou `no_restrictions` ao enum

### 3. ❌ Contract Type Não Extraído
**Severidade:** BAIXA
**Problema:** Jobs full-time não estão sendo classificados como "permanent"
**Padrão:** "Full-time" → contract_type: "permanent"

### 4. ⚠️ Soft Skills - Inconsistente
**Severidade:** MÉDIA
**Sucesso parcial:**
- ✅ Amazon: Extraiu "Leadership, Mentoring, Team Collaboration"
- ✅ Eames: Extraiu "Communication, Team Collaboration, Empathy"
- ❌ Outros 3 jobs: Zero soft skills extraídos

---

## Recomendações de Fix

### Priority 1: Fix Eames Consulting Skills Classification
**Ação:**
1. Mover a regra "CRITICAL: Internal qualifiers override section titles" para o TOPO do SKILLS CLASSIFICATION RULES
2. Adicionar exemplo EXATO do padrão Eames no prompt:
```python
EXAMPLE - Preferred Qualifications with Strong Internal Qualifiers:
"Preferred Qualifications:
- Strong proficiency in SQL and Python"
→ MUST extract as must_have_hard_skills: ["SQL", "Python"]
→ DO NOT extract as nice_to_have because section says "Preferred"
```

### Priority 2: Add Visa Sponsorship Pattern
**Ação:**
```python
VALID_VISA_SPONSORSHIP = {
    "will_sponsor",
    "will_not_sponsor",
    "must_be_authorized",
    "no_restrictions",  # NEW
    "not_mentioned"
}

# Extraction rule:
"All immigration statuses accepted" → "no_restrictions"
"No restrictions" → "no_restrictions"
```

### Priority 3: Improve Contract Type Inference
**Ação:**
```python
# Add to prompt:
- "Full-time" (without contract mention) → contract_type: "permanent"
- "Full-time employee" → contract_type: "permanent"
```

### Priority 4: Strengthen Soft Skills Extraction
**Ação:**
- Adicionar no prompt: "ALWAYS scan the entire job description for soft skills"
- Adicionar mais exemplos de contextos onde soft skills aparecem

---

## Taxa de Sucesso por Grupo de Campos

| Grupo | Taxa de Sucesso | Comentário |
|-------|----------------|------------|
| Compensation | 60% (3/5 disclose) | ✅ Extração correta quando disclosed |
| Work Authorization | 20% (1/5 correct) | ❌ Precisa melhorar |
| Work Model | 80% (4/5 correct) | ✅ Bom desempenho |
| Contract Details | 20% (1/5 correct) | ❌ Precisa melhorar |
| Skills Classification | 40% (2/5 correct) | ⚠️ Crítico - Eames failed |
| Soft Skills | 40% (2/5 extracted) | ⚠️ Inconsistente |
| Experience | 60% (3/5 extracted) | ✅ Razoável |
| Benefits | 20% (1/5 complete) | ❌ Precisa melhorar |

**Overall Assessment:** 50% effective (needs improvement on critical issues)
