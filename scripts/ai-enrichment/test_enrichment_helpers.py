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
    job_id = job.get('job_posting_id', '')
    if not job_id:
        # If no ID, hash the job content
        content = json.dumps(job, sort_keys=True)
        job_id = hashlib.md5(content.encode()).hexdigest()
    # Clean job_id to be filesystem-safe
    return job_id.replace('/', '_').replace('\\', '_')


def get_cache_dir() -> Path:
    """Get cache directory path, creating it if needed."""
    cache_dir = Path(__file__).parent.parent.parent / "data" / "local"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def load_from_cache(job: Dict[str, Any], model_id: str, pass_name: str = "pass1") -> Optional[Dict[str, Any]]:
    """
    Load pass result from cache if available.
    Cache path: data/local/{job_id}/{pass}-{model}.json

    Args:
        job: Job dictionary
        model_id: Model ID used for this pass
        pass_name: Pass name (pass1, pass2, pass3)

    Returns:
        Cached result or None if not found
    """
    job_id = get_job_id(job)
    model_clean = model_id.replace(':', '-').replace('/', '-').replace('.', '-')
    cache_file = get_cache_dir() / job_id / f"{pass_name}-{model_clean}.json"

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
    Save pass result to cache.
    Cache path: data/local/{job_id}/{pass}-{model}.json

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
    Save a single pass result to ./{job_id}/{pass}-{model}.json

    Args:
        job: Job dictionary with job_posting_id
        pass_name: Pass name (pass1, pass2, pass3)
        model_id: Model ID used for this pass
        result: Result data to save
        base_dir: Base directory for output (default: script's parent/data/local)
        raw_response: Optional raw LLM response text to include

    Returns:
        Path to saved file or None if failed
    """
    try:
        # Get job ID
        job_id = get_job_id(job)

        # Create job directory
        if base_dir is None:
            base_dir = Path(__file__).parent.parent.parent / "data" / "local"
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


def save_raw_response(
    job: Dict[str, Any],
    pass_name: str,
    model_id: str,
    raw_response: str,
    base_dir: Optional[Path] = None,
) -> Optional[str]:
    """
    Save raw LLM response to ./{job_id}/{pass}-{model}-raw.txt

    Args:
        job: Job dictionary with job_posting_id
        pass_name: Pass name (pass1, pass2, pass3)
        model_id: Model ID used for this pass
        raw_response: Raw LLM response text
        base_dir: Base directory for output

    Returns:
        Path to saved file or None if failed
    """
    try:
        job_id = get_job_id(job)

        if base_dir is None:
            base_dir = Path(__file__).parent.parent.parent / "data" / "local"
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


def load_jobs_from_s3(date_str: Optional[str] = None, limit: int = 5) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Load jobs from S3 silver bucket.

    Args:
        date_str: Optional date in YYYY-MM-DD format
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

        # Get partition with highest hour value
        matching_partitions.sort(key=lambda p: int(p['hour']), reverse=True)
        selected = matching_partitions[0]
    else:
        # Use most recent partition overall
        partitions.sort(key=lambda p: (int(p['year']), int(p['month']), int(p['day']), int(p['hour'])), reverse=True)
        selected = partitions[0]

    # Load data from selected partition
    df = read_partition(
        year=selected['year'],
        month=selected['month'],
        day=selected['day'],
        hour=selected['hour']
    )

    if df is None or df.empty:
        raise ValueError(f"Partition {selected['year']}-{selected['month']}-{selected['day']} hour {selected['hour']} is empty")

    # Convert to list of dicts and limit
    jobs = df.head(limit).to_dict('records')

    # Return jobs and partition info
    partition_info = {
        'year': selected['year'],
        'month': selected['month'],
        'day': selected['day'],
        'hour': selected['hour']
    }

    return jobs, partition_info


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
