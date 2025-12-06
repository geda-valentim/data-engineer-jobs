"""
Helper functions for AI Enrichment tests.
Includes cache management, S3 loading, and JSON export.
"""

import os
import json
import hashlib
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any


def get_cache_dir() -> Path:
    """Get cache directory path, creating it if needed."""
    cache_dir = Path(__file__).parent.parent.parent / ".cache" / "enrichment"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_cache_key(job: Dict[str, Any]) -> str:
    """Generate cache key from job posting ID."""
    job_id = job.get('job_posting_id', '')
    if not job_id:
        # If no ID, hash the job content
        content = json.dumps(job, sort_keys=True)
        job_id = hashlib.md5(content.encode()).hexdigest()
    # Clean job_id to be filesystem-safe
    return job_id.replace('/', '_').replace('\\', '_')


def load_from_cache(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Load enrichment result from cache if available.

    Args:
        job: Job dictionary

    Returns:
        Cached result or None if not found
    """
    cache_key = get_cache_key(job)
    cache_file = get_cache_dir() / f"{cache_key}.json"

    if cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
                return cached
        except Exception as e:
            print(f"Warning: Could not load cache for {cache_key}: {e}")
            return None
    return None


def save_to_cache(job: Dict[str, Any], result: Dict[str, Any], pass2_result: Optional[Dict[str, Any]] = None):
    """
    Save enrichment result to cache (Pass 1 and optionally Pass 2/3).

    Args:
        job: Job dictionary
        result: Pass 1 enrichment result
        pass2_result: Optional Pass 2/3 result dict
    """
    cache_key = get_cache_key(job)
    cache_file = get_cache_dir() / f"{cache_key}.json"

    try:
        # Load existing cache if present
        existing_cache = {}
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    existing_cache = json.load(f)
            except:
                pass

        # Merge Pass 1 result
        cache_data = {**existing_cache, **result}

        # Add Pass 2/3 result if provided
        if pass2_result:
            cache_data.update(pass2_result)

        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2, default=str)
    except Exception as e:
        print(f"Warning: Could not save cache for {cache_key}: {e}")


def save_results_to_json(
    results: List[Dict[str, Any]],
    test_type: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Save enrichment results to JSON file in data/ folder.

    Args:
        results: List of job results with pass1/pass2/pass3 data
        test_type: Type of test (pass1, pass2, pass3, compare)
        metadata: Optional metadata dict (data_source, partition, etc.)

    Returns:
        Path to saved file or None if failed
    """
    try:
        # Create data directory if it doesn't exist
        data_dir = Path(__file__).parent.parent.parent / "data" / "local"
        data_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"enrichment_results_{test_type}_{timestamp}.json"
        filepath = data_dir / filename

        # Build output structure
        output = {
            "metadata": {
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "test_type": test_type,
                "jobs_processed": len(results),
            },
            "jobs": []
        }

        # Add optional metadata
        if metadata:
            output["metadata"].update(metadata)

        # Process each job result
        for job_result in results:
            job_data = {
                "job_info": {
                    "job_posting_id": job_result["job"].get("job_posting_id"),
                    "job_title": job_result["job"].get("job_title"),
                    "company_name": job_result["job"].get("company_name"),
                    "job_location": job_result["job"].get("job_location"),
                }
            }

            # Add Pass 1 data if available
            if job_result.get("pass1_result"):
                pass1 = job_result["pass1_result"]
                job_data["pass1"] = {
                    "success": pass1.get("pass1_success", False),
                    "from_cache": job_result.get("pass1_from_cache", False),
                    "extraction": {
                        "skills_classified": {
                            "must_have_hard_skills": pass1.get("ext_must_have_hard_skills"),
                            "nice_to_have_hard_skills": pass1.get("ext_nice_to_have_hard_skills"),
                            "must_have_soft_skills": pass1.get("ext_must_have_soft_skills"),
                            "nice_to_have_soft_skills": pass1.get("ext_nice_to_have_soft_skills"),
                            "certifications_mentioned": pass1.get("ext_certifications_mentioned"),
                            "years_experience_min": pass1.get("ext_years_experience_min"),
                            "years_experience_max": pass1.get("ext_years_experience_max"),
                            "years_experience_text": pass1.get("ext_years_experience_text"),
                            "education_stated": pass1.get("ext_education_stated"),
                            "llm_genai_mentioned": pass1.get("ext_llm_genai_mentioned"),
                            "feature_store_mentioned": pass1.get("ext_feature_store_mentioned"),
                        },
                        "compensation": {
                            "salary_disclosed": pass1.get("ext_salary_disclosed"),
                            "salary_min": pass1.get("ext_salary_min"),
                            "salary_max": pass1.get("ext_salary_max"),
                            "salary_currency": pass1.get("ext_salary_currency"),
                            "salary_period": pass1.get("ext_salary_period"),
                        },
                        "work_authorization": {
                            "visa_sponsorship_stated": pass1.get("ext_visa_sponsorship_stated"),
                            "security_clearance_stated": pass1.get("ext_security_clearance_stated"),
                        },
                        "work_model": {
                            "work_model_stated": pass1.get("ext_work_model_stated"),
                            "employment_type_stated": pass1.get("ext_employment_type_stated"),
                        },
                    },
                    "tokens": pass1.get("total_tokens_used", 0),
                    "cost": pass1.get("total_cost", 0.0),
                }

            # Add Pass 2 data if available
            if job_result.get("pass2_result"):
                job_data["pass2"] = {
                    "success": job_result.get("pass2_success", False),
                    "from_cache": job_result.get("pass2_from_cache", False),
                    "inference": job_result["pass2_result"],
                    "tokens": job_result.get("pass2_tokens", 0),
                    "cost": job_result.get("pass2_cost", 0.0),
                }

            # Add Pass 3 data if available
            if job_result.get("pass3_result"):
                job_data["pass3"] = {
                    "success": job_result.get("pass3_success", False),
                    "from_cache": job_result.get("pass3_from_cache", False),
                    "analysis": job_result["pass3_result"].get("analysis", {}),
                    "summary": job_result["pass3_result"].get("summary", {}),
                    "tokens": job_result.get("pass3_tokens", 0),
                    "cost": job_result.get("pass3_cost", 0.0),
                }

            output["jobs"].append(job_data)

        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)

        return str(filepath)

    except Exception as e:
        print(f"\n⚠ Warning: Could not save results to JSON: {e}")
        traceback.print_exc()
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
