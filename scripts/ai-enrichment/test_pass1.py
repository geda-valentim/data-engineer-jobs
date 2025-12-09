"""
Pass 1 Extraction tests.
Contains functions for testing Pass 1 extraction with multiple jobs and comparison.
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
    load_jobs_from_s3,
    save_pass_result,
    save_raw_response,
    print_comparison_table,
    save_job_original,
)


def test_multiple_jobs_comparison(
    use_s3: bool = False,
    date: Optional[str] = None,
    limit: int = 5,
    use_cache: bool = False,
    save_json: bool = False,
    preloaded_jobs: Optional[List[Dict[str, Any]]] = None,
    preloaded_partition_info: Optional[Dict[str, Any]] = None
):
    """Test Pass 1 extraction with multiple real LinkedIn jobs and compare results.

    Args:
        preloaded_jobs: Optional pre-loaded jobs to avoid repeated S3 calls (for multiple model testing)
        preloaded_partition_info: Optional partition info from pre-loaded jobs
    """
    print("\n" + "=" * 60)
    print("Testing Pass 1 Extraction - Multiple Jobs Comparison")
    print("=" * 60)

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
            # Save original job data from S3 (only if from S3, not mocks)
            if use_s3 or preloaded_jobs is not None:
                save_job_original(job)

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

                # Save raw response for debugging
                pass1_raw = result.pop('pass1_raw_response', None)
                if pass1_raw:
                    save_raw_response(job, "pass1", model, pass1_raw)

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
