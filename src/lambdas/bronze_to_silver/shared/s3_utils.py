"""
S3 utility functions for Bronze to Silver transformations.

Provides functions to read company JSON from Bronze layer and
write Parquet files to Silver layer.
"""

import json
import os
import re
from datetime import date
from typing import Any, Generator, Optional

import boto3
import pyarrow as pa
import pyarrow.parquet as pq

# Environment variables
BRONZE_BUCKET = os.environ.get("BRONZE_BUCKET", "data-engineer-jobs-bronze")
SILVER_BUCKET = os.environ.get("SILVER_BUCKET", "data-engineer-jobs-silver")

# S3 client (lazy initialization)
_s3_client = None


def get_s3_client():
    """Get or create S3 client."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def list_company_partitions(
    bucket: Optional[str] = None,
    prefix: str = "linkedin_companies/",
    max_partitions: Optional[int] = None,
) -> list[str]:
    """
    List all company_id partitions in the Bronze bucket.

    Args:
        bucket: S3 bucket name (defaults to BRONZE_BUCKET)
        prefix: S3 prefix for company data
        max_partitions: Maximum number of partitions to return

    Returns:
        List of company_id values (e.g., ["100008473", "10001914", ...])
    """
    bucket = bucket or BRONZE_BUCKET
    s3 = get_s3_client()

    partitions = []
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
        for common_prefix in page.get("CommonPrefixes", []):
            # Extract company_id from "linkedin_companies/company_id=123/"
            partition_path = common_prefix["Prefix"]
            match = re.search(r"company_id=([^/]+)", partition_path)
            if match:
                partitions.append(match.group(1))

                if max_partitions and len(partitions) >= max_partitions:
                    return partitions

    return partitions


def list_company_snapshots(
    company_id: str,
    bucket: Optional[str] = None,
    prefix: str = "linkedin_companies/",
) -> list[str]:
    """
    List all snapshot files for a specific company.

    Args:
        company_id: Company ID to list snapshots for
        bucket: S3 bucket name
        prefix: S3 prefix for company data

    Returns:
        List of snapshot filenames (e.g., ["snapshot_2025-12-08.json"])
    """
    bucket = bucket or BRONZE_BUCKET
    s3 = get_s3_client()

    partition_prefix = f"{prefix}company_id={company_id}/"
    response = s3.list_objects_v2(Bucket=bucket, Prefix=partition_prefix)

    snapshots = []
    for obj in response.get("Contents", []):
        key = obj["Key"]
        filename = key.split("/")[-1]
        if filename.endswith(".json"):
            snapshots.append(filename)

    return snapshots


def read_company_json(
    company_id: str,
    snapshot_filename: str,
    bucket: Optional[str] = None,
    prefix: str = "linkedin_companies/",
) -> tuple[dict[str, Any], str]:
    """
    Read a company JSON file from S3.

    Args:
        company_id: Company ID
        snapshot_filename: Snapshot filename (e.g., "snapshot_2025-12-08.json")
        bucket: S3 bucket name
        prefix: S3 prefix for company data

    Returns:
        Tuple of (parsed JSON data, filename)
    """
    bucket = bucket or BRONZE_BUCKET
    s3 = get_s3_client()

    key = f"{prefix}company_id={company_id}/{snapshot_filename}"
    response = s3.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read().decode("utf-8")

    return json.loads(content), snapshot_filename


def read_company_json_local(file_path: str) -> tuple[dict[str, Any], str]:
    """
    Read a company JSON file from local filesystem.

    Args:
        file_path: Path to JSON file

    Returns:
        Tuple of (parsed JSON data, filename)
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    filename = os.path.basename(file_path)
    return data, filename


