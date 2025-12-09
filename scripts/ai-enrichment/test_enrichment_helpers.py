"""
Helper functions for AI Enrichment tests.
Includes S3 loading and JSON export.
"""

import os
import json
import hashlib
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any


def get_job_id(job: Dict[str, Any]) -> str:
    """Get job ID for file naming, generating hash if needed."""
    import pandas as pd
    import numpy as np

    job_id = job.get('job_posting_id', '')

    # Handle pandas NaN/None values for job_id
    if pd.isna(job_id) or not job_id:
        # If no ID, hash the job content
        # Convert pandas NaN/NaT to None for JSON serialization

        def sanitize_value(v):
            """Convert pandas NaN/NaT to None for JSON serialization."""
            # Handle collections first (before checking pd.isna which fails on arrays)
            if isinstance(v, dict):
                return {k: sanitize_value(val) for k, val in v.items()}
            elif isinstance(v, (list, tuple)):
                return [sanitize_value(item) for item in v]
            elif isinstance(v, np.ndarray):
                return [sanitize_value(item) for item in v.tolist()]
            # Handle scalar values
            elif isinstance(v, (np.integer, np.floating)):
                return v.item()
            # Check for NaN/NaT (only works on scalars)
            try:
                if pd.isna(v):
                    return None
            except (ValueError, TypeError):
                # pd.isna() failed, return as-is
                pass
            return v

        sanitized_job = {k: sanitize_value(v) for k, v in job.items()}
        content = json.dumps(sanitized_job, sort_keys=True, default=str)
        job_id = hashlib.md5(content.encode()).hexdigest()
    # Clean job_id to be filesystem-safe
    return str(job_id).replace('/', '_').replace('\\', '_')


def get_cache_dir(layer: str = "bronze") -> Path:
    """
    Get cache directory path for AI enrichment following Medallion Architecture.

    Args:
        layer: Data layer (bronze/silver/gold). Default: bronze

    Returns:
        Path to cache directory for the specified layer

    Structure:
        data/local/ai_enrichment/
        ├── bronze/           # JSON raw results from LLMs
        │   └── {job_id}/
        │       ├── pass1-{model}.json
        │       ├── pass2-{model}.json
        │       └── pass3-{model}.json
        ├── silver/           # Parquet with Delta Lake (future)
        │   └── delta/
        │       └── enriched_jobs/
        └── gold/             # Aggregated analysis (future)
            └── delta/
                └── model_comparisons/
    """
    base_dir = Path(__file__).parent.parent.parent / "data" / "local" / "ai_enrichment"

    if layer == "bronze":
        cache_dir = base_dir / "bronze"
    elif layer == "silver":
        cache_dir = base_dir / "silver"
    elif layer == "gold":
        cache_dir = base_dir / "gold"
    else:
        raise ValueError(f"Invalid layer: {layer}. Must be 'bronze', 'silver', or 'gold'")

    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def load_from_cache(job: Dict[str, Any], model_id: str, pass_name: str = "pass1") -> Optional[Dict[str, Any]]:
    """
    Load pass result from cache if available (Bronze layer - JSON).
    Cache path: data/local/ai_enrichment/bronze/{job_id}/{pass}-{model}.json

    Args:
        job: Job dictionary
        model_id: Model ID used for this pass
        pass_name: Pass name (pass1, pass2, pass3)

    Returns:
        Cached result or None if not found
    """
    job_id = get_job_id(job)
    model_clean = model_id.replace(':', '-').replace('/', '-').replace('.', '-')
    cache_file = get_cache_dir(layer="bronze") / job_id / f"{pass_name}-{model_clean}.json"

    if cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
                return cached.get('result', cached)
        except Exception as e:
            print(f"Warning: Could not load cache for {job_id}/{pass_name}: {e}")
            return None
    return None


def save_to_cache(job: Dict[str, Any], model_id: str, result: Dict[str, Any], pass_name: str = "pass1"):
    """
    Save pass result to cache (Bronze layer - JSON).
    Cache path: data/local/ai_enrichment/bronze/{job_id}/{pass}-{model}.json

    Args:
        job: Job dictionary
        model_id: Model ID used for this pass
        result: Result data to cache
        pass_name: Pass name (pass1, pass2, pass3)
    """
    save_pass_result(job, pass_name, model_id, result)


