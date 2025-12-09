# Local Data Structure (data/local)

This document describes the organizational structure for local data storage during AI enrichment testing and development.

## Overview

The `data/local/ai_enrichment/` directory follows the **Medallion Architecture** pattern (Bronze → Silver → Gold) specifically for AI enrichment workflows.

## Directory Structure

```
data/local/
└── ai_enrichment/
    ├── bronze/                      # JSON raw results from LLMs
    │   └── {job_id}/
    │       ├── pass1-{model}.json   # Pass 1: Extraction
    │       ├── pass1-{model}-raw.txt
    │       ├── pass2-{model}.json   # Pass 2: Inference
    │       ├── pass2-{model}-raw.txt
    │       ├── pass3-{model}.json   # Pass 3: Analysis
    │       └── pass3-{model}-raw.txt
    │
    ├── silver/                      # Parquet with Delta Lake (future)
    │   └── delta/
    │       └── enriched_jobs/       # DeltaLake table
    │           ├── _delta_log/
    │           └── *.parquet
    │
    └── gold/                        # Aggregated analysis (future)
        └── delta/
            └── model_comparisons/   # DeltaLake table
                ├── _delta_log/
                └── *.parquet
```

## Layers Explained

### Bronze Layer (JSON)
- **Purpose**: Raw JSON results from LLM API calls
- **Format**: JSON files + raw text responses
- **Usage**: Primary cache for enrichment results during testing
- **Path**: `data/local/ai_enrichment/bronze/{job_id}/`
- **Characteristics**:
  - One directory per job (`job_posting_id` or hash)
  - Multiple files per model (pass1, pass2, pass3)
  - Raw LLM responses saved as `.txt` for debugging

#### File Naming Convention
- **Results**: `{pass}-{model}.json`
  - Example: `pass1-openai-gpt-oss-120b-1-0.json`
- **Raw Responses**: `{pass}-{model}-raw.txt`
  - Example: `pass3-minimax-m2-raw.txt`

#### Model ID Sanitization
Model IDs are cleaned for filesystem compatibility:
- `:` → `-`
- `/` → `-`
- `.` → `-`

Example: `openai.gpt-oss-120b-1:0` → `openai-gpt-oss-120b-1-0`

### Silver Layer (Parquet + Delta Lake)
- **Purpose**: Structured, queryable enrichment results
- **Format**: Parquet files managed by Delta Lake
- **Usage**: Efficient queries, time travel, schema evolution
- **Path**: `data/local/ai_enrichment/silver/delta/enriched_jobs/`
- **Future Features**:
  - ACID transactions
  - Time travel (query historical versions)
  - Schema evolution
  - Efficient filtering and aggregation

#### Bronze → Silver Transformation Script (Future)
```bash
python scripts/ai-enrichment/bronze_to_silver.py \
  --input data/local/ai_enrichment/bronze \
  --output data/local/ai_enrichment/silver/delta/enriched_jobs
```

### Gold Layer (Delta Lake Analytics)
- **Purpose**: Aggregated analysis and model comparisons
- **Format**: Parquet files managed by Delta Lake
- **Usage**: Business intelligence, reporting, model evaluation
- **Path**: `data/local/ai_enrichment/gold/delta/`
- **Tables** (planned):
  - `model_comparisons/` - Compare accuracy across models
  - `consensus_analysis/` - Agreement metrics between LLMs
  - `cost_analysis/` - Token usage and cost by model

## Usage in Code

### Getting Cache Directory

```python
from test_enrichment_helpers import get_cache_dir

# Get Bronze cache directory (default)
bronze_dir = get_cache_dir()
# Returns: data/local/ai_enrichment/bronze/

# Get specific layer
bronze_dir = get_cache_dir(layer="bronze")
silver_dir = get_cache_dir(layer="silver")
gold_dir = get_cache_dir(layer="gold")
```

### Loading from Cache (Bronze)

```python
from test_enrichment_helpers import load_from_cache

# Load cached Pass 1 results
result = load_from_cache(
    job=job_dict,
    model_id="openai.gpt-oss-120b-1:0",
    pass_name="pass1"
)
```

### Saving to Cache (Bronze)

```python
from test_enrichment_helpers import save_to_cache

# Save Pass 2 results
save_to_cache(
    job=job_dict,
    model_id="minimax.minimax-m2:0",
    result=pass2_result,
    pass_name="pass2"
)
```

## Benefits of This Structure

1. **Domain-focused**: All AI enrichment data in one place
2. **Delta Lake Ready**: Prepared for efficient local analytics
3. **Medallion Architecture**: Clear data quality progression
4. **ACID Guarantees**: Delta Lake provides transactional consistency
5. **Time Travel**: Query historical versions of enrichment results
6. **Schema Evolution**: Adapt to changing enrichment fields

