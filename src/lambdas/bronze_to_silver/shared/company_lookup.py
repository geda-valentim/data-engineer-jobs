"""
Centralized company lookup utility.

Provides a simple interface to lookup company data from the Silver layer
with automatic bucket resolution and caching support.

Usage:
    from bronze_to_silver.shared.company_lookup import CompanyLookup

    # Initialize (once per Lambda cold start)
    lookup = CompanyLookup()

    # Get company by ID
    company = lookup.get_company("1028")
    print(company["name"])  # "Oracle"

    # Preload specific buckets for batch processing
    lookup.preload_bucket(23)

    # Get multiple companies
    companies = lookup.get_companies(["1028", "3364", "3409"])
"""

import hashlib
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import pyarrow.parquet as pq

# Configuration - Change these if project structure changes
NUM_BUCKETS = 50
SILVER_BUCKET = os.environ.get("SILVER_BUCKET", "data-engineer-jobs-silver")
SILVER_PREFIX = "linkedin_companies"
LOCAL_SILVER_PATH = os.environ.get(
    "LOCAL_SILVER_PATH",
    str(Path(__file__).parent.parent.parent.parent.parent / "data" / "local" / "silver" / "linkedin_companies_partitioned")
)


def compute_bucket(company_id: str) -> int:
    """
    Compute bucket number from company_id using MD5 hash.

    This is the single source of truth for bucket calculation.
    If partitioning strategy changes, update only this function.

    Args:
        company_id: Company ID string

    Returns:
        Bucket number (0 to NUM_BUCKETS-1)
    """
    hash_val = int(hashlib.md5(str(company_id).encode()).hexdigest(), 16)
    return hash_val % NUM_BUCKETS


def get_bucket_path(bucket: int, use_s3: bool = False) -> str:
    """
    Get the path to a specific bucket partition.

    Args:
        bucket: Bucket number
        use_s3: If True, returns S3 path; otherwise local path

    Returns:
        Path string to the bucket partition
    """
    if use_s3:
        return f"s3://{SILVER_BUCKET}/{SILVER_PREFIX}/bucket={bucket}/"
    else:
        return str(Path(LOCAL_SILVER_PATH) / f"bucket={bucket}")