def save_pass_result(
    job: Dict[str, Any],
    pass_name: str,
    model_id: str,
    result: Dict[str, Any],
    base_dir: Optional[Path] = None,
    raw_response: Optional[str] = None,
) -> Optional[str]:
    """
    Save a single pass result to Bronze layer (JSON).
    Path: data/local/ai_enrichment/bronze/{job_id}/{pass}-{model}.json

    Args:
        job: Job dictionary with job_posting_id
        pass_name: Pass name (pass1, pass2, pass3)
        model_id: Model ID used for this pass
        result: Result data to save
        base_dir: Base directory for output (default: bronze)
        raw_response: Optional raw LLM response text to include

    Returns:
        Path to saved file or None if failed
    """
    try:
        # Get job ID
        job_id = get_job_id(job)

        # Create job directory in Bronze layer
        if base_dir is None:
            base_dir = get_cache_dir(layer="bronze")
        job_dir = base_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Clean model ID for filename (replace special chars)
        model_clean = model_id.replace(':', '-').replace('/', '-').replace('.', '-')

        # Generate filename: {pass}-{model}.json
        filename = f"{pass_name}-{model_clean}.json"
        filepath = job_dir / filename

        # Build output structure
        output = {
            "metadata": {
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "job_posting_id": job.get("job_posting_id"),
                "job_title": job.get("job_title"),
                "company_name": job.get("company_name"),
                "job_location": job.get("job_location"),
                "pass_name": pass_name,
                "model_id": model_id,
            },
            "result": result,
        }

        # Include raw response if provided
        if raw_response is not None:
            output["raw_response"] = raw_response

        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)

        return str(filepath)

    except Exception as e:
        print(f"\n⚠ Warning: Could not save {pass_name} result: {e}")
        traceback.print_exc()
        return None


def save_job_original(job: Dict[str, Any], base_dir: Optional[Path] = None) -> Optional[str]:
    """
    Save original job data from S3 to Bronze layer.
    Path: data/local/ai_enrichment/bronze/{job_id}/job-original.json

    Args:
        job: Job dictionary from S3
        base_dir: Base directory for output (default: bronze)

    Returns:
        Path to saved file or None if failed
    """
    try:
        job_id = get_job_id(job)

        if base_dir is None:
            base_dir = get_cache_dir(layer="bronze")
        job_dir = base_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        filepath = job_dir / "job-original.json"

        # Only save if doesn't exist (don't overwrite)
        if not filepath.exists():
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(job, f, indent=2, ensure_ascii=False, default=str)

        return str(filepath)

    except Exception as e:
        print(f"\n⚠ Warning: Could not save original job data: {e}")
        return None


def save_raw_response(
    job: Dict[str, Any],
    pass_name: str,
    model_id: str,
    raw_response: str,
    base_dir: Optional[Path] = None,
) -> Optional[str]:
    """
    Save raw LLM response to Bronze layer.
    Path: data/local/ai_enrichment/bronze/{job_id}/{pass}-{model}-raw.txt

    Args:
        job: Job dictionary with job_posting_id
        pass_name: Pass name (pass1, pass2, pass3)
        model_id: Model ID used for this pass
        raw_response: Raw LLM response text
        base_dir: Base directory for output (default: bronze)

    Returns:
        Path to saved file or None if failed
    """
    try:
        job_id = get_job_id(job)

        if base_dir is None:
            base_dir = get_cache_dir(layer="bronze")
        job_dir = base_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        model_clean = model_id.replace(':', '-').replace('/', '-').replace('.', '-')
        filename = f"{pass_name}-{model_clean}-raw.txt"
        filepath = job_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(raw_response)

        return str(filepath)

    except Exception as e:
        print(f"\n⚠ Warning: Could not save raw response: {e}")
        return None


