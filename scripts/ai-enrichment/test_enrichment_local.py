#!/usr/bin/env python3
"""
Local test script for AI Enrichment pipeline.
Tests Bedrock connectivity and S3 access.

Usage:
    python scripts/test_enrichment_local.py
    python scripts/test_enrichment_local.py --bedrock-only
    python scripts/test_enrichment_local.py --s3-only
    python scripts/test_enrichment_local.py --compare --s3-source --cache
    python scripts/test_enrichment_local.py --pass2 --cache --save-json
    python scripts/test_enrichment_local.py --pass3 --s3-source --date=2025-12-05 --limit=5 --cache --save-json
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Add src to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "lambdas" / "ai_enrichment"))

# Import Bedrock and enrichment modules
from enrich_partition.bedrock_client import BedrockClient
from enrich_partition.handler import enrich_single_job
from dotenv import load_dotenv
import boto3

# Import test functions from separated modules
from test_enrichment_passes import (
    test_multiple_jobs_comparison,
    test_pass2_inference,
    test_pass3_analysis,
)

load_dotenv()


def test_bedrock_connectivity():
    """Test that we can connect to Bedrock and invoke a model."""
    print("=" * 60)
    print("Testing Bedrock connectivity...")
    print("=" * 60)

    region = os.getenv("AWS_REGION", "us-east-1")
    model_id = os.getenv("BEDROCK_MODEL_PASS1", "openai.gpt-oss-120b-1:0")

    print(f"Region: {region}")
    print(f"Model: {model_id}")

    try:
        client = boto3.client("bedrock-runtime", region_name=region)

        # Build request based on model type
        if model_id.startswith("openai.gpt-oss-120b-1:0"):
            # OpenAI-compatible format (works for openai.gpt-oss-120b-1:0)
            body = {
                "max_tokens": 100,
                "temperature": 0.1,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say 'Bedrock connection successful!' and nothing else."}
                ]
            }
        elif model_id.startswith("anthropic.claude"):
            # Claude format
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 100,
                "messages": [
                    {
                        "role": "user",
                        "content": "Say 'Bedrock connection successful!' and nothing else."
                    }
                ]
            }
        else:
            # Generic format
            body = {
                "prompt": "Say 'Bedrock connection successful!' and nothing else.",
                "max_tokens": 100
            }

        print(f"\nSending test request to {model_id}...")
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json"
        )

        response_body = json.loads(response["body"].read())

        # Extract output based on model type
        if model_id.startswith("openai.gpt-oss-120b-1:0"):
            # OpenAI-compatible format (works for openai.gpt-oss-120b-1:0)
            output_text = response_body.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = response_body.get("usage", {})
            input_tokens = usage.get("prompt_tokens", "N/A")
            output_tokens = usage.get("completion_tokens", "N/A")
        elif "content" in response_body:
            # Claude format
            output_text = response_body["content"][0]["text"]
            usage = response_body.get("usage", {})
            input_tokens = usage.get("input_tokens", "N/A")
            output_tokens = usage.get("output_tokens", "N/A")
        else:
            output_text = str(response_body)
            input_tokens = "N/A"
            output_tokens = "N/A"

        print(f"\nResponse: {output_text}")
        print(f"Input tokens: {input_tokens}")
        print(f"Output tokens: {output_tokens}")
        print("\n✓ Bedrock connectivity test PASSED")
        return True

    except Exception as e:
        print(f"\n✗ Bedrock connectivity test FAILED: {e}")
        return False


def test_s3_silver_access():
    """Test that we can read from Silver bucket."""
    print("\n" + "=" * 60)
    print("Testing S3 Silver access...")
    print("=" * 60)

    bucket = os.getenv("SILVER_BUCKET")
    if not bucket:
        print("✗ SILVER_BUCKET environment variable not set")
        print("  Set it in .env file: SILVER_BUCKET=data-engineer-jobs-silver-dev")
        return False

    print(f"Bucket: {bucket}")

    try:
        import awswrangler as wr

        # List partitions
        base_path = f"s3://{bucket}/linkedin/"
        print(f"Listing: {base_path}")

        dirs = wr.s3.list_directories(path=base_path)
        print(f"Found {len(dirs)} year partitions")

        if dirs:
            print(f"Sample: {dirs[0]}")

            # Try to find a partition with data
            for year_dir in dirs[:2]:  # Check first 2 years
                try:
                    month_dirs = wr.s3.list_directories(path=year_dir)
                    if month_dirs:
                        day_dirs = wr.s3.list_directories(path=month_dirs[0])
                        if day_dirs:
                            hour_dirs = wr.s3.list_directories(path=day_dirs[0])
                            if hour_dirs:
                                # Try to read first partition
                                print(f"\nReading sample partition: {hour_dirs[0]}")
                                df = wr.s3.read_parquet(path=hour_dirs[0])
                                print(f"✓ Read {len(df)} records")
                                print(f"Columns: {list(df.columns)[:5]}...")
                                break
                except Exception as e:
                    print(f"  Could not read partition: {e}")

        print("\n✓ S3 Silver access test PASSED")
        return True

    except Exception as e:
        print(f"\n✗ S3 Silver access test FAILED: {e}")
        return False


def test_list_partitions():
    """Test partition listing functionality."""
    print("\n" + "=" * 60)
    print("Testing partition listing...")
    print("=" * 60)

    bucket = os.getenv("SILVER_BUCKET")
    if not bucket:
        print("✗ SILVER_BUCKET not set")
        return False

    try:
        from shared.s3_utils import list_silver_partitions, list_silver_ai_partitions

        print("Listing Silver partitions...")
        silver = list_silver_partitions()
        print(f"Found {len(silver)} Silver partitions")

        print("\nListing Silver-AI partitions...")
        silver_ai = list_silver_ai_partitions()
        print(f"Found {len(silver_ai)} Silver-AI partitions")

        if silver:
            print(f"\nSample Silver partition: {silver[0]}")

        # Calculate pending
        silver_keys = {f"{p['year']}/{p['month']}/{p['day']}/{p['hour']}" for p in silver}
        silver_ai_keys = {f"{p['year']}/{p['month']}/{p['day']}/{p['hour']}" for p in silver_ai}
        pending = silver_keys - silver_ai_keys

        print(f"\nPending partitions: {len(pending)}")

        print("\n✓ Partition listing test PASSED")
        return True

    except Exception as e:
        print(f"\n✗ Partition listing test FAILED: {e}")
        return False


def test_pass1_extraction():
    """Test Pass 1 extraction with a sample job."""
    print("\n" + "=" * 60)
    print("Testing Pass 1 Extraction...")
    print("=" * 60)

    # Sample job for testing
    sample_job = {
        "job_posting_id": "test-001",
        "job_title": "Senior Data Engineer",
        "company_name": "TechCorp",
        "job_location": "San Francisco, CA (Remote)",
        "job_description_text": """
