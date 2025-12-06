# Save JSON Results Feature - Implementation

**Date:** 2025-12-06
**Status:** Implemented and Ready to Use

---

## Summary

Added `--save-json` option to save complete enrichment results to JSON files in the `data/local/` folder. This allows users to export all Pass 1, Pass 2, and Pass 3 results for analysis, backup, or integration with other tools.

---

## What Was Implemented

### 1. New Function: `_save_results_to_json()`

**Location:** `scripts/ai-enrichment/test_enrichment_local.py` (lines 379-502)

**Features:**
- Saves complete enrichment results to structured JSON file
- Creates `data/local/` directory automatically
- Generates timestamped filenames
- Includes metadata (timestamp, test type, partition info)
- Exports all three passes (Pass 1, Pass 2, Pass 3) when available
- Handles cache information (shows which passes were loaded from cache)

### 2. New CLI Argument: `--save-json`

**Added to:**
- Pass 2 test: `test_pass2_inference()`
- Pass 3 test: `test_pass3_analysis()`

**Usage:**
```bash
--save-json    Save complete results to JSON file in data/local/ folder
```

---

## Usage Examples

### Pass 2 with JSON Export
```bash
python scripts/ai-enrichment/test_enrichment_local.py \
  --pass2 \
  --s3-source \
  --date=2025-12-05 \
  --limit=5 \
  --cache \
  --save-json
```

**Output:**
```
💾 Results saved to: /home/playground/data-engineer-jobs/data/local/enrichment_results_pass2_20251206_134523.json
```

### Pass 3 with JSON Export
```bash
python scripts/ai-enrichment/test_enrichment_local.py \
  --pass3 \
  --s3-source \
  --date=2025-12-05 \
  --limit=10 \
  --cache \
  --save-json
```

**Output:**
```
💾 Results saved to: /home/playground/data-engineer-jobs/data/local/enrichment_results_pass3_20251206_145612.json
```

---

## JSON File Structure

### File Naming Convention
```
data/local/enrichment_results_{test_type}_{timestamp}.json
```

**Examples:**
- `enrichment_results_pass2_20251206_134523.json`
- `enrichment_results_pass3_20251206_145612.json`

### JSON Schema