def iter_companies_from_s3(
    company_ids: Optional[list[str]] = None,
    bucket: Optional[str] = None,
    prefix: str = "linkedin_companies/",
    max_companies: Optional[int] = None,
) -> Generator[tuple[dict[str, Any], str], None, None]:
    """
    Iterate over company JSON files from S3.

    Args:
        company_ids: List of company IDs to process (None = all)
        bucket: S3 bucket name
        prefix: S3 prefix for company data
        max_companies: Maximum number of companies to yield

    Yields:
        Tuple of (company data dict, snapshot filename)
    """
    bucket = bucket or BRONZE_BUCKET

    if company_ids is None:
        company_ids = list_company_partitions(bucket, prefix, max_companies)

    count = 0
    for company_id in company_ids:
        if max_companies and count >= max_companies:
            break

        snapshots = list_company_snapshots(company_id, bucket, prefix)
        for snapshot in snapshots:
            try:
                data, filename = read_company_json(company_id, snapshot, bucket, prefix)
                yield data, filename
                count += 1

                if max_companies and count >= max_companies:
                    return
            except Exception as e:
                print(f"Error reading company {company_id}/{snapshot}: {e}")
                continue


def iter_companies_from_local(
    base_path: str,
    max_companies: Optional[int] = None,
) -> Generator[tuple[dict[str, Any], str], None, None]:
    """
    Iterate over company JSON files from local filesystem.

    Args:
        base_path: Base directory containing company_id=* folders
        max_companies: Maximum number of companies to yield

    Yields:
        Tuple of (company data dict, snapshot filename)
    """
    count = 0
    for entry in os.scandir(base_path):
        if max_companies and count >= max_companies:
            break

        if entry.is_dir() and entry.name.startswith("company_id="):
            for file_entry in os.scandir(entry.path):
                if file_entry.name.endswith(".json"):
                    try:
                        data, filename = read_company_json_local(file_entry.path)
                        yield data, filename
                        count += 1

                        if max_companies and count >= max_companies:
                            return
                    except Exception as e:
                        print(f"Error reading {file_entry.path}: {e}")
                        continue


def write_silver_parquet(
    table: pa.Table,
    output_path: str,
    partition_cols: Optional[list[str]] = None,
    bucket: Optional[str] = None,
) -> str:
    """
    Write a PyArrow table to Silver layer as Parquet.

    Args:
        table: PyArrow table to write
        output_path: Output path (key prefix for S3, or local path)
        partition_cols: Columns to partition by
        bucket: S3 bucket (if None, writes to local filesystem)

    Returns:
        Output location string
    """
    if bucket:
        # Write to S3 using awswrangler (included in aws-sdk-pandas layer)
        import awswrangler as wr

        full_path = f"s3://{bucket}/{output_path}"

        # Convert PyArrow table to pandas DataFrame for awswrangler
        df = table.to_pandas()

        wr.s3.to_parquet(
            df=df,
            path=full_path,
            dataset=True,
            partition_cols=partition_cols,
            mode="overwrite_partitions",
        )
        return full_path
    else:
        # Write to local filesystem
        os.makedirs(output_path, exist_ok=True)
        pq.write_to_dataset(
            table,
            root_path=output_path,
            partition_cols=partition_cols,
            existing_data_behavior="overwrite_or_ignore",
        )
        return output_path


def write_silver_parquet_single(
    table: pa.Table,
    output_key: str,
    bucket: Optional[str] = None,
) -> str:
    """
    Write a PyArrow table to a single Parquet file.

    Args:
        table: PyArrow table to write
        output_key: Output key/path
        bucket: S3 bucket (if None, writes to local filesystem)

    Returns:
        Output location string
    """
    if bucket:
        # Write to S3
        import io
        buffer = io.BytesIO()
        pq.write_table(table, buffer)
        buffer.seek(0)

        s3 = get_s3_client()
        s3.put_object(Bucket=bucket, Key=output_key, Body=buffer.getvalue())
        return f"s3://{bucket}/{output_key}"
    else:
        # Write to local filesystem
        os.makedirs(os.path.dirname(output_key), exist_ok=True)
        pq.write_table(table, output_key)
        return output_key