About the Role:
We are looking for a Senior Data Engineer to join our growing data platform team.

Requirements:
- 5+ years of experience in data engineering
- Strong proficiency in Python and SQL
- Experience with AWS (S3, Redshift, Glue, Lambda)
- Experience with Apache Spark and Airflow
- Bachelor's degree in Computer Science or related field

Nice to Have:
- Experience with dbt
- Kafka streaming experience
- AWS certifications

Compensation:
- Salary: $180,000 - $220,000 per year
- Equity package included
- Comprehensive health benefits
- 401k matching

Work Model:
This is a fully remote position. Candidates must be authorized to work in the US.
We do not sponsor visas at this time.
        """,
    }

    try:
        region = os.getenv("AWS_REGION", "us-east-1")
        model = os.getenv("BEDROCK_MODEL_PASS1", "openai.gpt-oss-120b-1:0")

        print(f"Using model: {model}")
        print(f"Region: {region}")
        print(f"\nProcessing job: {sample_job['job_title']} at {sample_job['company_name']}")

        # Create client
        client = BedrockClient(
            model_ids={"pass1": model, "pass2": model, "pass3": model},
            region=region,
        )

        # Run enrichment
        result = enrich_single_job(sample_job, bedrock_client=client)

        # Check results
        print("\n--- Results ---")
        print(f"Pass 1 Success: {result.get('pass1_success')}")
        print(f"Tokens Used: {result.get('total_tokens_used')}")
        cost = result.get('enrichment_cost_usd') or 0
        print(f"Cost: ${cost:.6f}")

        if result.get("enrichment_errors"):
            print(f"Errors: {result.get('enrichment_errors')}")

        # Show extracted fields
        print("\n--- Extracted Fields ---")
        ext_fields = [k for k in result.keys() if k.startswith("ext_")]
        for field in ext_fields:
            value = result.get(field)
            if value is not None:
                print(f"  {field}: {value}")

        if result.get("pass1_success"):
            print("\n✓ Pass 1 extraction test PASSED")
            return True
        else:
            print("\n✗ Pass 1 extraction test FAILED")
            return False

    except Exception as e:
        print(f"\n✗ Pass 1 extraction test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Test AI Enrichment pipeline locally",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="For complete documentation with examples, run: python scripts/ai-enrichment/test_enrichment_help.py"
    )
    parser.add_argument("--help-full", action="store_true", help="Show complete help with examples and use cases")
    parser.add_argument("--bedrock-only", action="store_true", help="Only test Bedrock connectivity")
    parser.add_argument("--s3-only", action="store_true", help="Only test S3 access")
    parser.add_argument("--pass1", action="store_true", help="Test Pass 1 extraction with sample job")
    parser.add_argument("--pass2", action="store_true", help="Test Pass 2 inference using Pass 1 results (use --cache to load Pass 1 from cache)")
    parser.add_argument("--pass3", action="store_true", help="Test Pass 3 complex analysis using Pass 1 + Pass 2 results (use --cache to load from cache)")
    parser.add_argument("--compare", action="store_true", help="Test Pass 1 with multiple real LinkedIn jobs and compare")
    parser.add_argument("--s3-source", action="store_true", help="Use real jobs from S3 bucket instead of mocks (requires --compare, --pass2, or --pass3)")
    parser.add_argument("--date", type=str, help="Partition date in YYYY-MM-DD format (uses latest hour of that day). Defaults to most recent partition if not specified. Requires --s3-source.")
    parser.add_argument("--limit", type=int, default=5, help="Number of jobs to process (default: 5). Used with --s3-source.")
    parser.add_argument("--cache", action="store_true", help="Enable caching of Pass 1, Pass 2, and Pass 3 results (saves cost during testing)")
    parser.add_argument("--save-json", action="store_true", help="Save complete results to JSON file in data/local/ folder")
    args = parser.parse_args()

    # Show full help if requested
    if args.help_full:
        try:
            from test_enrichment_help import show_help
            show_help()
        except ImportError:
            print("Error: test_enrichment_help.py not found")
            print("Run: python scripts/ai-enrichment/test_enrichment_help.py")
        return 0

    print("\n" + "=" * 60)
    print("AI Enrichment Pipeline - Local Test")
    print("=" * 60)

    results = []

    # If --compare is specified, run multi-job comparison
    if args.compare:
        results.append(("Multi-Job Comparison", test_multiple_jobs_comparison(
            use_s3=args.s3_source,
            date=args.date,
            limit=args.limit,
            use_cache=args.cache
        )))
    # If --pass2 is specified, test Pass 2 inference
    elif args.pass2:
        results.append(("Pass 2 Inference", test_pass2_inference(
            use_s3=args.s3_source,
            date=args.date,
            limit=args.limit,
            use_cache=args.cache,
            save_json=args.save_json
        )))
    # If --pass3 is specified, test Pass 3 complex analysis
    elif args.pass3:
        results.append(("Pass 3 Complex Analysis", test_pass3_analysis(
            use_s3=args.s3_source,
            date=args.date,
            limit=args.limit,
            use_cache=args.cache,
            save_json=args.save_json
        )))
    # If --pass1 is specified, only run that test
    elif args.pass1:
        results.append(("Pass 1 Extraction", test_pass1_extraction()))
    else:
        if not args.s3_only:
            results.append(("Bedrock connectivity", test_bedrock_connectivity()))

        if not args.bedrock_only:
            results.append(("S3 Silver access", test_s3_silver_access()))
            results.append(("Partition listing", test_list_partitions()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\nAll tests passed!")
    else:
        print("\nSome tests failed. Check configuration and try again.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