```json
{
  "metadata": {
    "timestamp": "2025-12-06 13:45:23",
    "test_type": "pass3",
    "jobs_processed": 5,
    "data_source": "S3 Silver Bucket",
    "partition": "2025-12-05 Hour 23"
  },
  "jobs": [
    {
      "job_info": {
        "job_posting_id": "linkedin-001",
        "job_title": "Senior Data Engineer",
        "company_name": "Tech Company",
        "job_location": "San Francisco, CA"
      },
      "pass1": {
        "success": true,
        "from_cache": true,
        "extraction": {
          "skills_classified": {
            "must_have_hard_skills": ["Python", "SQL", "Spark"],
            "nice_to_have_hard_skills": ["Kafka", "Airflow"],
            "must_have_soft_skills": ["Communication", "Leadership"],
            "nice_to_have_soft_skills": ["Mentoring"],
            "certifications_mentioned": [],
            "years_experience_min": 5,
            "years_experience_max": 8,
            "years_experience_text": "5-8 years",
            "education_stated": "Bachelor's in CS or related field",
            "llm_genai_mentioned": true,
            "feature_store_mentioned": false
          },
          "compensation": {
            "salary_disclosed": true,
            "salary_min": 150000,
            "salary_max": 200000,
            "salary_currency": "USD",
            "salary_period": "yearly"
          },
          "work_authorization": {
            "visa_sponsorship_stated": "will_not_sponsor",
            "security_clearance_stated": null
          },
          "work_model": {
            "work_model_stated": "remote",
            "employment_type_stated": "full_time"
          }
        },
        "tokens": 2834,
        "cost": 0.001234
      },
      "pass2": {
        "success": true,
        "from_cache": true,
        "inference": {
          "seniority_and_role": {
            "seniority_level": {
              "value": "senior",
              "confidence": 0.95,
              "evidence": "Title + 5-8 years experience requirement",
              "source": "combined"
            },
            "job_family": {
              "value": "data_engineering",
              "confidence": 0.98,
              "evidence": "Title explicitly states Data Engineer",
              "source": "pass1_derived"
            },
            "sub_specialty": {
              "value": "platform",
              "confidence": 0.85,
              "evidence": "Building infrastructure and pipelines",
              "source": "inferred"
            },
            "leadership_expectation": {
              "value": "tech_lead",
              "confidence": 0.80,
              "evidence": "Mentoring mentioned, team size signals",
              "source": "inferred"
            }
          },
          "stack_and_cloud": {
            "primary_cloud": {
              "value": "aws",
              "confidence": 0.90,
              "evidence": "S3, Redshift, EMR mentioned",
              "source": "pass1_derived"
            },
            "secondary_clouds": {
              "value": [],
              "confidence": 0.95,
              "evidence": "No other cloud providers mentioned",
              "source": "pass1_derived"
            },
            "processing_paradigm": {
              "value": "hybrid",
              "confidence": 0.85,
              "evidence": "Both batch (Airflow) and streaming (Kafka) mentioned",
              "source": "inferred"
            },
            "orchestrator_category": {
              "value": "airflow",
              "confidence": 0.95,
              "evidence": "Airflow explicitly mentioned",
              "source": "pass1_derived"
            },
            "storage_layer": {
              "value": "data_warehouse",
              "confidence": 0.90,
              "evidence": "Redshift mentioned",
              "source": "pass1_derived"
            }
          },
          "geo_and_work_model": {
            "remote_restriction": {
              "value": "fully_remote",
              "confidence": 0.95,
              "evidence": "Remote explicitly stated",
              "source": "pass1_derived"
            },
            "timezone_focus": {
              "value": "us_timezones",
              "confidence": 0.70,
              "evidence": "US location + remote suggests US timezone focus",
              "source": "inferred"
            },
            "relocation_required": {
              "value": false,
              "confidence": 0.95,
              "evidence": "Remote work allows any US location",
              "source": "inferred"
            }
          },
          "visa_and_authorization": {
            "h1b_friendly": {
              "value": false,
              "confidence": 0.90,
              "evidence": "No visa sponsorship stated",
              "source": "pass1_derived"
            },
            "opt_cpt_friendly": {
              "value": false,
              "confidence": 0.85,
              "evidence": "No visa sponsorship typically excludes OPT/CPT",
              "source": "inferred"
            },
            "citizenship_required": {
              "value": false,
              "confidence": 0.80,
              "evidence": "Work authorization required but not citizenship",
              "source": "inferred"
            }
          },
          "contract_and_compensation": {
            "w2_vs_1099": {
              "value": "w2",
              "confidence": 0.95,
              "evidence": "Full-time employee position",
              "source": "inferred"
            },
            "benefits_level": {
              "value": "comprehensive",
              "confidence": 0.85,
              "evidence": "Competitive salary + benefits package mentioned",
              "source": "inferred"
            }
          },
          "career_development": {
            "growth_path_clarity": {
              "value": "explicit",
              "confidence": 0.80,
              "evidence": "Leadership opportunities mentioned",
              "source": "inferred"
            },
            "mentorship_signals": {
              "value": true,
              "confidence": 0.85,
              "evidence": "Mentoring junior engineers mentioned",
              "source": "pass1_derived"
            },
            "promotion_path_mentioned": {
              "value": true,
              "confidence": 0.75,
              "evidence": "Career growth mentioned",
              "source": "inferred"
            },
            "internal_mobility_mentioned": {
              "value": false,
              "confidence": 0.90,
              "evidence": "Not mentioned in posting",
              "source": "inferred"
            },
            "career_tracks_available": {
              "value": true,
              "confidence": 0.70,
              "evidence": "IC and management tracks implied",
              "source": "inferred"
            }
          },
          "requirements_classification": {
            "requirement_strictness": {
              "value": "moderate",
              "confidence": 0.80,
              "evidence": "Mix of required and preferred skills",
              "source": "inferred"
            },
            "scope_definition": {
              "value": "well_defined",
              "confidence": 0.85,
              "evidence": "Clear responsibilities and requirements",
              "source": "inferred"
            },
            "skill_inflation_detected": {
              "value": false,
              "confidence": 0.90,
              "evidence": "Reasonable skill requirements for senior level",
              "source": "inferred"
            }
          }
        },
        "tokens": 8953,
        "cost": 0.001733
      },
      "pass3": {
        "success": true,
        "from_cache": false,
        "analysis": {
          "company_maturity": {
            "data_maturity_score": {
              "value": 4,
              "confidence": 0.85,
              "evidence": "Modern data stack (Snowflake, dbt, Airflow), CI/CD practices, monitoring",
              "source": "inferred"
            },
            "data_maturity_level": {
              "value": "managed",
              "confidence": 0.85,
              "evidence": "Score 4 indicates managed maturity level with strong practices",
              "source": "inferred"
            },
            "maturity_signals": {
              "value": [
                "modern_data_stack_adoption",
                "cicd_practices",
                "data_quality_testing",
                "monitoring_observability",
                "cloud_native"
              ],
              "confidence": 0.90,
              "evidence": "Multiple advanced tooling and practices mentioned",
              "source": "inferred"
            }
          },
          "red_flags_and_role_quality": {
            "scope_creep_score": {
              "value": 0.2,
              "confidence": 0.85,
              "evidence": "Clear DE focus, no unrelated responsibilities",
              "source": "inferred"
            },
            "overtime_risk_score": {
              "value": 0.3,
              "confidence": 0.75,
              "evidence": "Remote work flexibility, but no explicit WLB mentions",
              "source": "inferred"
            },
            "role_clarity": {
              "value": "clear",
              "confidence": 0.90,
              "evidence": "Well-defined responsibilities and expectations",
              "source": "inferred"
            },
            "overall_red_flag_score": {
              "value": 0.15,
              "confidence": 0.80,
              "evidence": "Low risk overall - clear role, good stack, remote flexibility",
              "source": "inferred"
            }
          },
          "stakeholders_and_leadership": {
            "reporting_structure_clarity": {
              "value": "moderate",
              "confidence": 0.70,
              "evidence": "Reporting structure not explicitly detailed",
              "source": "inferred"
            },
            "manager_level_inferred": {
              "value": "engineering_manager",
              "confidence": 0.75,
              "evidence": "Senior role likely reports to EM or Director",
              "source": "inferred"
            },
            "team_growth_velocity": {
              "value": "steady",
              "confidence": 0.65,
              "evidence": "No urgent hiring signals, standard posting",
              "source": "inferred"
            },
            "team_composition": {
              "value": {
                "size": "medium",
                "structure": "cross_functional"
              },
              "confidence": 0.70,
              "evidence": "Collaboration with analysts and scientists mentioned",
              "source": "inferred"
            },
            "reporting_structure": {
              "value": "hierarchical",
              "confidence": 0.75,
              "evidence": "Traditional company structure implied",
              "source": "inferred"
            },
            "cross_functional_embedded": {
              "value": true,
              "confidence": 0.85,
              "evidence": "Works with product, analytics, data science teams",
              "source": "inferred"
            }
          },
          "tech_culture": {
            "work_life_balance_score": {
              "value": 0.7,
              "confidence": 0.70,
              "evidence": "Remote flexibility positive, but no explicit WLB signals",
              "source": "inferred"
            },
            "growth_opportunities_score": {
              "value": 0.8,
              "confidence": 0.80,
              "evidence": "Leadership opportunities, mentoring, career growth mentioned",
              "source": "inferred"
            },
            "tech_culture_score": {
              "value": 0.85,
              "confidence": 0.85,
              "evidence": "Modern stack, good practices, learning culture",
              "source": "inferred"
            }
          }
        },
        "summary": {
          "strengths": [
            "Transparent compensation ($150-200k)",
            "Strong modern data stack (Spark, Airflow, Kafka)",
            "Remote work flexibility",
            "Clear career growth and leadership opportunities",
            "Well-defined role with no scope creep"
          ],
          "concerns": [
            "No visa sponsorship",
            "Work-life balance signals not explicit",
            "Reporting structure not detailed"
          ],
          "best_fit_for": [
            "Senior DEs with 5-8 years wanting platform/infrastructure focus",
            "Engineers seeking remote work with modern stack",
            "Those interested in technical leadership and mentoring"
          ],
          "red_flags_to_probe": [
            "Ask about actual work hours and on-call expectations",
            "Understand team size and composition",
            "Clarify reporting structure and career progression"
          ],
          "negotiation_leverage": [
            "Strong Spark and streaming expertise (Kafka) is high-value",
            "Leadership and mentoring experience is differentiator",
            "Remote work allows geographic flexibility"
          ],
          "overall_assessment": "Strong opportunity for senior DE seeking modern stack, remote work, and technical leadership. Competitive compensation, clear role definition, good tech culture. Main trade-offs are lack of visa sponsorship and unclear WLB signals.",
          "recommendation_score": 0.82,
          "recommendation_confidence": 0.85
        },
        "tokens": 12453,
        "cost": 0.005769
      }
    }
  ]
}
```