def sanitize_job_dict(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize job dictionary by converting pandas NaN/NaT to None.

    Args:
        job: Job dictionary potentially containing pandas NaN values

    Returns:
        Sanitized job dictionary with None instead of NaN
    """
    import pandas as pd
    import numpy as np

    def sanitize_value(v):
        """Convert pandas NaN/NaT to None for JSON serialization."""
        # Handle collections first (before checking pd.isna which fails on arrays)
        if isinstance(v, dict):
            return {k: sanitize_value(val) for k, val in v.items()}
        elif isinstance(v, (list, tuple)):
            return [sanitize_value(item) for item in v]
        elif isinstance(v, np.ndarray):
            return [sanitize_value(item) for item in v.tolist()]
        # Handle scalar values
        elif isinstance(v, (np.integer, np.floating)):
            return v.item()
        # Check for NaN/NaT (only works on scalars)
        try:
            if pd.isna(v):
                return None
        except (ValueError, TypeError):
            # pd.isna() failed, return as-is
            pass
        return v

    return {k: sanitize_value(v) for k, v in job.items()}


def load_jobs_from_s3(date_str: Optional[str] = None, limit: int = 5) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Load jobs from S3 silver bucket across multiple partitions if needed.

    Args:
        date_str: Optional date in YYYY-MM-DD format (will load from all hours of that day)
        limit: Number of jobs to return

    Returns:
        Tuple of (list of job dictionaries, partition info dict)
    """
    from shared.s3_utils import list_silver_partitions, read_partition

    # Get available partitions
    partitions = list_silver_partitions()

    if not partitions:
        raise ValueError("No partitions found in S3 bucket")

    # Filter partitions based on date_str
    if date_str:
        # Validate date format
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            target_year = str(date_obj.year)
            target_month = f"{date_obj.month:02d}"
            target_day = f"{date_obj.day:02d}"
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD")

        # Filter partitions matching the date
        matching_partitions = [
            p for p in partitions
            if p['year'] == target_year and p['month'] == target_month and p['day'] == target_day
        ]

        if not matching_partitions:
            # Show available dates to help user
            available_dates = {}
            for p in partitions:
                date_key = f"{p['year']}-{p['month']}-{p['day']}"
                if date_key not in available_dates:
                    available_dates[date_key] = []
                available_dates[date_key].append(p['hour'])

            error_msg = f"No partitions found for date {date_str}\n\nAvailable dates:\n"
            for date_key in sorted(available_dates.keys(), reverse=True)[:10]:
                hours = available_dates[date_key]
                error_msg += f"  {date_key} (hours: {min(hours)}-{max(hours)})\n"
            raise ValueError(error_msg)

        # Sort by hour descending (most recent first)
        matching_partitions.sort(key=lambda p: int(p['hour']), reverse=True)
        partitions_to_load = matching_partitions
    else:
        # Use most recent partitions overall
        partitions.sort(key=lambda p: (int(p['year']), int(p['month']), int(p['day']), int(p['hour'])), reverse=True)
        partitions_to_load = partitions

    # Load jobs from multiple partitions until we reach the limit
    all_jobs = []
    first_partition = None
    partitions_used = 0

    print(f"\n  Loading up to {limit} jobs from partition(s)...")

    for partition in partitions_to_load:
        if len(all_jobs) >= limit:
            break

        partition_label = f"{partition['year']}-{partition['month']}-{partition['day']} Hour {partition['hour']}"

        df = read_partition(
            year=partition['year'],
            month=partition['month'],
            day=partition['day'],
            hour=partition['hour']
        )

        if df is None or df.empty:
            print(f"    Partition {partition_label}: 0 jobs (empty)")
            continue

        # Track first partition for info
        if first_partition is None:
            first_partition = partition

        # How many more jobs do we need?
        remaining = limit - len(all_jobs)
        total_available = len(df)
        jobs_to_take = min(remaining, total_available)

        # Convert DataFrame to list of dicts and sanitize pandas NaN values
        partition_jobs = df.head(jobs_to_take).to_dict('records')
        sanitized_jobs = [sanitize_job_dict(job) for job in partition_jobs]

        # Filter out invalid jobs (missing critical fields)
        valid_jobs = []
        skipped = 0
        for job in sanitized_jobs:
            # Job must have at least job_title and company_name
            if job.get('job_title') and job.get('company_name'):
                valid_jobs.append(job)
            else:
                skipped += 1

        all_jobs.extend(valid_jobs)
        partitions_used += 1

        loaded_msg = f"    Partition {partition_label}: {len(valid_jobs)} jobs loaded"
        if skipped > 0:
            loaded_msg += f" ({skipped} skipped - invalid)"
        loaded_msg += f" (from {total_available} available)"
        print(loaded_msg)

    if not all_jobs:
        raise ValueError(f"No jobs found in any partition")

    print(f"\n  {'=' * 80}")
    print(f"  TOTAL LOADED: {len(all_jobs)} jobs from {partitions_used} partition(s)")
    if len(all_jobs) < limit:
        print(f"  WARNING: Requested {limit} jobs but only {len(all_jobs)} were available")
    print(f"  {'=' * 80}")

    # Return jobs and partition info (from first partition)
    partition_info = {
        'year': first_partition['year'],
        'month': first_partition['month'],
        'day': first_partition['day'],
        'hour': first_partition['hour'],
        'partitions_used': partitions_used
    }

    return all_jobs, partition_info


def print_comparison_table(jobs, results):
    """Print a formatted comparison table of extraction results."""

    # Key fields to compare
    comparison_fields = [
        ("Success", lambda r: "✓" if r.get('pass1_success') else "✗"),
        ("Salary Min", lambda r: f"${r.get('ext_salary_min', 0):,.0f}" if r.get('ext_salary_min') else "-"),
        ("Salary Max", lambda r: f"${r.get('ext_salary_max', 0):,.0f}" if r.get('ext_salary_max') else "-"),
        ("Yrs Exp Min", lambda r: r.get('ext_years_experience_min') or "-"),
        ("Yrs Exp Max", lambda r: r.get('ext_years_experience_max') or "-"),
        ("Work Model", lambda r: r.get('ext_work_model_stated') or "-"),
        ("Visa", lambda r: r.get('ext_visa_sponsorship_stated') or "-"),
        ("Contract", lambda r: r.get('ext_contract_type') or "-"),
        ("Must Skills", lambda r: len(r.get('ext_must_have_hard_skills', []))),
        ("Nice Skills", lambda r: len(r.get('ext_nice_to_have_hard_skills', []))),
        ("Equity", lambda r: "Yes" if r.get('ext_equity_mentioned') else "No"),
        ("PTO", lambda r: r.get('ext_pto_policy') or "-"),
    ]

    # Print header
    print(f"{'Company':<25} | ", end="")
    for field_name, _ in comparison_fields:
        print(f"{field_name:>12} | ", end="")
    print()
    print("-" * 120)

    # Print each job's results
    for job, result in zip(jobs, results):
        company = job['company_name'][:24]
        print(f"{company:<25} | ", end="")

        for _, extractor in comparison_fields:
            value = extractor(result)
            print(f"{str(value):>12} | ", end="")
        print()
