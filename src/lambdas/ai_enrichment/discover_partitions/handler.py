"""
Lambda: DiscoverPartitions
Finds Silver partitions that haven't been processed to Silver-AI yet.
"""

import os
import logging
from typing import Dict, Any, List, Set

import awswrangler as wr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SILVER_BUCKET = os.environ.get("SILVER_BUCKET")
SILVER_PREFIX = os.environ.get("SILVER_PREFIX", "linkedin/")
SILVER_AI_PREFIX = os.environ.get("SILVER_AI_PREFIX", "linkedin_ai/")
MAX_PARTITIONS = int(os.environ.get("MAX_PARTITIONS", "10"))


def list_partitions(bucket: str, prefix: str) -> Set[str]:
    """
    List all partitions under a prefix.

    Returns set of partition keys like "year=2024/month=01/day=15/hour=12"
    """
    path = f"s3://{bucket}/{prefix}"

    try:
        directories = wr.s3.list_directories(path)
        partitions = set()

        for dir_path in directories:
            # Extract partition key from path
            parts = dir_path.replace(path, "").strip("/")
            if parts and "year=" in parts:
                partitions.add(parts)

        return partitions

    except Exception as e:
        logger.error(f"Error listing partitions at {path}: {e}")
        return set()


def parse_partition_key(partition_key: str) -> Dict[str, str]:
    """
    Parse partition key string into dict.

    Args:
        partition_key: "year=2024/month=01/day=15/hour=12"

    Returns:
        {"year": "2024", "month": "01", "day": "15", "hour": "12"}
    """
    result = {}
    for part in partition_key.split("/"):
        if "=" in part:
            key, value = part.split("=", 1)
            result[key] = value
    return result


def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Discover partitions pending enrichment.

    Returns:
    {
        "has_work": bool,
        "partitions": [
            {"year": "2025", "month": "12", "day": "05", "hour": "10"},
            ...
        ],
        "total_pending": int,
        "processing_count": int
    }
    """
    logger.info(f"DiscoverPartitions started - bucket={SILVER_BUCKET}")
    logger.info(f"Silver prefix: {SILVER_PREFIX}, Silver-AI prefix: {SILVER_AI_PREFIX}")

    if not SILVER_BUCKET:
        raise ValueError("SILVER_BUCKET environment variable not set")

    # List existing partitions
    silver_partitions = list_partitions(SILVER_BUCKET, SILVER_PREFIX)
    silver_ai_partitions = list_partitions(SILVER_BUCKET, SILVER_AI_PREFIX)

    logger.info(f"Found {len(silver_partitions)} Silver partitions")
    logger.info(f"Found {len(silver_ai_partitions)} Silver-AI partitions")

    # Compute pending (Silver - Silver-AI)
    pending_partitions = silver_partitions - silver_ai_partitions
    logger.info(f"Pending partitions: {len(pending_partitions)}")

    # Sort by partition key (oldest first) and limit
    sorted_pending = sorted(pending_partitions)[:MAX_PARTITIONS]

    # Parse into structured format
    partitions = [parse_partition_key(pk) for pk in sorted_pending]

    result = {
        "has_work": len(partitions) > 0,
        "partitions": partitions,
        "total_pending": len(pending_partitions),
        "processing_count": len(partitions)
    }

    logger.info(f"Returning {len(partitions)} partitions for processing")
    return result


if __name__ == "__main__":
    # Local testing
    from dotenv import load_dotenv
    load_dotenv()

    result = handler({}, None)
    print(result)