---

## File Location

**Directory:** `data/local/`

**Structure:**
```
data-engineer-jobs/
├── data/
│   └── local/
│       ├── enrichment_results_pass2_20251206_134523.json
│       ├── enrichment_results_pass2_20251206_145612.json
│       ├── enrichment_results_pass3_20251206_150234.json
│       └── enrichment_results_pass3_20251206_161045.json
```

**Why `data/local/`?**
- `data/` is already gitignored
- `local/` distinguishes from S3/production data
- Prevents accidental commits of test results

---

## Benefits

### 1. **Analysis and Reporting**
- Export results to CSV/Excel for analysis
- Generate reports and visualizations
- Track LLM performance over time
- Compare results across different dates

### 2. **Backup and Versioning**
- Keep snapshots of test results
- Compare before/after prompt changes
- Historical record of enrichment quality

### 3. **Integration**
- Import into other tools (Jupyter, pandas, BI tools)
- Feed into ML pipelines
- Use for validation and testing

### 4. **Cost Tracking**
- Track token usage over time
- Monitor cost per job
- Identify expensive jobs for optimization

### 5. **Debugging**
- Inspect exact LLM outputs
- Trace confidence scores and evidence
- Validate schema compliance

---

## Code Changes Summary

### Files Modified

**1. `scripts/ai-enrichment/test_enrichment_local.py`**

