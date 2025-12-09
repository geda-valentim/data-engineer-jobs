"""
Pass 3 Analysis tests.
Contains functions for testing Pass 3 complex analysis using Pass 1 and Pass 2 results.
"""

import os
import sys
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

# Add project root and lambda path to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src" / "lambdas" / "ai_enrichment"))

# Import after path is set
from enrich_partition.bedrock_client import BedrockClient
from enrich_partition.handler import enrich_single_job

# Import helper functions
from test_enrichment_helpers import (
    load_from_cache,
    save_to_cache,
    load_jobs_from_s3,
    save_pass_result,
    save_raw_response,
    save_job_original,
)

# Import execution helpers
from test_execution_helpers import execute_pass2, execute_pass3, display_pass3_results


def test_pass3_analysis(
    use_s3: bool = False,
    date: Optional[str] = None,
    limit: int = 5,
    use_cache: bool = False,
    save_json: bool = False,
    preloaded_jobs: Optional[List[Dict[str, Any]]] = None,
    preloaded_partition_info: Optional[Dict[str, Any]] = None
):
    """Test Pass 3 complex analysis using Pass 1 + Pass 2 results (use cache to skip previous passes if available).

    Args:
        preloaded_jobs: Optional pre-loaded jobs to avoid repeated S3 calls (for multiple model testing)
        preloaded_partition_info: Optional partition info from pre-loaded jobs
    """
    print("\n" + "=" * 120)
    print("Testing Pass 3 Complex Analysis")
    print("=" * 120)

    # Use pre-loaded jobs if provided, otherwise load from S3 or use mocks
    partition_info = preloaded_partition_info
    if preloaded_jobs is not None:
        linkedin_jobs = preloaded_jobs
        print(f"\nUsing {len(linkedin_jobs)} pre-loaded jobs")
        if partition_info:
            print(f"  Partition: {partition_info['year']}-{partition_info['month']}-{partition_info['day']} Hour {partition_info['hour']}")
    elif use_s3:
        print("\nLoading jobs from S3 bucket...")
        if date:
            print(f"  Date filter: {date}")
        else:
            print(f"  Using most recent partition(s)")
        print(f"  Requested limit: {limit} jobs")

        linkedin_jobs, partition_info = load_jobs_from_s3(date_str=date, limit=limit)
    else:
        # Use same hardcoded mocks as comparison test
        linkedin_jobs = [
            {
                "job_posting_id": "linkedin-001",
                "job_title": "Data Engineer (Cloud, ETL, Big Data, AI/ML Pipelines)",
                "company_name": "Precision Technologies",
                "job_location": "United States (Remote)",
            },
            {
                "job_posting_id": "linkedin-002",
                "job_title": "Senior Python Data Engineer - GIS/Mapping",
                "company_name": "IntagHire",
                "job_location": "Houston, TX (100% onsite)",
            },
        ]

    try:
        region = os.getenv("AWS_REGION", "us-east-1")
        model_pass1 = os.getenv("BEDROCK_MODEL_PASS1", "openai.gpt-oss-120b-1:0")
        model_pass2 = os.getenv("BEDROCK_MODEL_PASS2", "openai.gpt-oss-120b-1:0")
        model_pass3 = os.getenv("BEDROCK_MODEL_PASS3", "openai.gpt-oss-120b-1:0")

        print(f"Using model (Pass 1): {model_pass1}")
        print(f"Using model (Pass 2): {model_pass2}")
        print(f"Using model (Pass 3): {model_pass3}")
        print(f"Region: {region}")
        if use_cache:
            print(f"Cache: ENABLED (data/local/{{job_id}}/pass*-*.json)")
        print(f"Processing {len(linkedin_jobs)} jobs (Pass 1 → Pass 2 → Pass 3)...\n")

        # Create client once
        client = BedrockClient(
            model_ids={"pass1": model_pass1, "pass2": model_pass2, "pass3": model_pass3},
            region=region,
        )

        # Track results for all jobs
        all_results = []
        saved_files = []
        pass1_cache_hits = 0
        pass1_cache_misses = 0
        pass2_cache_hits = 0
        pass2_cache_misses = 0
        pass3_cache_hits = 0
        pass3_cache_misses = 0

        for i, job in enumerate(linkedin_jobs, 1):
            print(f"\n{'=' * 120}")
            print(f"[{i}/{len(linkedin_jobs)}] {job['company_name']} - {job['job_title']}")
            print(f"{'=' * 120}")

            # Save original job data from S3 (only if from S3, not mocks)
            if use_s3 or preloaded_jobs is not None:
                save_job_original(job)

            job_result = {"job": job}
            pass1_from_cache = False
            pass2_from_cache = False
            pass3_from_cache = False

            # === PASS 1: Extraction ===
            print(f"\n→ Pass 1 (Extraction)...", end=" ")

            # Always check for existing results first to avoid re-running expensive LLM calls
            cached_pass1 = load_from_cache(job, model_pass1, "pass1")
            if cached_pass1 and cached_pass1.get('pass1_success'):
                pass1_result = cached_pass1
                print("✓ (cached)")
                pass1_from_cache = True
                pass1_cache_hits += 1
            else:
                # No cache found, execute Pass 1
                pass1_cache_misses += 1
                pass1_result = enrich_single_job(job, bedrock_client=client)
                success = pass1_result.get('pass1_success', False)
                print("✓" if success else "✗")
                # Save raw response for debugging (always, even on failure)
                pass1_raw = pass1_result.pop('pass1_raw_response', None)
                if pass1_raw:
                    save_raw_response(job, "pass1", model_pass1, pass1_raw)
                # Save to cache for future runs
                if success:
                    save_to_cache(job, model_pass1, pass1_result, "pass1")

            job_result["pass1_result"] = pass1_result
            job_result["pass1_from_cache"] = pass1_from_cache

            if save_json and pass1_result.get('pass1_success') and not pass1_from_cache:
                filepath = save_pass_result(job, "pass1", model_pass1, pass1_result)
                if filepath:
                    saved_files.append(filepath)

            if not pass1_result.get('pass1_success'):
                print("  ⊘ Skipping Pass 2 and Pass 3 (Pass 1 failed)")
                all_results.append(job_result)
                continue

            # === PASS 2: Inference ===
            print(f"→ Pass 2 (Inference)...", end=" ")

            # Always check for existing results first to avoid re-running expensive LLM calls
            cached_pass2 = load_from_cache(job, model_pass2, "pass2")
            if cached_pass2:
                pass2_result_raw = cached_pass2.get('inference', cached_pass2)
                pass2_tokens = cached_pass2.get('tokens', 0)
                pass2_input_tokens = cached_pass2.get('input_tokens', 0)
                pass2_output_tokens = cached_pass2.get('output_tokens', 0)
                pass2_cost = cached_pass2.get('cost', 0.0)
                print("✓ (cached)")
                pass2_from_cache = True
                pass2_cache_hits += 1
            else:
                # No cache found, execute Pass 2
                pass2_cache_misses += 1
                pass2_result_raw, pass2_tokens, pass2_input_tokens, pass2_output_tokens, pass2_cost, pass2_raw = execute_pass2(
                    client, job, pass1_result
                )
                # Save raw response for debugging
                if pass2_raw:
                    save_raw_response(job, "pass2", model_pass2, pass2_raw)
                print("✓" if pass2_result_raw else "✗")
                # Save to cache for future runs
                if pass2_result_raw:
                    pass2_data = {
                        "inference": pass2_result_raw,
                        "tokens": pass2_tokens,
                        "input_tokens": pass2_input_tokens,
                        "output_tokens": pass2_output_tokens,
                        "cost": pass2_cost,
                    }
                    save_to_cache(job, model_pass2, pass2_data, "pass2")

            job_result["pass2_result"] = pass2_result_raw
            job_result["pass2_from_cache"] = pass2_from_cache
            job_result["pass2_success"] = pass2_result_raw is not None
            job_result["pass2_tokens"] = pass2_tokens
            job_result["pass2_input_tokens"] = pass2_input_tokens
            job_result["pass2_output_tokens"] = pass2_output_tokens
            job_result["pass2_cost"] = pass2_cost

            if save_json and pass2_result_raw and not pass2_from_cache:
                pass2_data = {
                    "inference": pass2_result_raw,
                    "tokens": pass2_tokens,
                    "input_tokens": pass2_input_tokens,
                    "output_tokens": pass2_output_tokens,
                    "cost": pass2_cost,
                }
                filepath = save_pass_result(job, "pass2", model_pass2, pass2_data)
                if filepath:
                    saved_files.append(filepath)

            if not pass2_result_raw:
                print("  ⊘ Skipping Pass 3 (Pass 2 failed)")
                all_results.append(job_result)
                continue

            # === PASS 3: Complex Analysis ===
            print(f"→ Pass 3 (Analysis)...", end=" ")

            # Always check for existing results first to avoid re-running expensive LLM calls
            cached_pass3 = load_from_cache(job, model_pass3, "pass3")
            if cached_pass3:
                pass3_analysis_raw = cached_pass3.get('analysis', {})
                pass3_summary_raw = cached_pass3.get('summary', {})
                pass3_tokens = cached_pass3.get('tokens', 0)
                pass3_input_tokens = cached_pass3.get('input_tokens', 0)
                pass3_output_tokens = cached_pass3.get('output_tokens', 0)
                pass3_cost = cached_pass3.get('cost', 0.0)
                print("✓ (cached)")
                pass3_from_cache = True
                pass3_cache_hits += 1
            else:
                # No cache found, execute Pass 3
                pass3_cache_misses += 1
                pass3_analysis_raw, pass3_summary_raw, pass3_tokens, pass3_input_tokens, pass3_output_tokens, pass3_cost, pass3_raw = execute_pass3(
                    client, job, pass1_result, pass2_result_raw
                )
                # Save raw response for debugging
                if pass3_raw:
                    save_raw_response(job, "pass3", model_pass3, pass3_raw)
                print("✓" if pass3_analysis_raw else "✗")
                # Save to cache for future runs
                if pass3_analysis_raw:
                    pass3_data = {
                        "analysis": pass3_analysis_raw,
                        "summary": pass3_summary_raw,
                        "tokens": pass3_tokens,
                        "input_tokens": pass3_input_tokens,
                        "output_tokens": pass3_output_tokens,
                        "cost": pass3_cost,
                    }
                    save_to_cache(job, model_pass3, pass3_data, "pass3")

            job_result["pass3_result"] = {
                "analysis": pass3_analysis_raw,
                "summary": pass3_summary_raw,
            }
            job_result["pass3_from_cache"] = pass3_from_cache
            job_result["pass3_success"] = pass3_analysis_raw is not None
            job_result["pass3_tokens"] = pass3_tokens
            job_result["pass3_input_tokens"] = pass3_input_tokens
            job_result["pass3_output_tokens"] = pass3_output_tokens
            job_result["pass3_cost"] = pass3_cost

            if save_json and pass3_analysis_raw and not pass3_from_cache:
                pass3_data = {
                    "analysis": pass3_analysis_raw,
                    "summary": pass3_summary_raw,
                    "tokens": pass3_tokens,
                    "input_tokens": pass3_input_tokens,
                    "output_tokens": pass3_output_tokens,
                    "cost": pass3_cost,
                }
                filepath = save_pass_result(job, "pass3", model_pass3, pass3_data)
                if filepath:
                    saved_files.append(filepath)

            # Display Pass 3 results
            if pass3_analysis_raw:
                display_pass3_results(pass3_analysis_raw, pass3_summary_raw)

            all_results.append(job_result)

        # Print cache statistics
        if use_cache:
            print(f"\n{'=' * 120}")
            print("CACHE STATISTICS")
            print(f"{'=' * 120}")
            print(f"\nPass 1: {pass1_cache_hits} hits, {pass1_cache_misses} misses")
            print(f"Pass 2: {pass2_cache_hits} hits, {pass2_cache_misses} misses")
            print(f"Pass 3: {pass3_cache_hits} hits, {pass3_cache_misses} misses")

        # Print summary
        print(f"\n{'=' * 120}")
        print("SUMMARY STATISTICS")
        print(f"{'=' * 120}")

        # Data source
        print(f"\nData Source: {'S3 Silver Bucket' if use_s3 else 'Local Mocks'}")
        if use_s3 and partition_info:
            print(f"Partition: {partition_info['year']}-{partition_info['month']}-{partition_info['day']} Hour {partition_info['hour']}")
        print(f"Jobs Processed: {len(all_results)}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Success rates
        pass1_success = sum(1 for r in all_results if r.get('pass1_result', {}).get('pass1_success'))
        pass2_success = sum(1 for r in all_results if r.get('pass2_success'))
        pass3_success = sum(1 for r in all_results if r.get('pass3_success'))
        print(f"\nPass 1 Success Rate: {pass1_success}/{len(all_results)} ({pass1_success/len(all_results)*100:.1f}%)")
        print(f"Pass 2 Success Rate: {pass2_success}/{len(all_results)} ({pass2_success/len(all_results)*100:.1f}%)")
        print(f"Pass 3 Success Rate: {pass3_success}/{len(all_results)} ({pass3_success/len(all_results)*100:.1f}%)")

        # Token and cost statistics for Pass 3
        total_pass3_input = sum(r.get('pass3_input_tokens', 0) for r in all_results)
        total_pass3_output = sum(r.get('pass3_output_tokens', 0) for r in all_results)
        total_pass3_tokens = sum(r.get('pass3_tokens', 0) for r in all_results)
        total_pass3_cost = sum(r.get('pass3_cost', 0.0) for r in all_results)

        print(f"\nPass 3 Token Statistics:")
        print(f"  Input Tokens:  {total_pass3_input:,}")
        print(f"  Output Tokens: {total_pass3_output:,}")
        print(f"  Total Tokens:  {total_pass3_tokens:,}")

        print(f"\nPass 3 Cost Analysis:")
        print(f"  Total Cost: ${total_pass3_cost:.6f}")
        print(f"  Average Cost per Job: ${total_pass3_cost/len(all_results):.6f}" if all_results else "  Average Cost per Job: $0.000000")

        # Print saved files
        if save_json and saved_files:
            print(f"\nSaved Files:")
            for f in saved_files:
                print(f"  ✓ {f}")

        return pass3_success == len(all_results)

    except Exception as e:
        print(f"\n✗ Pass 3 test FAILED: {e}")
        traceback.print_exc()
        return False
