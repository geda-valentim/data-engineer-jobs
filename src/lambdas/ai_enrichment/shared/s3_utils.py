"""
S3 utilities for reading/writing Parquet files.
Uses AWS SDK for Pandas (awswrangler).
"""

import os
import logging
from typing import List, Dict, Optional

import awswrangler as wr
import pandas as pd

logger = logging.getLogger()

SILVER_BUCKET = os.environ.get("SILVER_BUCKET")
SILVER_PREFIX = os.environ.get("SILVER_PREFIX", "linkedin/")
SILVER_AI_PREFIX = os.environ.get("SILVER_AI_PREFIX", "linkedin_ai/")


def get_silver_path(year: str, month: str, day: str, hour: str) -> str:
    """Build Silver partition path."""
    return f"s3://{SILVER_BUCKET}/{SILVER_PREFIX}year={year}/month={month}/day={day}/hour={hour}/"


def get_silver_ai_path(year: str = None, month: str = None, day: str = None, hour: str = None) -> str:
    """Build Silver-AI path (base or partition-specific)."""
    base = f"s3://{SILVER_BUCKET}/{SILVER_AI_PREFIX}"
    if all([year, month, day, hour]):
        return f"{base}year={year}/month={month}/day={day}/hour={hour}/"
    return base


def read_partition(year: str, month: str, day: str, hour: str) -> Optional[pd.DataFrame]:
    """
    Read a Silver partition as DataFrame.
    Returns None if partition doesn't exist or is empty.
    """
    path = get_silver_path(year, month, day, hour)
    logger.info(f"Reading partition: {path}")

    try:
        df = wr.s3.read_parquet(path=path)
        logger.info(f"Loaded {len(df)} records from {path}")
        return df
    except Exception as e:
        logger.warning(f"Could not read partition {path}: {e}")
        return None


def write_partition(
    df: pd.DataFrame,
    year: str,
    month: str,
    day: str,
    hour: str,
    mode: str = "overwrite"
) -> str:
    """
    Write enriched DataFrame to Silver-AI.

    Args:
        df: DataFrame to write
        year, month, day, hour: Partition values
        mode: 'overwrite' or 'append'

    Returns:
        Written path
    """
    path = get_silver_ai_path(year, month, day, hour)
    logger.info(f"Writing {len(df)} records to {path}")

    wr.s3.to_parquet(
        df=df,
        path=path,
        index=False,
        dataset=False,  # Single file per partition
        mode=mode
    )

    return path


def list_silver_partitions() -> List[Dict[str, str]]:
    """List all Silver partitions as dicts."""
    base_path = f"s3://{SILVER_BUCKET}/{SILVER_PREFIX}"

    try:
        # List year directories first
        year_dirs = wr.s3.list_directories(path=base_path)
        partitions = []

        for year_dir in year_dirs:
            if "year=" not in year_dir:
                continue

            # List recursively to get all partitions
            try:
                month_dirs = wr.s3.list_directories(path=year_dir)
                for month_dir in month_dirs:
                    day_dirs = wr.s3.list_directories(path=month_dir)
                    for day_dir in day_dirs:
                        hour_dirs = wr.s3.list_directories(path=day_dir)
                        for hour_dir in hour_dirs:
                            partition = _parse_partition_path(hour_dir, base_path)
                            if partition:
                                partitions.append(partition)
            except Exception as e:
                logger.warning(f"Error listing under {year_dir}: {e}")

        return partitions

    except Exception as e:
        logger.error(f"Error listing Silver partitions: {e}")
        return []


def list_silver_ai_partitions() -> List[Dict[str, str]]:
    """List all Silver-AI partitions as dicts."""
    base_path = get_silver_ai_path()

    try:
        year_dirs = wr.s3.list_directories(path=base_path)
        partitions = []

        for year_dir in year_dirs:
            if "year=" not in year_dir:
                continue

            try:
                month_dirs = wr.s3.list_directories(path=year_dir)
                for month_dir in month_dirs:
                    day_dirs = wr.s3.list_directories(path=month_dir)
                    for day_dir in day_dirs:
                        hour_dirs = wr.s3.list_directories(path=day_dir)
                        for hour_dir in hour_dirs:
                            partition = _parse_partition_path(hour_dir, base_path)
                            if partition:
                                partitions.append(partition)
            except Exception as e:
                logger.warning(f"Error listing under {year_dir}: {e}")

        return partitions

    except Exception as e:
        logger.warning(f"Error listing Silver-AI partitions (may not exist yet): {e}")
        return []


def _parse_partition_path(path: str, base_path: str) -> Optional[Dict[str, str]]:
    """Parse partition path into dict."""
    relative = path.replace(base_path, "").strip("/")
    parts = relative.split("/")

    partition = {}
    for part in parts:
        if "=" in part:
            key, value = part.split("=", 1)
            partition[key] = value

    if all(k in partition for k in ["year", "month", "day", "hour"]):
        return partition
    return None
