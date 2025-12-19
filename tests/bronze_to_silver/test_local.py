"""
Local test script for LinkedIn Companies Bronze to Silver transformation.

Tests the transformation pipeline using local company JSON files.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src" / "lambdas"))

import pyarrow as pa
import pyarrow.parquet as pq

from bronze_to_silver.companies.schema import get_schema, get_column_names
from bronze_to_silver.companies.transformer import transform_company
from bronze_to_silver.shared.s3_utils import (
    iter_companies_from_local,
    write_silver_parquet,
)


# Local paths
LOCAL_BRONZE_PATH = project_root / "data" / "local" / "linkedin_companies"
LOCAL_SILVER_PATH = project_root / "data" / "local" / "silver" / "linkedin_companies"


def test_single_company_transform():
    """Test transformation of a single company JSON."""
    print("\n=== Test: Single Company Transformation ===\n")

    # Find first company with data
    for entry in os.scandir(LOCAL_BRONZE_PATH):
        if entry.is_dir() and entry.name.startswith("company_id="):
            for file_entry in os.scandir(entry.path):
                if file_entry.name.endswith(".json"):
                    with open(file_entry.path, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)

                    filename = file_entry.name
                    processed_at = datetime.now(timezone.utc)

                    # Transform
                    row = transform_company(raw_data, filename, processed_at)

                    print(f"Source: {entry.name}/{filename}")
                    print(f"\nTransformed fields ({len(row)} total):\n")

                    # Print key fields
                    key_fields = [
                        "company_id", "linkedin_id", "name", "headquarters",
                        "industries", "company_size", "followers",
                        "employees_on_linkedin", "founded_year",
                        "has_funding_info", "employees_featured_count",
                        "similar_companies_count", "updates_count",
                        "snapshot_date", "latest_update_date",
                    ]

                    for field in key_fields:
                        value = row.get(field)
                        if isinstance(value, str) and len(value) > 80:
                            value = value[:80] + "..."
                        print(f"  {field}: {value}")

                    # Check JSON fields
                    print("\nJSON field lengths:")
                    json_fields = [
                        "locations_json", "employees_json",
                        "similar_companies_json", "updates_json"
                    ]
                    for field in json_fields:
                        value = row.get(field)
                        if value:
                            print(f"  {field}: {len(value)} chars")
                        else:
                            print(f"  {field}: None")

                    return row

    print("No company JSON files found!")
    return None


def test_batch_transform(max_companies: int = 30):
    """Test batch transformation and schema validation."""
    print(f"\n=== Test: Batch Transformation ({max_companies} companies) ===\n")

    rows = []
    errors = []
    processed_at = datetime.now(timezone.utc)

    for raw_data, filename in iter_companies_from_local(
        str(LOCAL_BRONZE_PATH),
        max_companies=max_companies
    ):
        try:
            row = transform_company(raw_data, filename, processed_at)
            rows.append(row)
        except Exception as e:
            errors.append({
                "company_id": raw_data.get("company_id", "unknown"),
                "error": str(e)
            })

    print(f"Successfully transformed: {len(rows)} companies")
    print(f"Errors: {len(errors)}")

    if errors:
        print("\nFirst 5 errors:")
        for err in errors[:5]:
            print(f"  {err['company_id']}: {err['error']}")

    return rows, errors


def test_parquet_creation(rows: list, output_path: str = None):
    """Test PyArrow table creation and Parquet writing."""
    print("\n=== Test: Parquet Creation ===\n")

    if not rows:
        print("No rows to process!")
        return None

    schema = get_schema()
    output_path = output_path or str(LOCAL_SILVER_PATH)

    # Build column arrays
    arrays = {}
    for field in schema:
        col_name = field.name
        values = [row.get(col_name) for row in rows]
        arrays[col_name] = values

    # Create table
    try:
        table = pa.table(arrays, schema=schema)
        print(f"Created PyArrow table: {table.num_rows} rows x {table.num_columns} columns")
        print(f"Memory usage: {table.nbytes / 1024:.2f} KB")

        # Write to local path
        os.makedirs(output_path, exist_ok=True)
        output_file = os.path.join(output_path, "linkedin_companies.parquet")
        pq.write_table(table, output_file)
        print(f"\nWrote Parquet to: {output_file}")

        # Verify by reading back
        read_table = pq.read_table(output_file)
        print(f"Verified: Read back {read_table.num_rows} rows")

        # Show sample data
        print("\nSample data (first 3 rows, selected columns):")
        sample_cols = ["company_id", "name", "industries", "followers", "snapshot_date"]
        df = table.select(sample_cols).to_pandas()
        print(df.head(3).to_string())

        return table

    except Exception as e:
        print(f"Error creating table: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_schema_coverage(rows: list):
    """Test schema coverage - check for null values in each column."""
    print("\n=== Test: Schema Coverage ===\n")

    if not rows:
        print("No rows to analyze!")
        return

    column_names = get_column_names()
    coverage = {}

    for col in column_names:
        non_null_count = sum(1 for row in rows if row.get(col) is not None)
        coverage[col] = {
            "non_null": non_null_count,
            "null": len(rows) - non_null_count,
            "coverage_pct": (non_null_count / len(rows)) * 100,
        }

    # Sort by coverage
    sorted_coverage = sorted(coverage.items(), key=lambda x: x[1]["coverage_pct"], reverse=True)

    print(f"Column coverage for {len(rows)} companies:\n")
    print(f"{'Column':<35} {'Non-Null':<10} {'Null':<10} {'Coverage':<10}")
    print("-" * 65)

    for col, stats in sorted_coverage:
        print(f"{col:<35} {stats['non_null']:<10} {stats['null']:<10} {stats['coverage_pct']:.1f}%")


def main():
    """Run all tests."""
    print("=" * 70)
    print("LinkedIn Companies Bronze → Silver Local Test")
    print("=" * 70)

    # Check if local data exists
    if not LOCAL_BRONZE_PATH.exists():
        print(f"ERROR: Bronze data path not found: {LOCAL_BRONZE_PATH}")
        print("Please ensure company data is available in data/local/linkedin_companies/")
        return 1

    company_count = sum(1 for _ in LOCAL_BRONZE_PATH.iterdir() if _.is_dir())
    print(f"\nFound {company_count} company directories in {LOCAL_BRONZE_PATH}")

    # Run tests
    test_single_company_transform()

    rows, errors = test_batch_transform(max_companies=30)

    if rows:
        test_schema_coverage(rows)
        test_parquet_creation(rows)

    print("\n" + "=" * 70)
    print("Tests completed!")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
