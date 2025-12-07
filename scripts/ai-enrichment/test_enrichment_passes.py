"""
Test functions for AI Enrichment passes (Pass 1, Pass 2, Pass 3).
Contains the main test execution logic for each enrichment pass.
"""

import os
import sys
import json
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
from enrich_partition.prompts.pass2_inference import build_pass2_prompt
from enrich_partition.prompts.pass3_complex import build_pass3_prompt
from enrich_partition.parsers.json_parser import parse_llm_json
from enrich_partition.parsers.validators import validate_inference_response, validate_analysis_response

# Import helper functions from test_enrichment_helpers
from test_enrichment_helpers import (
    get_job_id,
    load_from_cache,
    save_to_cache,
    load_jobs_from_s3,
    save_pass_result,
    print_comparison_table,
)

# Model configuration with pricing (per 1M tokens)
AVAILABLE_MODELS = {
    "gpt-oss": {
        "id": "openai.gpt-oss-120b-1:0",
        "name": "OpenAI GPT-OSS 120B",
        "input_cost_per_1m": 0.15,
        "output_cost_per_1m": 0.60,
    },
    "minimax-m2": {
        "id": "minimax.minimax-m2",
        "name": "MiniMax M2",
        "input_cost_per_1m": 0.30,
        "output_cost_per_1m": 1.20,
    },
    "qwen3-235b": {
        "id": "qwen.qwen3-vl-235b-a22b",
        "name": "Qwen3 235B",
        "input_cost_per_1m": 0.22,
        "output_cost_per_1m": 0.88,
    },
    "mistral-large": {
        "id": "mistral.mistral-large-3-675b-instruct",
        "name": "Mistral Large 675B",
        "input_cost_per_1m": 2.00,
        "output_cost_per_1m": 6.00,
    },
    "gemma-27b": {
        "id": "google.gemma-3-27b-it",
        "name": "Gemma 3 27B",
        "input_cost_per_1m": 0.23,
        "output_cost_per_1m": 0.38,
    },
}


