
# Inter-Model Evaluation Analysis Summary

**Generated:** 2025-12-08 00:21:29

## Overview
- **Jobs Analyzed:** 17
- **Total Fields Evaluated:** 2079
- **Overall Consensus Rate:** 80.1%

## Pass-by-Pass Performance
- **Pass 1 (Extraction):** 89.5%
- **Pass 2 (Inference):** 85.4%
- **Pass 3 (Analysis):** 60.4%

## Key Findings

### Model Performance
- **Best Performer:** Qwen3 235B (Score: 82.9)
- **Needs Improvement:** OpenAI GPT-OSS 120B (Score: 78.6)

### Field Type Analysis
- **Highest Agreement:** boolean (98.7%)
- **Lowest Agreement:** array (73.8%)
- **Gap Fields:** 16 fields with <60% agreement

### Recommendations
1. **Focus on improving:** array field types (lowest agreement)
2. **Review models:** Investigate why OpenAI GPT-OSS 120B has lower performance
3. **Address gaps:** Review 16 low-agreement fields for prompt improvements
4. **Leverage strengths:** Qwen3 235B shows strong performance, consider as reference

## Next Steps
- Review detailed field-level analysis for specific improvements
- Consider adding more models or adjusting prompts for low-agreement fields
- Monitor trends as new jobs are added