**Added:**
- `_save_results_to_json()` function (lines 379-502) - 124 lines
- `--save-json` CLI argument (line 2042)
- `save_json` parameter to `test_pass2_inference()` (line 1031)
- `save_json` parameter to `test_pass3_analysis()` (line 1482)
- Save logic in Pass 2 test (lines 1461-1471)
- Save logic in Pass 3 test (lines 2005-2015)
- Updated function calls in main() (lines 2076, 2085)

**Total additions:** ~140 lines

---

## Usage Workflow

### Complete Test with Export

```bash
# Step 1: Run Pass 3 test with cache and save results
python scripts/ai-enrichment/test_enrichment_local.py \
  --pass3 \
  --s3-source \
  --date=2025-12-05 \
  --limit=10 \
  --cache \
  --save-json

# Step 2: Check saved file
ls -lh data/local/

# Output:
# enrichment_results_pass3_20251206_134523.json (45 KB)

# Step 3: Analyze with jq
cat data/local/enrichment_results_pass3_20251206_134523.json | jq '.metadata'

# Step 4: Extract specific data
cat data/local/enrichment_results_pass3_20251206_134523.json | \
  jq '.jobs[].pass3.summary.recommendation_score'
```

### Python Analysis

```python
import json
import pandas as pd

# Load results
with open('data/local/enrichment_results_pass3_20251206_134523.json') as f:
    data = json.load(f)

# Extract metadata
print(f"Test: {data['metadata']['test_type']}")
print(f"Jobs: {data['metadata']['jobs_processed']}")
print(f"Source: {data['metadata']['data_source']}")

# Convert to DataFrame
jobs_data = []
for job in data['jobs']:
    jobs_data.append({
        'company': job['job_info']['company_name'],
        'title': job['job_info']['job_title'],
        'pass1_success': job.get('pass1', {}).get('success'),
        'pass2_success': job.get('pass2', {}).get('success'),
        'pass3_success': job.get('pass3', {}).get('success'),
        'recommendation_score': job.get('pass3', {}).get('summary', {}).get('recommendation_score'),
        'total_cost': (
            job.get('pass1', {}).get('cost', 0) +
            job.get('pass2', {}).get('cost', 0) +
            job.get('pass3', {}).get('cost', 0)
        )
    })

df = pd.DataFrame(jobs_data)
print(df)

# Summary statistics
print(f"\nAverage recommendation score: {df['recommendation_score'].mean():.2f}")
print(f"Total cost: ${df['total_cost'].sum():.4f}")
print(f"Success rate: {df['pass3_success'].mean()*100:.0f}%")
```

