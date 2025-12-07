"""
Pass 2 Inference tests.
Contains functions for testing Pass 2 inference using Pass 1 results.
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
)

# Import execution helpers
from test_execution_helpers import execute_pass2, display_pass2_results


def test_pass2_inference(
    use_s3: bool = False,
    date: Optional[str] = None,
    limit: int = 5,
    use_cache: bool = False,
    save_json: bool = False
):
    """Test Pass 2 inference using Pass 1 results (use cache to skip Pass 1 if available)."""
    print("\n" + "=" * 120)
    print("Testing Pass 2 Inference")
    print("=" * 120)

    # Load jobs from S3 or use hardcoded mocks
    partition_info = None
    if use_s3:
        print("\nLoading jobs from S3 bucket...")
        if date:
            print(f"  Date: {date} (latest hour)")
        else:
            print(f"  Using most recent partition")
        print(f"  Limit: {limit} jobs")

        linkedin_jobs, partition_info = load_jobs_from_s3(date_str=date, limit=limit)
        print(f"  ✓ Loaded {len(linkedin_jobs)} jobs from partition\n")
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

        print(f"Using model (Pass 1): {model_pass1}")
        print(f"Using model (Pass 2): {model_pass2}")
        print(f"Region: {region}")
        if use_cache:
            print(f"Cache: ENABLED (data/local/{{job_id}}/pass*-*.json)")
        print(f"Processing {len(linkedin_jobs)} jobs (Pass 1 → Pass 2)...\n")

        # Create client once
        client = BedrockClient(
            model_ids={"pass1": model_pass1, "pass2": model_pass2, "pass3": model_pass2},
            region=region,
        )

        # Track results for all jobs
        all_results = []
        saved_files = []
        pass1_cache_hits = 0
        pass1_cache_misses = 0
        pass2_cache_hits = 0
        pass2_cache_misses = 0

        for i, job in enumerate(linkedin_jobs, 1):
            print(f"\n{'=' * 120}")
            print(f"[{i}/{len(linkedin_jobs)}] {job['company_name']} - {job['job_title']}")
            print(f"{'=' * 120}")

            job_result = {"job": job}
            pass1_from_cache = False

            # === PASS 1: Extraction ===
            print(f"\n→ Pass 1 (Extraction)...", end=" ")

            # Try to load Pass 1 from cache
            if use_cache:
                cached_pass1 = load_from_cache(job, model_pass1, "pass1")
                if cached_pass1 and cached_pass1.get('pass1_success'):
                    pass1_result = cached_pass1
                    print("✓ (from cache)")
                    pass1_from_cache = True
                    pass1_cache_hits += 1
                else:
                    pass1_cache_misses += 1
                    pass1_result = enrich_single_job(job, bedrock_client=client)
                    success = pass1_result.get('pass1_success', False)
                    print("✓" if success else "✗")
                    if success:
                        save_to_cache(job, model_pass1, pass1_result, "pass1")
            else:
                pass1_result = enrich_single_job(job, bedrock_client=client)
                success = pass1_result.get('pass1_success', False)
                print("✓" if success else "✗")

            job_result["pass1_result"] = pass1_result
            job_result["pass1_from_cache"] = pass1_from_cache

            # Save Pass 1 result if requested
            if save_json and pass1_result.get('pass1_success') and not pass1_from_cache:
                filepath = save_pass_result(job, "pass1", model_pass1, pass1_result)
                if filepath:
                    saved_files.append(filepath)

            if not pass1_result.get('pass1_success'):
                print("  ⊘ Skipping Pass 2 (Pass 1 failed)")
                all_results.append(job_result)
                continue

            # === PASS 2: Inference ===
            print(f"→ Pass 2 (Inference)...", end=" ")

            pass2_from_cache = False
            # Try to load Pass 2 from cache
            if use_cache:
                cached_pass2 = load_from_cache(job, model_pass2, "pass2")
                if cached_pass2:
                    pass2_result_raw = cached_pass2.get('inference', cached_pass2)
                    pass2_tokens = cached_pass2.get('tokens', 0)
                    pass2_input_tokens = cached_pass2.get('input_tokens', 0)
                    pass2_output_tokens = cached_pass2.get('output_tokens', 0)
                    pass2_cost = cached_pass2.get('cost', 0.0)
                    print("✓ (from cache)")
                    pass2_from_cache = True
                    pass2_cache_hits += 1
                else:
                    pass2_cache_misses += 1
                    pass2_result_raw, pass2_tokens, pass2_input_tokens, pass2_output_tokens, pass2_cost, pass2_raw = execute_pass2(
                        client, job, pass1_result
                    )
                    # Save raw response for debugging
                    if pass2_raw:
                        save_raw_response(job, "pass2", model_pass2, pass2_raw)
                    print("✓" if pass2_result_raw else "✗")
                    if pass2_result_raw:
                        pass2_data = {
                            "inference": pass2_result_raw,
                            "tokens": pass2_tokens,
                            "input_tokens": pass2_input_tokens,
                            "output_tokens": pass2_output_tokens,
                            "cost": pass2_cost,
                        }
                        save_to_cache(job, model_pass2, pass2_data, "pass2")
            else:
                pass2_result_raw, pass2_tokens, pass2_input_tokens, pass2_output_tokens, pass2_cost, pass2_raw = execute_pass2(
                    client, job, pass1_result
                )
                # Save raw response for debugging
                if pass2_raw:
                    save_raw_response(job, "pass2", model_pass2, pass2_raw)
                print("✓" if pass2_result_raw else "✗")

            job_result["pass2_result"] = pass2_result_raw
            job_result["pass2_from_cache"] = pass2_from_cache
            job_result["pass2_success"] = pass2_result_raw is not None
            job_result["pass2_tokens"] = pass2_tokens
            job_result["pass2_input_tokens"] = pass2_input_tokens
            job_result["pass2_output_tokens"] = pass2_output_tokens
            job_result["pass2_cost"] = pass2_cost

            # Save Pass 2 result if requested
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

            # Display Pass 2 results
            if pass2_result_raw:
                display_pass2_results(pass2_result_raw)

            all_results.append(job_result)

        # Print cache statistics
        if use_cache:
            print(f"\n{'=' * 120}")
            print("CACHE STATISTICS")
            print(f"{'=' * 120}")
            print(f"\nPass 1: {pass1_cache_hits} hits, {pass1_cache_misses} misses")
            print(f"Pass 2: {pass2_cache_hits} hits, {pass2_cache_misses} misses")

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
        print(f"\nPass 1 Success Rate: {pass1_success}/{len(all_results)} ({pass1_success/len(all_results)*100:.1f}%)")
        print(f"Pass 2 Success Rate: {pass2_success}/{len(all_results)} ({pass2_success/len(all_results)*100:.1f}%)")

        # Token and cost statistics
        total_pass2_input = sum(r.get('pass2_input_tokens', 0) for r in all_results)
        total_pass2_output = sum(r.get('pass2_output_tokens', 0) for r in all_results)
        total_pass2_tokens = sum(r.get('pass2_tokens', 0) for r in all_results)
        total_pass2_cost = sum(r.get('pass2_cost', 0.0) for r in all_results)

        print(f"\nPass 2 Token Statistics:")
        print(f"  Input Tokens:  {total_pass2_input:,}")
        print(f"  Output Tokens: {total_pass2_output:,}")
        print(f"  Total Tokens:  {total_pass2_tokens:,}")

        print(f"\nPass 2 Cost Analysis:")
        print(f"  Total Cost: ${total_pass2_cost:.6f}")
        print(f"  Average Cost per Job: ${total_pass2_cost/len(all_results):.6f}" if all_results else "  Average Cost per Job: $0.000000")

        # Print saved files
        if save_json and saved_files:
            print(f"\nSaved Files:")
            for f in saved_files:
                print(f"  ✓ {f}")

        return pass2_success == len(all_results)

    except Exception as e:
        print(f"\n✗ Pass 2 test FAILED: {e}")
        traceback.print_exc()
        return False