## Cache Management

### Viewing Cache Contents

```bash
# List all cached jobs in Bronze
ls data/local/ai_enrichment/bronze/

# View specific job results
ls data/local/ai_enrichment/bronze/{job_id}/

# Count total cached jobs
find data/local/ai_enrichment/bronze/ -maxdepth 1 -type d | wc -l

# View Silver Delta Lake table info
python -c "
from deltalake import DeltaTable
dt = DeltaTable('data/local/ai_enrichment/silver/delta/enriched_jobs')
print(dt.version())
print(dt.files())
"
```

### Clearing Cache

```bash
# Clear all Bronze cache
rm -rf data/local/ai_enrichment/bronze/

# Clear specific pass results
find data/local/ai_enrichment/bronze/ -name "pass3-*.json" -delete

# Clear specific model results
find data/local/ai_enrichment/bronze/ -name "*minimax-m2*.json" -delete

# Clear entire AI enrichment directory (including Silver/Gold)
rm -rf data/local/ai_enrichment/
```

### Cache Statistics

```bash
# Total size of Bronze cache
du -sh data/local/ai_enrichment/bronze/

# Number of jobs cached
ls data/local/ai_enrichment/bronze/ | wc -l

# Files per job (should be 6: 3 JSON + 3 raw TXT)
ls data/local/ai_enrichment/bronze/{job_id}/ | wc -l

# Count JSON files by pass
find data/local/ai_enrichment/bronze/ -name "pass1-*.json" | wc -l
find data/local/ai_enrichment/bronze/ -name "pass2-*.json" | wc -l
find data/local/ai_enrichment/bronze/ -name "pass3-*.json" | wc -l
```

## Migration from Old Structure

If you have data in the old `data/local/{job_id}/` structure:

```bash
# Create new structure
mkdir -p data/local/ai_enrichment/bronze

# Move old job directories to new Bronze location
for dir in data/local/[0-9a-f]*; do
  if [ -d "$dir" ]; then
    mv "$dir" data/local/ai_enrichment/bronze/
  fi
done

for dir in data/local/linkedin-*; do
  if [ -d "$dir" ]; then
    mv "$dir" data/local/ai_enrichment/bronze/
  fi
done
```

## Future: Delta Lake Local Setup

### Installing Delta Lake

```bash
pip install deltalake pandas pyarrow
```

### Example Bronze → Silver Script

```python
import pandas as pd
import json
from pathlib import Path
from deltalake import write_deltalake

def bronze_to_silver():
    """Convert Bronze JSON files to Silver Delta Lake."""
    bronze_dir = Path("data/local/ai_enrichment/bronze")
    silver_path = "data/local/ai_enrichment/silver/delta/enriched_jobs"

    records = []
    for job_dir in bronze_dir.iterdir():
        if not job_dir.is_dir():
            continue

        for json_file in job_dir.glob("pass*.json"):
            with open(json_file) as f:
                data = json.load(f)
                record = {
                    "job_id": job_dir.name,
                    "pass": json_file.stem.split("-")[0],
                    "model": "-".join(json_file.stem.split("-")[1:]),
                    **data.get("result", data)
                }
                records.append(record)

    df = pd.DataFrame(records)
    write_deltalake(silver_path, df, mode="overwrite")
    print(f"✓ Wrote {len(records)} records to {silver_path}")

if __name__ == "__main__":
    bronze_to_silver()
```

### Querying Silver Delta Lake

```python
from deltalake import DeltaTable
import pandas as pd

# Load Delta table
dt = DeltaTable("data/local/ai_enrichment/silver/delta/enriched_jobs")

# Convert to pandas for analysis
df = dt.to_pandas()

# Example queries
print(f"Total records: {len(df)}")
print(f"Unique jobs: {df['job_id'].nunique()}")
print(f"Models tested: {df['model'].unique()}")

# Filter by pass
pass3_results = df[df['pass'] == 'pass3']

# Time travel (query previous version)
dt_v0 = DeltaTable("data/local/ai_enrichment/silver/delta/enriched_jobs", version=0)
df_old = dt_v0.to_pandas()
```

## Related Documentation

- [AI Enrichment Technical Guide](AI_ENRICHMENT_TECHNICAL_GUIDE.md)
- [Silver Schema](silver_schema.md)
- Main README: [Project Structure](../README.md#project-structure)

## Why Delta Lake?

1. **ACID Transactions**: No partial writes or corruption
2. **Time Travel**: Query any historical version
3. **Schema Evolution**: Add/remove fields without breaking queries
4. **Efficient Queries**: Predicate pushdown, column pruning
5. **Open Format**: Parquet-based, compatible with Spark, pandas, DuckDB
6. **Local First**: Works on laptop, scales to cluster
