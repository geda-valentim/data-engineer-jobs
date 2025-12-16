
# Inter-Model Evaluation Analysis Summary

**Generated:** 2025-12-11 20:40:18

## Overview
- **Jobs Analyzed:** 96
- **Total Fields Evaluated:** 12000
- **Overall Consensus Rate:** 78.2%

## Pass-by-Pass Performance
- **Pass 1 (Extraction):** 88.6%
- **Pass 2 (Inference):** 87.5%
- **Pass 3 (Analysis):** 61.0%

## Key Findings

### Model Performance
- **Best Performer:** MiniMax M2 (Score: 77.2)
- **Needs Improvement:** Google Gemma 3 27B (Score: 71.3)

### Field Type Analysis
- **Highest Agreement:** boolean (99.0%)
- **Lowest Agreement:** array (64.8%)
- **Gap Fields:** 27 fields with <60% agreement

### Recommendations
1. **Focus on improving:** array field types (lowest agreement)
2. **Review models:** Investigate why Google Gemma 3 27B has lower performance
3. **Address gaps:** Review 27 low-agreement fields for prompt improvements
4. **Leverage strengths:** MiniMax M2 shows strong performance, consider as reference

## Next Steps
- Review detailed field-level analysis for specific improvements
- Consider adding more models or adjusting prompts for low-agreement fields
- Monitor trends as new jobs are added