---

## Error Handling

### Graceful Failure
- If JSON save fails, warning is shown but test continues
- Console output is not affected
- Test results are still displayed normally

### Example Warning:
```
⚠ Warning: Could not save results to JSON: [Errno 13] Permission denied
```

---

## Performance Impact

**Minimal:**
- JSON serialization happens after all processing
- File I/O is asynchronous
- No impact on LLM calls or token usage
- Typically <100ms for 10 jobs

---

## Future Enhancements (Out of Scope)

1. **Custom output directory:** `--output-dir=path/to/folder`
2. **Custom filename:** `--output-file=my_results.json`
3. **CSV export:** `--save-csv`
4. **Parquet export:** `--save-parquet`
5. **S3 upload:** `--upload-to-s3`
6. **Append mode:** Add to existing file instead of creating new one

---

## Testing

### Verify JSON Structure
```bash
# Run test with save
python scripts/ai-enrichment/test_enrichment_local.py --pass3 --cache --save-json

# Validate JSON
python -m json.tool data/local/enrichment_results_pass3_*.json > /dev/null && echo "Valid JSON"

# Count jobs
jq '.jobs | length' data/local/enrichment_results_pass3_*.json
```

### Verify All Passes Present
```bash
# Check Pass 1 data
jq '.jobs[0].pass1.success' data/local/enrichment_results_pass3_*.json

# Check Pass 2 data
jq '.jobs[0].pass2.success' data/local/enrichment_results_pass3_*.json

# Check Pass 3 data
jq '.jobs[0].pass3.success' data/local/enrichment_results_pass3_*.json
```

---

## Summary

The `--save-json` feature provides a robust way to export enrichment results for analysis, backup, and integration. It follows best practices:

✅ **Non-intrusive:** Optional flag, doesn't affect normal operation
✅ **Complete:** Exports all passes with full metadata
✅ **Structured:** Well-defined JSON schema
✅ **Timestamped:** Unique filenames prevent overwrites
✅ **Error-resilient:** Graceful failure handling
✅ **Performance:** Minimal overhead

**Ready to use with:**
```bash
python scripts/ai-enrichment/test_enrichment_local.py --pass3 --s3-source --date=2025-12-05 --limit=5 --cache --save-json
```