def test_multiple_jobs_comparison(use_s3: bool = False, date: Optional[str] = None, limit: int = 5, use_cache: bool = False, save_json: bool = False):
    """Test Pass 1 extraction with multiple real LinkedIn jobs and compare results."""
    print("\n" + "=" * 60)
    print("Testing Pass 1 Extraction - Multiple Jobs Comparison")
    print("=" * 60)

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
        # Real LinkedIn jobs (hardcoded mocks)
        linkedin_jobs = [
        {
            "job_posting_id": "linkedin-001",
            "job_title": "Data Engineer (Cloud, ETL, Big Data, AI/ML Pipelines)",
            "company_name": "Precision Technologies",
            "job_location": "United States (Remote)",
            "job_description_text": """
Design, build, and maintain scalable data pipelines for ingestion, processing, transformation, and storage using modern ETL/ELT frameworks.
Develop and optimize data workflows on cloud platforms such as AWS, Azure, or Google Cloud using services like S3, Redshift, Glue, Databricks, Synapse, Dataflow, or BigQuery.
Work with batch and streaming data technologies such as Spark, Kafka, Airflow, Snowflake, Hadoop, Flink, or Delta Lake to support high-volume data workloads.
Implement robust data models, warehouse structures, and lakehouse architectures to enable analytics, BI reporting, and operational insights.
Build, automate, and maintain CI/CD pipelines for data engineering workflows using tools like Git, Jenkins, Docker, and Terraform.
Collaborate with Data Scientists and AI/ML engineers to build feature pipelines, deploy models, and operationalize machine learning workflows.
Ensure data quality, governance, security, and compliance across the entire data lifecycle using frameworks such as Great Expectations or cloud-native monitoring tools.
Perform root-cause analysis on data issues, optimize performance, and implement best practices for cost-efficient cloud resource usage.
Work closely with product teams, analysts, and business stakeholders to translate requirements into scalable data engineering solutions.
Stay updated on the latest trends in cloud data engineering, lakehouse architectures, data observability, and AI-driven automation.
Employment Type: W2 · Full-time · All immigration statuses accepted (No restrictions)
            """
        },
        {
            "job_posting_id": "linkedin-002",
            "job_title": "Senior Python Data Engineer - GIS/Mapping",
            "company_name": "IntagHire",
            "job_location": "Houston, TX (100% onsite)",
            "job_description_text": """
Our client is looking for a candidate that can take ownership of a Data Engineering platform built for the GIS/Mapping Customers. The Platform is built with FastAPI, leaning heavily on Pydantic, and accessing data from PostgreSQL & ElasticSearch. The data engineer should be very familiar with async programming and creating functional tests to ensure that the applications continue to operate in its expected manner.

The platform serves 1000 users a month across several different product lines. On the security front, it manages user-to-group membership, access control based, resource and privilege definition. On the GIS front, it stores and serves up the configuration used for user maps. On the search front, it ties in user security with the request to search against the geospatial datasets presented in the map.

Must Have Skills:
- Python
- Async Programming
- SQL (creating optimized queries and creating data models in the database)
- Git

Good Skills to Have:
- Python packages: Psycopg3, Pydantic
- Docker
- PostgreSQL (PostGIS)
- ElasticSearch
- Redis
- Monitoring Platforms (DataDog, LogStash-Kibana)
- GIS Concepts

Job Type: Full-time
Location: Houston, TX, 100% onsite
We are unable to consider visa sponsorship or C2C
            """
        },
    ]

    try:
        region = os.getenv("AWS_REGION", "us-east-1")
        model = os.getenv("BEDROCK_MODEL_PASS1", "openai.gpt-oss-120b-1:0")

        print(f"Using model: {model}")
        print(f"Region: {region}")
        if use_cache:
            print(f"Cache: ENABLED (data/local/{{job_id}}/pass1-*.json)")
        print(f"Processing {len(linkedin_jobs)} real LinkedIn jobs...\n")

        # Create client once
        client = BedrockClient(
            model_ids={"pass1": model, "pass2": model, "pass3": model},
            region=region,
        )

        # Process all jobs
        results = []
        saved_files = []
        cache_hits = 0
        cache_misses = 0

        for i, job in enumerate(linkedin_jobs, 1):
            print(f"[{i}/{len(linkedin_jobs)}] Processing: {job['job_title']} @ {job['company_name']}...", end=" ")

            # Try to load from cache if enabled
            if use_cache:
                cached_result = load_from_cache(job, model, "pass1")
                if cached_result and cached_result.get('pass1_success'):
                    print("✓ (from cache)")
                    results.append(cached_result)
                    cache_hits += 1
                    continue
                else:
                    cache_misses += 1

            try:
                result = enrich_single_job(job, bedrock_client=client)
                success = result.get('pass1_success', False)
                status = "✓" if success else "✗"
                print(f"{status}")
                results.append(result)

                # Save result to ./{job_id}/pass1-{model}.json (also serves as cache)
                if (save_json or use_cache) and success:
                    filepath = save_pass_result(job, "pass1", model, result)
                    if filepath and save_json:
                        saved_files.append(filepath)
            except Exception as e:
                print(f"✗ ERROR: {e}")
                results.append({"pass1_success": False, "enrichment_errors": str(e)})

        # Print cache statistics if cache was used
        if use_cache:
            print(f"\nCache Statistics:")
            print(f"  Cache Hits: {cache_hits}")
            print(f"  Cache Misses: {cache_misses}")
            total = cache_hits + cache_misses
            print(f"  Cache Hit Rate: {cache_hits/total*100:.1f}%" if total > 0 else "  Cache Hit Rate: N/A")

        print("\n" + "=" * 120)
        print("RESULTS COMPARISON TABLE")
        print("=" * 120)

        # Print comparison table
        print_comparison_table(linkedin_jobs, results)

        # Print summary statistics
        print("\n" + "=" * 120)
        print("SUMMARY STATISTICS")
        print("=" * 120)

        # Data source information
        print(f"\nData Source: {'S3 Silver Bucket' if use_s3 else 'Local Mocks'}")
        if use_s3 and partition_info:
            print(f"Partition: {partition_info['year']}-{partition_info['month']}-{partition_info['day']} Hour {partition_info['hour']}")
            print(f"Jobs Loaded: {len(linkedin_jobs)}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        successful = sum(1 for r in results if r.get('pass1_success'))
        total_cost = sum(r.get('enrichment_cost_usd') or 0 for r in results)
        avg_cost = total_cost / len(results) if results else 0

        # Calculate token statistics
        total_input_tokens = sum(r.get('enrichment_input_tokens') or 0 for r in results)
        total_output_tokens = sum(r.get('enrichment_output_tokens') or 0 for r in results)
        total_tokens = total_input_tokens + total_output_tokens

        print(f"\nSuccess Rate: {successful}/{len(results)} ({successful/len(results)*100:.1f}%)")

        print(f"\nToken Statistics:")
        print(f"  Input Tokens:  {total_input_tokens:,}")
        print(f"  Output Tokens: {total_output_tokens:,}")
        print(f"  Total Tokens:  {total_tokens:,}")

        print(f"\nCost Analysis:")
        print(f"  Total Cost: ${total_cost:.6f}")
        print(f"  Average Cost per Job: ${avg_cost:.6f}")

        # Print saved files
        if save_json and saved_files:
            print(f"\nSaved Files:")
            for f in saved_files:
                print(f"  ✓ {f}")

        return successful == len(results)

    except Exception as e:
        print(f"\n✗ Multiple jobs test FAILED: {e}")
        traceback.print_exc()
        return False


def test_pass2_inference(use_s3: bool = False, date: Optional[str] = None, limit: int = 5, use_cache: bool = False, save_json: bool = False):
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
                    pass2_result_raw, pass2_tokens, pass2_input_tokens, pass2_output_tokens, pass2_cost = _execute_pass2(
                        client, job, pass1_result
                    )
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
                pass2_result_raw, pass2_tokens, pass2_input_tokens, pass2_output_tokens, pass2_cost = _execute_pass2(
                    client, job, pass1_result
                )
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
                _display_pass2_results(pass2_result_raw)

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


def test_pass3_analysis(use_s3: bool = False, date: Optional[str] = None, limit: int = 5, use_cache: bool = False, save_json: bool = False):
    """Test Pass 3 complex analysis using Pass 1 + Pass 2 results (use cache to skip previous passes if available)."""
    print("\n" + "=" * 120)
    print("Testing Pass 3 Complex Analysis")
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

            job_result = {"job": job}
            pass1_from_cache = False
            pass2_from_cache = False
            pass3_from_cache = False

            # === PASS 1: Extraction ===
            print(f"\n→ Pass 1 (Extraction)...", end=" ")

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
                    pass2_result_raw, pass2_tokens, pass2_input_tokens, pass2_output_tokens, pass2_cost = _execute_pass2(
                        client, job, pass1_result
                    )
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
                pass2_result_raw, pass2_tokens, pass2_input_tokens, pass2_output_tokens, pass2_cost = _execute_pass2(
                    client, job, pass1_result
                )
                print("✓" if pass2_result_raw else "✗")

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

            if use_cache:
                cached_pass3 = load_from_cache(job, model_pass3, "pass3")
                if cached_pass3:
                    pass3_analysis_raw = cached_pass3.get('analysis', {})
                    pass3_summary_raw = cached_pass3.get('summary', {})
                    pass3_tokens = cached_pass3.get('tokens', 0)
                    pass3_input_tokens = cached_pass3.get('input_tokens', 0)
                    pass3_output_tokens = cached_pass3.get('output_tokens', 0)
                    pass3_cost = cached_pass3.get('cost', 0.0)
                    print("✓ (from cache)")
                    pass3_from_cache = True
                    pass3_cache_hits += 1
                else:
                    pass3_cache_misses += 1
                    pass3_analysis_raw, pass3_summary_raw, pass3_tokens, pass3_input_tokens, pass3_output_tokens, pass3_cost = _execute_pass3(
                        client, job, pass1_result, pass2_result_raw
                    )
                    print("✓" if pass3_analysis_raw else "✗")
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
            else:
                pass3_analysis_raw, pass3_summary_raw, pass3_tokens, pass3_input_tokens, pass3_output_tokens, pass3_cost = _execute_pass3(
                    client, job, pass1_result, pass2_result_raw
                )
                print("✓" if pass3_analysis_raw else "✗")

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
                _display_pass3_results(pass3_analysis_raw, pass3_summary_raw)

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


# ============================================================================
# Helper Functions for Pass 2 and Pass 3
# ============================================================================

def _execute_pass2(client: BedrockClient, job: Dict[str, Any], pass1_result: Dict[str, Any]) -> tuple:
    """Execute Pass 2 inference and return results."""
    try:
        # Extract Pass 1 results
        pass1_extraction = {k: v for k, v in pass1_result.items() if k.startswith('ext_')}

        # Build Pass 2 prompt
        system_prompt, user_prompt = build_pass2_prompt(
            job_title=job.get('job_title', 'Unknown'),
            company_name=job.get('company_name', 'Unknown'),
            job_location=job.get('job_location', 'Unknown'),
            job_description_text=job.get('job_description_text', ''),
            pass1_extraction=pass1_extraction
        )

        # Call Bedrock
        raw_response, input_tokens, output_tokens, cost = client.invoke(
            prompt=user_prompt,
            system=system_prompt,
            pass_name="pass2",
            max_tokens=4096,
            temperature=0.1
        )
        total_tokens = input_tokens + output_tokens

        # Parse and validate response
        parsed, parse_error = parse_llm_json(raw_response)
        if not parsed:
            print(f"\n  Error parsing Pass 2 response: {parse_error}")
            return None, 0, 0, 0, 0.0

        # Validate Pass 2 structure
        is_valid, validation_errors = validate_inference_response(parsed)
        if not is_valid:
            print(f"\n  Warning: Validation errors in Pass 2 response: {validation_errors}")

        # Extract inference section
        inference_result = parsed.get('inference', {})

        return inference_result, total_tokens, input_tokens, output_tokens, cost

    except Exception as e:
        print(f"\n  Error in Pass 2: {e}")
        traceback.print_exc()
        return None, 0, 0, 0, 0.0


def _execute_pass3(client: BedrockClient, job: Dict[str, Any], pass1_result: Dict[str, Any], pass2_result: Dict[str, Any]) -> tuple:
    """Execute Pass 3 analysis and return results."""
    try:
        # Extract Pass 1 results
        pass1_extraction = {k: v for k, v in pass1_result.items() if k.startswith('ext_')}

        # Build Pass 3 prompt
        system_prompt, user_prompt = build_pass3_prompt(
            job_title=job.get('job_title', 'Unknown'),
            company_name=job.get('company_name', 'Unknown'),
            job_location=job.get('job_location', 'Unknown'),
            job_description_text=job.get('job_description_text', ''),
            pass1_extraction=pass1_extraction,
            pass2_inference=pass2_result
        )

        # Call Bedrock
        raw_response, input_tokens, output_tokens, cost = client.invoke(
            prompt=user_prompt,
            system=system_prompt,
            pass_name="pass3",
            max_tokens=4096,
            temperature=0.1
        )
        total_tokens = input_tokens + output_tokens

        # Parse and validate response
        parsed, parse_error = parse_llm_json(raw_response)
        if not parsed:
            print(f"\n  Error parsing Pass 3 response: {parse_error}")
            return None, None, 0, 0, 0, 0.0

        # Validate Pass 3 structure
        is_valid, validation_errors = validate_analysis_response(parsed)
        if not is_valid:
            print(f"\n  Warning: Validation errors in Pass 3 response: {validation_errors}")

        # Extract analysis and summary
        analysis_raw = parsed.get('analysis', {})
        summary_raw = parsed.get('summary', {})

        return analysis_raw, summary_raw, total_tokens, input_tokens, output_tokens, cost

    except Exception as e:
        print(f"\n  Error in Pass 3: {e}")
        traceback.print_exc()
        return None, None, 0, 0, 0, 0.0


def _display_pass2_results(pass2_result: Dict[str, Any]):
    """Display Pass 2 inference results in formatted view."""
    print(f"\n### PASS 2 INFERENCE ###\n")
    print(json.dumps(pass2_result, indent=2))


def _display_pass3_results(analysis: Dict[str, Any], summary: Dict[str, Any]):
    """Display Pass 3 analysis and summary in formatted view."""
    print(f"\n### PASS 3 ANALYSIS ###\n")

    # Display Analysis
    print("=== ANALYSIS ===\n")
    print(json.dumps(analysis, indent=2))

    # Display Summary
    print(f"\n{'=' * 120}")
    print("=== EXECUTIVE SUMMARY ===")
    print(f"{'=' * 120}\n")

    if summary.get('strengths'):
        print("✓ Strengths:")
        for strength in summary['strengths']:
            print(f"  • {strength}")
        print()

    if summary.get('concerns'):
        print("⚠ Concerns:")
        for concern in summary['concerns']:
            print(f"  • {concern}")
        print()

    if summary.get('best_fit_for'):
        print("👤 Best Fit For:")
        for fit in summary['best_fit_for']:
            print(f"  • {fit}")
        print()

    if summary.get('red_flags_to_probe'):
        print("🚩 Red Flags to Probe:")
        for flag in summary['red_flags_to_probe']:
            print(f"  • {flag}")
        print()

    if summary.get('negotiation_leverage'):
        print("💼 Negotiation Leverage:")
        for leverage in summary['negotiation_leverage']:
            print(f"  • {leverage}")
        print()

    if summary.get('overall_assessment'):
        print("📋 Overall Assessment:")
        print(f"  {summary['overall_assessment']}\n")

    if summary.get('recommendation_score') is not None:
        rec_score = summary.get('recommendation_score', 0.0)
        rec_conf = summary.get('recommendation_confidence', 0.0)
        # Handle dict case (nested value key)
        if isinstance(rec_score, dict):
            rec_score = rec_score.get('value', rec_score.get('score', 0.0))
        if isinstance(rec_conf, dict):
            rec_conf = rec_conf.get('value', rec_conf.get('confidence', 0.0))
        # Ensure numeric values
        try:
            rec_score = float(rec_score) if rec_score is not None else 0.0
            rec_conf = float(rec_conf) if rec_conf is not None else 0.0
            print(f"⭐ Recommendation Score: {rec_score:.2f} (confidence: {rec_conf:.2f})")
        except (TypeError, ValueError):
            print(f"⭐ Recommendation Score: {rec_score} (confidence: {rec_conf})")


# ============================================================================
# Multiple Models Comparison
# ============================================================================

def test_multiple_models(
    use_s3: bool = False,
    date: Optional[str] = None,
    limit: int = 5,
    save_json: bool = True,
    models: Optional[List[str]] = None,
    pass_type: str = "pass1",
    use_cache: bool = False
):
    """
    Test extraction/inference across multiple models and compare results.
    Reuses existing test functions by temporarily overriding env vars.

    Args:
        use_s3: Use jobs from S3 bucket
        date: Partition date (YYYY-MM-DD)
        limit: Number of jobs to process
        save_json: Save results to data/local/{job_id}/{pass}-{model}.json
        models: List of model keys to test (default: all available)
        pass_type: Which pass to test (pass1, pass2, pass3)
        use_cache: Enable caching of results
    """
    print("\n" + "=" * 120)
    print(f"Testing Multiple Models - {pass_type.upper()}")
    print("=" * 120)

    # Determine which models to test
    if models:
        test_models = {k: v for k, v in AVAILABLE_MODELS.items() if k in models}
        invalid = [m for m in models if m not in AVAILABLE_MODELS]
        if invalid:
            print(f"Warning: Unknown models ignored: {invalid}")
    else:
        test_models = AVAILABLE_MODELS

    if not test_models:
        print("Error: No valid models to test")
        print(f"Available models: {list(AVAILABLE_MODELS.keys())}")
        return False

    print(f"\nModels to test ({len(test_models)}):")
    for key, model in test_models.items():
        print(f"  • {key}: {model['name']} ({model['id']})")
        print(f"    Cost: ${model['input_cost_per_1m']}/1M input, ${model['output_cost_per_1m']}/1M output")

    # Save original env vars
    original_pass1 = os.getenv("BEDROCK_MODEL_PASS1")
    original_pass2 = os.getenv("BEDROCK_MODEL_PASS2")
    original_pass3 = os.getenv("BEDROCK_MODEL_PASS3")

    model_results = {}

    try:
        # Run test for each model
        for model_key, model_config in test_models.items():
            model_id = model_config['id']
            model_name = model_config['name']

            print(f"\n{'=' * 120}")
            print(f"MODEL: {model_name} ({model_id})")
            print(f"{'=' * 120}")

            # Override env vars for this model
            os.environ["BEDROCK_MODEL_PASS1"] = model_id
            os.environ["BEDROCK_MODEL_PASS2"] = model_id
            os.environ["BEDROCK_MODEL_PASS3"] = model_id

            # Call existing test function based on pass_type
            try:
                if pass_type == "pass1":
                    success = test_multiple_jobs_comparison(
                        use_s3=use_s3,
                        date=date,
                        limit=limit,
                        use_cache=use_cache,
                        save_json=save_json
                    )
                elif pass_type == "pass2":
                    success = test_pass2_inference(
                        use_s3=use_s3,
                        date=date,
                        limit=limit,
                        use_cache=use_cache,
                        save_json=save_json
                    )
                elif pass_type == "pass3":
                    success = test_pass3_analysis(
                        use_s3=use_s3,
                        date=date,
                        limit=limit,
                        use_cache=use_cache,
                        save_json=save_json
                    )
                else:
                    print(f"Unknown pass type: {pass_type}")
                    success = False

                model_results[model_key] = {
                    "name": model_name,
                    "model_id": model_id,
                    "success": success,
                    "input_cost_per_1m": model_config['input_cost_per_1m'],
                    "output_cost_per_1m": model_config['output_cost_per_1m'],
                }

            except Exception as e:
                print(f"ERROR testing {model_name}: {e}")
                traceback.print_exc()
                model_results[model_key] = {
                    "name": model_name,
                    "model_id": model_id,
                    "success": False,
                    "error": str(e),
                }

    finally:
        # Restore original env vars
        if original_pass1:
            os.environ["BEDROCK_MODEL_PASS1"] = original_pass1
        elif "BEDROCK_MODEL_PASS1" in os.environ:
            del os.environ["BEDROCK_MODEL_PASS1"]

        if original_pass2:
            os.environ["BEDROCK_MODEL_PASS2"] = original_pass2
        elif "BEDROCK_MODEL_PASS2" in os.environ:
            del os.environ["BEDROCK_MODEL_PASS2"]

        if original_pass3:
            os.environ["BEDROCK_MODEL_PASS3"] = original_pass3
        elif "BEDROCK_MODEL_PASS3" in os.environ:
            del os.environ["BEDROCK_MODEL_PASS3"]

    # Print summary
    print(f"\n{'=' * 120}")
    print("MULTIPLE MODELS - FINAL SUMMARY")
    print(f"{'=' * 120}")

    print(f"\n{'Model':<30} | {'Status':<10} | {'Input $/1M':<12} | {'Output $/1M':<12}")
    print("-" * 70)

    for model_key, result in model_results.items():
        status = "✓ OK" if result.get('success') else "✗ FAIL"
        if 'error' in result:
            status = "✗ ERROR"
        input_cost = f"${result.get('input_cost_per_1m', 0):.2f}"
        output_cost = f"${result.get('output_cost_per_1m', 0):.2f}"
        print(f"{result['name'][:29]:<30} | {status:<10} | {input_cost:<12} | {output_cost:<12}")

    print(f"\nResults saved to: data/local/{{job_id}}/{pass_type}-{{model}}.json")
    print("Compare results by inspecting the JSON files for each model.")

    return all(r.get('success', False) for r in model_results.values())