class CompanyLookup:
    """
    Centralized company data lookup with caching.

    Handles bucket resolution automatically and caches loaded data
    for efficient repeated lookups.
    """

    def __init__(self, use_s3: bool = False, cache_size: int = 10):
        """
        Initialize the company lookup.

        Args:
            use_s3: If True, reads from S3; otherwise from local filesystem
            cache_size: Number of buckets to keep in LRU cache
        """
        self.use_s3 = use_s3
        self.cache_size = cache_size
        self._bucket_cache: dict[int, dict[str, dict]] = {}
        self._company_index: dict[str, int] = {}  # company_id -> bucket

    def _load_bucket(self, bucket: int) -> dict[str, dict]:
        """
        Load all companies from a bucket into memory.

        Args:
            bucket: Bucket number to load

        Returns:
            Dictionary mapping company_id to company data
        """
        if bucket in self._bucket_cache:
            return self._bucket_cache[bucket]

        bucket_path = get_bucket_path(bucket, self.use_s3)

        try:
            if self.use_s3:
                import awswrangler as wr
                df = wr.s3.read_parquet(path=bucket_path)
            else:
                table = pq.read_table(bucket_path)
                df = table.to_pandas()
            companies = {}
            for _, row in df.iterrows():
                company_id = str(row["company_id"])
                companies[company_id] = row.to_dict()
                self._company_index[company_id] = bucket

            # Manage cache size
            if len(self._bucket_cache) >= self.cache_size:
                # Remove oldest bucket (simple FIFO)
                oldest = next(iter(self._bucket_cache))
                del self._bucket_cache[oldest]

            self._bucket_cache[bucket] = companies
            return companies

        except Exception as e:
            print(f"Error loading bucket {bucket}: {e}")
            return {}

    def get_company(self, company_id: str) -> Optional[dict[str, Any]]:
        """
        Get company data by company_id.

        Automatically resolves the correct bucket and loads data.

        Args:
            company_id: Company ID to lookup

        Returns:
            Company data dictionary or None if not found
        """
        company_id = str(company_id)

        # Check if already indexed
        if company_id in self._company_index:
            bucket = self._company_index[company_id]
            if bucket in self._bucket_cache:
                return self._bucket_cache[bucket].get(company_id)

        # Compute bucket and load
        bucket = compute_bucket(company_id)
        companies = self._load_bucket(bucket)
        return companies.get(company_id)

    def get_companies(self, company_ids: list[str]) -> dict[str, Optional[dict[str, Any]]]:
        """
        Get multiple companies by their IDs.

        Optimizes by grouping lookups by bucket.

        Args:
            company_ids: List of company IDs to lookup

        Returns:
            Dictionary mapping company_id to company data (or None)
        """
        # Group by bucket for efficient loading
        by_bucket: dict[int, list[str]] = {}
        for cid in company_ids:
            cid = str(cid)
            bucket = compute_bucket(cid)
            if bucket not in by_bucket:
                by_bucket[bucket] = []
            by_bucket[bucket].append(cid)

        # Load buckets and collect results
        results = {}
        for bucket, cids in by_bucket.items():
            companies = self._load_bucket(bucket)
            for cid in cids:
                results[cid] = companies.get(cid)

        return results

    def preload_bucket(self, bucket: int) -> int:
        """
        Preload a specific bucket into cache.

        Useful when you know which buckets you'll need.

        Args:
            bucket: Bucket number to preload

        Returns:
            Number of companies loaded
        """
        companies = self._load_bucket(bucket)
        return len(companies)

    def preload_for_companies(self, company_ids: list[str]) -> int:
        """
        Preload all buckets needed for a list of company IDs.

        Args:
            company_ids: List of company IDs

        Returns:
            Total number of companies loaded across all buckets
        """
        buckets = set(compute_bucket(str(cid)) for cid in company_ids)
        total = 0
        for bucket in buckets:
            total += self.preload_bucket(bucket)
        return total

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return {
            "buckets_cached": len(self._bucket_cache),
            "companies_indexed": len(self._company_index),
            "cache_size_limit": self.cache_size,
            "use_s3": self.use_s3,
        }

    def clear_cache(self):
        """Clear all cached data."""
        self._bucket_cache.clear()
        self._company_index.clear()


# Singleton instance for convenience
_default_lookup: Optional[CompanyLookup] = None


def get_company_lookup(use_s3: bool = False, cache_size: int = 10) -> CompanyLookup:
    """
    Get or create the default CompanyLookup instance.

    Args:
        use_s3: If True, reads from S3
        cache_size: Number of buckets to cache

    Returns:
        CompanyLookup instance
    """
    global _default_lookup
    if _default_lookup is None:
        _default_lookup = CompanyLookup(use_s3=use_s3, cache_size=cache_size)
    return _default_lookup


# Convenience functions for simple usage
def get_company(company_id: str, use_s3: bool = False) -> Optional[dict[str, Any]]:
    """
    Quick lookup of a single company.

    Args:
        company_id: Company ID to lookup
        use_s3: If True, reads from S3

    Returns:
        Company data dictionary or None
    """
    lookup = get_company_lookup(use_s3=use_s3)
    return lookup.get_company(company_id)


def get_companies(company_ids: list[str], use_s3: bool = False) -> dict[str, Optional[dict[str, Any]]]:
    """
    Quick lookup of multiple companies.

    Args:
        company_ids: List of company IDs
        use_s3: If True, reads from S3

    Returns:
        Dictionary mapping company_id to company data
    """
    lookup = get_company_lookup(use_s3=use_s3)
    return lookup.get_companies(company_ids)
