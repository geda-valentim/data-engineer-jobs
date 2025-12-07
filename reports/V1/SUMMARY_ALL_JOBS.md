# Inter-Model Evaluation Summary - All Jobs

Generated: 2025-12-07

## Overview

| Job ID | Company | Title | Models | Overall | Pass 1 | Pass 2 | Pass 3 | High Disagreement |
|--------|---------|-------|--------|---------|--------|--------|--------|-------------------|
| 4323400548 | SimpliSafe | Senior Data Engineer | 5 | 80.8% | 88.9% | 100.0% | 60.9% | 22 |
| 4325829597 | TCS | Go Anywhere SFTP Data Engineer | 5 | 81.6% | 96.3% | 96.0% | 56.5% | 13 |
| 4325839911 | Mattoni 1873 | AI Data Engineer | 5 | 83.2% | 88.9% | 96.0% | 69.6% | 20 |
| 4325889818 | aKUBE | Senior Data Engineer – Commerce | 4 | 77.6% | 87.0% | 100.0% | 54.3% | 14 |
| 4325939213 | TCS | Senior Data Engineer (SQL, Python) | 5 | 84.8% | 90.7% | 100.0% | 69.6% | 18 |
| 4325939525 | Pacer Group | Sr. Data Engineer (Palantir) | 5 | 87.2% | 90.7% | 96.0% | 78.3% | 15 |
| 4325948158 | Manchester Digital | Data Engineer | 5 | 76.8% | 90.7% | 92.0% | 52.2% | 16 |
| 4326005551 | Equifax | Data Engineering USIS | 5 | 84.0% | 90.7% | 96.0% | 69.6% | 19 |
| 4342313220 | MUSINSA | Data Engineer (모델링) | 5 | 78.4% | 85.2% | 92.0% | 63.0% | 28 |
| 4342323073 | Ursa Major | Software & Data Engineer (Palantir) | 4 | 80.8% | 85.2% | 92.0% | 69.6% | 14 |

## Aggregate Statistics

| Metric | Average | Min | Max |
|--------|---------|-----|-----|
| Overall Consensus | **81.5%** | 76.8% | 87.2% |
| Pass 1 (Extraction) | **89.4%** | 85.2% | 96.3% |
| Pass 2 (Inference) | **96.0%** | 92.0% | 100.0% |
| Pass 3 (Analysis) | **64.4%** | 52.2% | 78.3% |

## Key Findings

### Pass Performance
- **Pass 2 (Inference)** has the highest consensus (96.0% avg) - structured inference objects work well
- **Pass 1 (Extraction)** performs well (89.4% avg) - clear extraction rules
- **Pass 3 (Analysis)** has lowest consensus (64.4% avg) - subjective analysis fields vary

### Recurring High-Disagreement Fields

Fields that appear frequently across jobs with low agreement:

| Field | Occurrences | Issue |
|-------|-------------|-------|
| `ext_salary_period` | 7/10 | Different interpretations (annual vs not_disclosed) |
| `ext_salary_currency` | 7/10 | Currency detection varies |
| `ext_location_restriction_text` | 6/10 | Free text extraction varies |
| `ext_allowed_countries` | 5/10 | Array extraction inconsistent |
| `ext_nice_to_have_soft_skills` | 3/10 | Skill categorization differs |
| `summary.*` arrays | 10/10 | Free text = no consensus (expected) |

### Pass 3 Summary Problem

The low Pass 3 consensus (64.4%) is primarily due to:
1. **summary.strengths/concerns/etc.** - Free text arrays with 0% consensus
2. **tech_culture scores** - Subjective scoring varies between models
3. **maturity_signals** - Different interpretations of maturity indicators

**Solution Implemented**: New v3.4 schema with:
- `*_categories` (enum arrays) for consensus
- `*_details` (text arrays) for context

## Recommendations

1. **Re-run Pass 3** with updated v3.4 schema to get category-based consensus
2. **Add salary_period validation** - Clarify rules for "annual" vs "not_disclosed"
3. **Improve currency detection** - Add fallback logic based on location
4. **Standardize geo fields** - Use structured extraction for allowed_countries

## Individual Reports

- [evaluation_4323400548.md](evaluation_4323400548.md)
- [evaluation_4325829597.md](evaluation_4325829597.md)
- [evaluation_4325839911.md](evaluation_4325839911.md)
- [evaluation_4325889818.md](evaluation_4325889818.md)
- [evaluation_4325939213.md](evaluation_4325939213.md)
- [evaluation_4325939525.md](evaluation_4325939525.md)
- [evaluation_4325948158.md](evaluation_4325948158.md)
- [evaluation_4326005551.md](evaluation_4326005551.md)
- [evaluation_4342313220.md](evaluation_4342313220.md)
- [evaluation_4342323073.md](evaluation_4342323073.md)
