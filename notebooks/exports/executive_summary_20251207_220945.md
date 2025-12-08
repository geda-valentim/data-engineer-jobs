
# Inter-Model Evaluation Analysis Summary

**Generated:** 2025-12-07 22:09:45

## Overview
- **Jobs Analyzed:** 1
- **Total Fields Evaluated:** 125
- **Overall Consensus Rate:** 81.6%

## Pass-by-Pass Performance
- **Pass 1 (Extraction):** 88.9%
- **Pass 2 (Inference):** 96.0%
- **Pass 3 (Analysis):** 65.2%

## Key Findings

### Model Performance
- **Best Performer:** Qwen3 235B (Score: 81.8)
- **Needs Improvement:** OpenAI GPT-OSS 120B (Score: 72.6)

### Field Type Analysis
- **Highest Agreement:** boolean (100.0%)
- **Lowest Agreement:** array (66.0%)
- **Gap Fields:** 21 fields with <60% agreement

### Recommendations
1. **Focus on improving:** array field types (lowest agreement)
2. **Review models:** Investigate why OpenAI GPT-OSS 120B has lower performance
3. **Address gaps:** Review 21 low-agreement fields for prompt improvements
4. **Leverage strengths:** Qwen3 235B shows strong performance, consider as reference

## Next Steps
- Review detailed field-level analysis for specific improvements
- Consider adding more models or adjusting prompts for low-agreement fields
- Monitor trends as new jobs are added
