"""
PyArrow schema definition for LinkedIn Companies Silver layer.

This schema defines the structure of the Parquet files in the Silver layer,
transforming raw JSON company data into a flat, queryable format.

Partitioning: Uses bucket hash (MD5) with 50 buckets for even distribution.
"""

import pyarrow as pa

# Handle imports for both Lambda (flat structure) and local execution (package structure)
try:
    # Lambda execution - flat structure
    from shared.company_lookup import compute_bucket, NUM_BUCKETS
except ImportError:
    # Local execution - package structure
    from ..shared.company_lookup import compute_bucket, NUM_BUCKETS


# Define the Silver layer schema for LinkedIn companies
COMPANIES_SILVER_SCHEMA = pa.schema([
    # Partition Key (must be first for efficient writes)
    pa.field("bucket", pa.int32(), nullable=False),

    # Core Identifiers
    pa.field("company_id", pa.string(), nullable=False),
    pa.field("linkedin_id", pa.string(), nullable=True),
    pa.field("name", pa.string(), nullable=True),
    pa.field("slogan", pa.string(), nullable=True),
    pa.field("headquarters", pa.string(), nullable=True),
    pa.field("country_code", pa.string(), nullable=True),
    pa.field("website", pa.string(), nullable=True),
    pa.field("website_domain", pa.string(), nullable=True),
    pa.field("linkedin_url", pa.string(), nullable=True),

    # Company Info
    pa.field("about", pa.string(), nullable=True),
    pa.field("industries", pa.string(), nullable=True),
    pa.field("specialties", pa.string(), nullable=True),
    pa.field("organization_type", pa.string(), nullable=True),
    pa.field("company_size", pa.string(), nullable=True),
    pa.field("founded_year", pa.int32(), nullable=True),

    # Metrics
    pa.field("followers", pa.int64(), nullable=True),
    pa.field("employees_on_linkedin", pa.int32(), nullable=True),

    # Location (JSON arrays as strings)
    pa.field("locations_json", pa.string(), nullable=True),
    pa.field("formatted_locations_json", pa.string(), nullable=True),
    pa.field("country_codes_json", pa.string(), nullable=True),

    # Media
    pa.field("logo_url", pa.string(), nullable=True),
    pa.field("cover_image_url", pa.string(), nullable=True),

    # Funding (nullable group)
    pa.field("funding_last_round_date", pa.date32(), nullable=True),
    pa.field("funding_last_round_type", pa.string(), nullable=True),
    pa.field("funding_rounds_count", pa.int32(), nullable=True),
    pa.field("funding_last_round_amount", pa.string(), nullable=True),

    # External Links
    pa.field("crunchbase_url", pa.string(), nullable=True),

    # Nested Data as JSON strings
    pa.field("employees_json", pa.string(), nullable=True),
    pa.field("similar_companies_json", pa.string(), nullable=True),
    pa.field("affiliated_pages_json", pa.string(), nullable=True),
    pa.field("updates_json", pa.string(), nullable=True),

    # Derived/Computed Fields
    pa.field("employees_featured_count", pa.int32(), nullable=True),
    pa.field("similar_companies_count", pa.int32(), nullable=True),
    pa.field("affiliated_pages_count", pa.int32(), nullable=True),
    pa.field("updates_count", pa.int32(), nullable=True),
    pa.field("has_funding_info", pa.bool_(), nullable=True),
    pa.field("latest_update_date", pa.timestamp("us", tz="UTC"), nullable=True),

    # Metadata
    pa.field("snapshot_date", pa.date32(), nullable=False),
    pa.field("scraped_at", pa.timestamp("us", tz="UTC"), nullable=True),
    pa.field("source_url", pa.string(), nullable=True),
    pa.field("processed_at", pa.timestamp("us", tz="UTC"), nullable=False),
])

# Column names for easy reference
COLUMN_NAMES = COMPANIES_SILVER_SCHEMA.names

# Partition columns for Parquet output (bucket hash)
PARTITION_COLS = ["bucket"]


def get_schema() -> pa.Schema:
    """Return the PyArrow schema for LinkedIn companies Silver layer."""
    return COMPANIES_SILVER_SCHEMA


def get_column_names() -> list[str]:
    """Return list of all column names in schema order."""
    return COLUMN_NAMES


def get_partition_columns() -> list[str]:
    """Return list of partition column names."""
    return PARTITION_COLS


def get_num_buckets() -> int:
    """Return the number of buckets for hash partitioning."""
    return NUM_BUCKETS
