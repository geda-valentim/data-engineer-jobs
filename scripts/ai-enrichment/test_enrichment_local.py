#!/usr/bin/env python3
"""
Local test script for AI Enrichment pipeline.
Tests Bedrock connectivity and S3 access.

Usage:
    python scripts/test_enrichment_local.py
    python scripts/test_enrichment_local.py --bedrock-only
    python scripts/test_enrichment_local.py --s3-only
"""

import os
import sys
import json
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

# Add src to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "lambdas" / "ai_enrichment"))

from dotenv import load_dotenv
import boto3

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
        from enrich_partition.handler import enrich_single_job
        from enrich_partition.bedrock_client import BedrockClient

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


def _get_cache_dir() -> Path:
    """Get cache directory path, creating it if needed."""
    cache_dir = Path(__file__).parent.parent.parent / ".cache" / "enrichment"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _get_cache_key(job: Dict[str, Any]) -> str:
    """Generate cache key from job posting ID."""
    job_id = job.get('job_posting_id', '')
    if not job_id:
        # If no ID, hash the job content
        content = json.dumps(job, sort_keys=True)
        job_id = hashlib.md5(content.encode()).hexdigest()
    # Clean job_id to be filesystem-safe
    return job_id.replace('/', '_').replace('\\', '_')


def _load_from_cache(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Load enrichment result from cache if available.

    Args:
        job: Job dictionary

    Returns:
        Cached result or None if not found
    """
    cache_key = _get_cache_key(job)
    cache_file = _get_cache_dir() / f"{cache_key}.json"

    if cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
                return cached
        except Exception as e:
            print(f"Warning: Could not load cache for {cache_key}: {e}")
            return None
    return None


def _save_to_cache(job: Dict[str, Any], result: Dict[str, Any], pass2_result: Optional[Dict[str, Any]] = None):
    """
    Save enrichment result to cache (Pass 1 and optionally Pass 2).

    Args:
        job: Job dictionary
        result: Pass 1 enrichment result
        pass2_result: Optional Pass 2 inference result dict with keys: pass2_result, pass2_success, pass2_tokens, pass2_cost
    """
    cache_key = _get_cache_key(job)
    cache_file = _get_cache_dir() / f"{cache_key}.json"

    try:
        # Load existing cache if present (to preserve Pass 2 if only updating Pass 1)
        existing_cache = {}
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    existing_cache = json.load(f)
            except:
                pass

        # Merge Pass 1 result
        cache_data = {**existing_cache, **result}

        # Add Pass 2 result if provided
        if pass2_result:
            cache_data.update(pass2_result)

        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2, default=str)
    except Exception as e:
        print(f"Warning: Could not save cache for {cache_key}: {e}")


def load_jobs_from_s3(date_str: Optional[str] = None, limit: int = 5) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Load jobs from S3 silver bucket.

    Args:
        date_str: Optional date in YYYY-MM-DD format. If provided, gets latest hour of that day.
                  If None, uses most recent partition overall.
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

        # Get partition with highest hour value (latest hour of the day)
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

    # Return jobs and partition info for display
    partition_info = {
        'year': selected['year'],
        'month': selected['month'],
        'day': selected['day'],
        'hour': selected['hour']
    }

    return jobs, partition_info


def test_multiple_jobs_comparison(use_s3: bool = False, date: Optional[str] = None, limit: int = 5, use_cache: bool = False):
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
        {
            "job_posting_id": "linkedin-003",
            "job_title": "Senior Data Engineer",
            "company_name": "Eames Consulting",
            "job_location": "United States (Remote)",
            "job_description_text": """
Come join a venture-backed Insurtech startup utilizing advanced AI and automation to modernize the $300B+ insurance claims industry. We are searching for a Senior Data Engineer to help scale our platform!

We're looking for a Senior Data Engineer who's passionate about building reliable, scalable, and high-quality data systems. You'll partner closely with analytics, product, and engineering teams to deliver data solutions that drive real business and customer impact.

Preferred Qualifications:
- 6-8 years of industry experience in data engineering building scalable data pipelines and data products
- Strong proficiency in SQL and Python within AWS or Google Cloud Platform (GCP), and dbt
- Proven experience building and maintaining robust data pipelines and ETL workflows, with hands-on dbt experience for reliable, testable, and maintainable data transformations
- Hands-on experience ingesting data from diverse sources, including APIs, databases, SaaS applications, and event streams
- Strong foundation in data modeling, schema design, and data quality best practices, with functional experience working on cloud platforms like Snowflake, Redshift, BigQuery, or Databricks
- Experience implementing CI/CD pipelines, automated testing, and data observability to ensure reliability and trust in data systems
- Familiarity with monitoring, alerting, and incident response for production-grade data pipelines
- Proven ability to optimize performance and cost across data workflows and storage systems
- Functional understanding of how to leverage AI and automation in data engineering, building self-service tools, intelligent pipelines, and agents that automate repetitive tasks
- Strong communication and collaboration skills, with a focus on clarity, empathy, and shared ownership

Compensation/Benefits:
- Salary: $165,000 - $185,000 per year
- 100% REMOTE job with flexible work arrangements
- UNLIMITED paid time off with a required minimum
- High-quality tech setup (Mac laptop, monitor, etc)
- Comprehensive health, dental, vision coverage
- 401(K) plus an employer match
- Generous parental leave policy
- Commitment to DEI - Inclusion
            """
        },
        {
            "job_posting_id": "linkedin-004",
            "job_title": "Data Engineer III, ITA",
            "company_name": "Amazon",
            "job_location": "Seattle, WA",
            "job_description_text": """
Do you want a role with deep meaning and the ability to make a major impact? As part of Intelligent Talent Acquisition (ITA), you'll have the opportunity to reinvent the hiring process and deliver unprecedented scale, sophistication, and accuracy for Amazon Talent Acquisition operations.

Key job responsibilities:
- Architect and implement scalable, reliable data pipelines and infrastructure, supporting analytics at scale
- Design and enforce data modeling standards, lineage, and governance frameworks while ensuring secure, compliant solutions
- Lead technical design/code reviews, evaluate emerging technologies, and drive engineering best practices across development lifecycle
- Work closely with business owners, developers, BI Engineers and Data Scientists to deliver scalable solutions enabling teams to access and analyze data effectively
- Mentor junior engineers, foster technical excellence, and empower team self-service capabilities for handling complex data tasks independently

Basic Qualifications:
- 5+ years of data engineering experience
- Experience with data modeling, warehousing and building ETL pipelines
- Experience with SQL
- Experience in at least one modern scripting or programming language, such as Python, Java, Scala, or NodeJS
- Experience mentoring team members on best practices
- Experience building modern cloud based data platforms for AI/ML and analytics usecases

Preferred Qualifications:
- Experience with big data technologies such as: Hadoop, Hive, Spark, EMR
- Experience operating large data warehouses
- Knowledge of professional software engineering & best practices for full software development life cycle

Compensation: $139,100/year - $240,500/year based on location
Pay is based on a number of factors including market location and may vary depending on job-related knowledge, skills, and experience.
            """
        },
        {
            "job_posting_id": "linkedin-005",
            "job_title": "Member of Technical Staff - Data Engineer",
            "company_name": "Microsoft",
            "job_location": "New York, NY (Hybrid)",
            "job_description_text": """
As Microsoft continues to push the boundaries of AI, we are on the lookout for individuals to work with us on the most interesting and challenging AI questions of our time.

Microsoft AI (MS AI) is seeking an experienced Member of Technical Staff - Data Engineer - Microsoft AI - Copilot to help build mission critical data pipelines that ingest, process and publishes data streams from our personal AI, Copilot systems.

The Data Platform Engineering team is responsible for building core data pipelines that help fine tune models, support introspection and retrospection of data so that we can constantly evolve and improve human AI interactions.

Starting January 26, 2026, MAI employees are expected to work from a designated Microsoft office at least four days a week.

Responsibilities:
- Build scalable data pipelines for sourcing, transforming and publishing data assets for AI use cases
- Work collaboratively with other Platform, infrastructure, application engineers as well as AI Researchers to build next generation data platform products and services
- Ship high-quality, well-tested, secure, and maintainable code
- Find a path to get things done despite roadblocks to get your work into the hands of users quickly and iteratively

Required Qualifications:
- Bachelor's Degree in Computer Science, Math, Software Engineering, Computer Engineering, or related field AND 6+ years experience in business analytics, data science, software development, data modeling or data engineering work
- OR Master's Degree AND 4+ years experience
- OR equivalent experience

Preferred Qualifications:
- 4+ years technical engineering experience building data processing applications (batch and streaming) with coding in languages including Python, Java, Spark, SQL
- Experience working with Apache Hadoop eco system, Kafka, NoSQL, etc
- 3+ years experience with data governance, data compliance and/or data security
- 2+ years' experience building scalable services on top of public cloud infrastructure like Azure, AWS, or GCP
- 2+ years' experience building distributed systems at scale

Compensation: $139,900 - $304,200 per year (location dependent)
            """
        }
    ]

    try:



        region = os.getenv("AWS_REGION", "us-east-1")
        model = os.getenv("BEDROCK_MODEL_PASS1", "openai.gpt-oss-120b-1:0")

        print(f"Using model: {model}")
        print(f"Region: {region}")
        if use_cache:
            print(f"Cache: ENABLED (results will be saved/loaded from .cache/enrichment/)")
        print(f"Processing {len(linkedin_jobs)} real LinkedIn jobs...\n")

        # Create client once
        client = BedrockClient(
            model_ids={"pass1": model, "pass2": model, "pass3": model},
            region=region,
        )

        # Process all jobs
        results = []
        cache_hits = 0
        cache_misses = 0

        for i, job in enumerate(linkedin_jobs, 1):
            print(f"[{i}/{len(linkedin_jobs)}] Processing: {job['job_title']} @ {job['company_name']}...", end=" ")

            # Try to load from cache if enabled
            cached_result = None
            if use_cache:
                cached_result = _load_from_cache(job)
                if cached_result:
                    print(f"✓ (from cache)")
                    results.append(cached_result)
                    cache_hits += 1
                    continue
                else:
                    cache_misses += 1

            # Process with LLM if not cached
            try:
                result = enrich_single_job(job, bedrock_client=client)
                success = result.get('pass1_success', False)
                status = "✓" if success else "✗"
                print(f"{status}")
                results.append(result)

                # Save to cache if enabled and successful
                if use_cache and success:
                    _save_to_cache(job, result)
            except Exception as e:
                print(f"✗ ERROR: {e}")
                results.append({"pass1_success": False, "enrichment_errors": str(e)})

        # Print cache statistics if cache was used
        if use_cache:
            print(f"\nCache Statistics:")
            print(f"  Cache Hits: {cache_hits}")
            print(f"  Cache Misses: {cache_misses}")
            print(f"  Cache Hit Rate: {cache_hits/(cache_hits+cache_misses)*100:.1f}%" if (cache_hits+cache_misses) > 0 else "  Cache Hit Rate: N/A")

        print("\n" + "=" * 120)
        print("RESULTS COMPARISON TABLE")
        print("=" * 120)

        # Print comparison table
        _print_comparison_table(linkedin_jobs, results)

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

        return successful == len(results)

    except Exception as e:
        print(f"\n✗ Multiple jobs test FAILED: {e}")

        traceback.print_exc()
        return False


def _print_comparison_table(jobs, results):
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

    # Print detailed individual results for each job
    print("\n" + "=" * 120)
    print("INDIVIDUAL EXTRACTION RESULTS (ALL FIELDS)")
    print("=" * 120)

    for i, (job, result) in enumerate(zip(jobs, results), 1):
        print(f"\n{'=' * 120}")
        print(f"[{i}/5] {job['company_name']} - {job['job_title']}")
        print(f"{'=' * 120}")
        print(f"Location: {job['job_location']}")
        print(f"Pass 1 Success: {result.get('pass1_success', False)}")
        print(f"Tokens Used: {(result.get('enrichment_input_tokens') or 0) + (result.get('enrichment_output_tokens') or 0)}")
        print(f"Cost: ${(result.get('enrichment_cost_usd') or 0):.6f}")

        print("\n--- Extracted Fields ---")

        # Compensation
        if result.get('ext_salary_disclosed'):
            print(f"  ext_salary_disclosed: {result.get('ext_salary_disclosed')}")
        if result.get('ext_salary_min'):
            print(f"  ext_salary_min: {result.get('ext_salary_min')}")
        if result.get('ext_salary_max'):
            print(f"  ext_salary_max: {result.get('ext_salary_max')}")
        if result.get('ext_salary_currency'):
            print(f"  ext_salary_currency: {result.get('ext_salary_currency')}")
        if result.get('ext_salary_period'):
            print(f"  ext_salary_period: {result.get('ext_salary_period')}")
        if result.get('ext_salary_text_raw'):
            print(f"  ext_salary_text_raw: {result.get('ext_salary_text_raw')}")

        # Work Authorization
        if result.get('ext_visa_sponsorship_stated'):
            print(f"  ext_visa_sponsorship_stated: {result.get('ext_visa_sponsorship_stated')}")
        if result.get('ext_work_auth_text'):
            print(f"  ext_work_auth_text: {result.get('ext_work_auth_text')}")
        if result.get('ext_security_clearance_stated') and result.get('ext_security_clearance_stated') != 'not_mentioned':
            print(f"  ext_security_clearance_stated: {result.get('ext_security_clearance_stated')}")

        # Work Model
        if result.get('ext_work_model_stated'):
            print(f"  ext_work_model_stated: {result.get('ext_work_model_stated')}")
        if result.get('ext_employment_type_stated'):
            print(f"  ext_employment_type_stated: {result.get('ext_employment_type_stated')}")

        # Contract Details
        if result.get('ext_contract_type'):
            print(f"  ext_contract_type: {result.get('ext_contract_type')}")
        if result.get('ext_start_date') and result.get('ext_start_date') != 'not_mentioned':
            print(f"  ext_start_date: {result.get('ext_start_date')}")

        # Pay Type
        if result.get('ext_pay_type'):
            print(f"  ext_pay_type: {result.get('ext_pay_type')}")

        # Skills
        if result.get('ext_must_have_hard_skills'):
            print(f"  ext_must_have_hard_skills: {result.get('ext_must_have_hard_skills')}")
        if result.get('ext_nice_to_have_hard_skills'):
            print(f"  ext_nice_to_have_hard_skills: {result.get('ext_nice_to_have_hard_skills')}")
        if result.get('ext_must_have_soft_skills'):
            print(f"  ext_must_have_soft_skills: {result.get('ext_must_have_soft_skills')}")
        if result.get('ext_nice_to_have_soft_skills'):
            print(f"  ext_nice_to_have_soft_skills: {result.get('ext_nice_to_have_soft_skills')}")
        if result.get('ext_certifications_mentioned'):
            print(f"  ext_certifications_mentioned: {result.get('ext_certifications_mentioned')}")

        # Experience
        if result.get('ext_years_experience_min'):
            print(f"  ext_years_experience_min: {result.get('ext_years_experience_min')}")
        if result.get('ext_years_experience_max'):
            print(f"  ext_years_experience_max: {result.get('ext_years_experience_max')}")
        if result.get('ext_years_experience_text'):
            print(f"  ext_years_experience_text: {result.get('ext_years_experience_text')}")
        if result.get('ext_education_stated'):
            print(f"  ext_education_stated: {result.get('ext_education_stated')}")

        # AI/ML Detection
        if result.get('ext_llm_genai_mentioned') is not None:
            print(f"  ext_llm_genai_mentioned: {result.get('ext_llm_genai_mentioned')}")
        if result.get('ext_feature_store_mentioned') is not None:
            print(f"  ext_feature_store_mentioned: {result.get('ext_feature_store_mentioned')}")

        # Geographic Restrictions
        if result.get('ext_geo_restriction_type'):
            print(f"  ext_geo_restriction_type: {result.get('ext_geo_restriction_type')}")
        if result.get('ext_allowed_countries'):
            print(f"  ext_allowed_countries: {result.get('ext_allowed_countries')}")
        if result.get('ext_excluded_countries'):
            print(f"  ext_excluded_countries: {result.get('ext_excluded_countries')}")
        if result.get('ext_residency_requirement') and result.get('ext_residency_requirement') != 'not_mentioned':
            print(f"  ext_residency_requirement: {result.get('ext_residency_requirement')}")

        # Benefits
        if result.get('ext_benefits_mentioned'):
            print(f"  ext_benefits_mentioned: {result.get('ext_benefits_mentioned')}")
        if result.get('ext_equity_mentioned') is not None:
            print(f"  ext_equity_mentioned: {result.get('ext_equity_mentioned')}")
        if result.get('ext_pto_policy') and result.get('ext_pto_policy') != 'not_mentioned':
            print(f"  ext_pto_policy: {result.get('ext_pto_policy')}")

    # Print detailed skills breakdown
    print("\n" + "=" * 120)
    print("DETAILED SKILLS BREAKDOWN (SUMMARY)")
    print("=" * 120)

    for job, result in zip(jobs, results):
        print(f"\n{job['company_name']} - {job['job_title']}")
        print(f"Location: {job['job_location']}")

        must_hard = result.get('ext_must_have_hard_skills', [])
        nice_hard = result.get('ext_nice_to_have_hard_skills', [])
        must_soft = result.get('ext_must_have_soft_skills', [])
        nice_soft = result.get('ext_nice_to_have_soft_skills', [])

        if must_hard:
            print(f"  Must-Have Tech: {', '.join(must_hard)}")
        if nice_hard:
            print(f"  Nice-To-Have Tech: {', '.join(nice_hard)}")
        if must_soft:
            print(f"  Must-Have Soft: {', '.join(must_soft)}")
        if nice_soft:
            print(f"  Nice-To-Have Soft: {', '.join(nice_soft)}")


def test_pass2_inference(use_s3: bool = False, date: Optional[str] = None, limit: int = 5, use_cache: bool = False):
    """Test Pass 2 inference using Pass 1 results (from cache or fresh execution)."""
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
                "job_description_text": """Design, build, and maintain scalable data pipelines for ingestion, processing, transformation, and storage using modern ETL/ELT frameworks...""",
            },
            {
                "job_posting_id": "linkedin-002",
                "job_title": "Senior Python Data Engineer - GIS/Mapping",
                "company_name": "IntagHire",
                "job_location": "Houston, TX (100% onsite)",
                "job_description_text": """Our client is looking for a candidate that can take ownership of a Data Engineering platform...""",
            },
        ]

    try:

        from enrich_partition.prompts.pass2_inference import build_pass2_prompt
        from enrich_partition.parsers.json_parser import parse_llm_json
        from enrich_partition.parsers.validators import validate_inference_response


        region = os.getenv("AWS_REGION", "us-east-1")
        model_pass1 = os.getenv("BEDROCK_MODEL_PASS1", "openai.gpt-oss-120b-1:0")
        model_pass2 = os.getenv("BEDROCK_MODEL_PASS2", "openai.gpt-oss-120b-1:0")

        print(f"Using models:")
        print(f"  Pass 1: {model_pass1}")
        print(f"  Pass 2: {model_pass2}")
        print(f"Region: {region}")
        if use_cache:
            print(f"Cache: ENABLED (Pass 1 results will be loaded from cache if available)")
        print(f"\nProcessing {len(linkedin_jobs)} jobs...\n")

        # Create client
        client = BedrockClient(
            model_ids={"pass1": model_pass1, "pass2": model_pass2, "pass3": model_pass2},
            region=region,
        )

        results = []
        pass1_cache_hits = 0
        pass1_cache_misses = 0
        pass2_cache_hits = 0
        pass2_cache_misses = 0
        pass2_total_input_tokens = 0
        pass2_total_output_tokens = 0
        pass2_total_cost = 0.0

        for i, job in enumerate(linkedin_jobs, 1):
            print(f"\n{'=' * 120}")
            print(f"[{i}/{len(linkedin_jobs)}] {job['company_name']} - {job['job_title']}")
            print(f"{'=' * 120}")

            job_result = {
                "job": job,
                "pass1_result": None,
                "pass2_result": None,
                "pass1_from_cache": False,
                "pass2_success": False,
            }

            # ═══════════════════════════════════════════════════════════════
            # STEP 1: Get Pass 1 results (from cache or fresh execution)
            # ═══════════════════════════════════════════════════════════════
            pass1_result = None
            pass1_extraction = None

            if use_cache:
                cached = _load_from_cache(job)
                if cached and cached.get('pass1_success'):
                    print(f"✓ Pass 1: Loaded from cache")
                    pass1_result = cached
                    job_result["pass1_from_cache"] = True
                    pass1_cache_hits += 1

                    # Reconstruct pass1_extraction from flattened ext_* fields
                    # This is a simplified reconstruction - in production you'd save the raw JSON
                    pass1_extraction = {
                        "skills_classified": {
                            "must_have_hard_skills": cached.get("ext_must_have_hard_skills"),
                            "nice_to_have_hard_skills": cached.get("ext_nice_to_have_hard_skills"),
                            "must_have_soft_skills": cached.get("ext_must_have_soft_skills"),
                            "nice_to_have_soft_skills": cached.get("ext_nice_to_have_soft_skills"),
                            "certifications_mentioned": cached.get("ext_certifications_mentioned"),
                            "years_experience_min": cached.get("ext_years_experience_min"),
                            "years_experience_max": cached.get("ext_years_experience_max"),
                            "years_experience_text": cached.get("ext_years_experience_text"),
                            "education_stated": cached.get("ext_education_stated"),
                            "llm_genai_mentioned": cached.get("ext_llm_genai_mentioned"),
                            "feature_store_mentioned": cached.get("ext_feature_store_mentioned"),
                        },
                        "compensation": {
                            "salary_disclosed": cached.get("ext_salary_disclosed"),
                            "salary_min": cached.get("ext_salary_min"),
                            "salary_max": cached.get("ext_salary_max"),
                            "salary_currency": cached.get("ext_salary_currency"),
                            "salary_period": cached.get("ext_salary_period"),
                        },
                        "work_authorization": {
                            "visa_sponsorship_stated": cached.get("ext_visa_sponsorship_stated"),
                            "security_clearance_stated": cached.get("ext_security_clearance_stated"),
                        },
                        "work_model": {
                            "work_model_stated": cached.get("ext_work_model_stated"),
                            "employment_type_stated": cached.get("ext_employment_type_stated"),
                        },
                    }
                else:
                    pass1_cache_misses += 1

            if not pass1_result:
                print(f"→ Pass 1: Executing fresh extraction...")
                try:
                    pass1_result = enrich_single_job(job, bedrock_client=client)
                    if pass1_result.get('pass1_success'):
                        print(f"✓ Pass 1: Success (tokens: {pass1_result.get('total_tokens_used', 0)})")
                        if use_cache:
                            _save_to_cache(job, pass1_result)

                        # Extract pass1_extraction - need to reconstruct from flattened
                        pass1_extraction = {
                            "skills_classified": {
                                "must_have_hard_skills": pass1_result.get("ext_must_have_hard_skills"),
                                "nice_to_have_hard_skills": pass1_result.get("ext_nice_to_have_hard_skills"),
                                "must_have_soft_skills": pass1_result.get("ext_must_have_soft_skills"),
                                "nice_to_have_soft_skills": pass1_result.get("ext_nice_to_have_soft_skills"),
                                "certifications_mentioned": pass1_result.get("ext_certifications_mentioned"),
                                "years_experience_min": pass1_result.get("ext_years_experience_min"),
                                "years_experience_max": pass1_result.get("ext_years_experience_max"),
                                "years_experience_text": pass1_result.get("ext_years_experience_text"),
                                "education_stated": pass1_result.get("ext_education_stated"),
                                "llm_genai_mentioned": pass1_result.get("ext_llm_genai_mentioned"),
                                "feature_store_mentioned": pass1_result.get("ext_feature_store_mentioned"),
                            },
                            "compensation": {
                                "salary_disclosed": pass1_result.get("ext_salary_disclosed"),
                                "salary_min": pass1_result.get("ext_salary_min"),
                                "salary_max": pass1_result.get("ext_salary_max"),
                                "salary_currency": pass1_result.get("ext_salary_currency"),
                                "salary_period": pass1_result.get("ext_salary_period"),
                            },
                            "work_authorization": {
                                "visa_sponsorship_stated": pass1_result.get("ext_visa_sponsorship_stated"),
                                "security_clearance_stated": pass1_result.get("ext_security_clearance_stated"),
                            },
                            "work_model": {
                                "work_model_stated": pass1_result.get("ext_work_model_stated"),
                                "employment_type_stated": pass1_result.get("ext_employment_type_stated"),
                            },
                        }
                    else:
                        print(f"✗ Pass 1: Failed - {pass1_result.get('enrichment_errors', 'Unknown error')}")
                except Exception as e:
                    print(f"✗ Pass 1: Exception - {e}")
                    pass1_result = {"pass1_success": False, "enrichment_errors": str(e)}

            job_result["pass1_result"] = pass1_result

            # ═══════════════════════════════════════════════════════════════
            # STEP 2: Execute Pass 2 if Pass 1 succeeded
            # ═══════════════════════════════════════════════════════════════
            if pass1_result and pass1_result.get('pass1_success') and pass1_extraction:
                # Check if Pass 2 is already in cache
                pass2_from_cache = False
                if use_cache:
                    cached = _load_from_cache(job)
                    if cached and cached.get('pass2_success'):
                        print(f"✓ Pass 2: Loaded from cache")
                        job_result["pass2_result"] = cached.get("pass2_result_raw", {})
                        job_result["pass2_success"] = True
                        job_result["pass2_tokens"] = cached.get("pass2_tokens", 0)
                        job_result["pass2_cost"] = cached.get("pass2_cost", 0.0)
                        pass2_from_cache = True
                        pass2_cache_hits += 1

                        # Add to totals even though from cache (for reporting)
                        pass2_total_input_tokens += cached.get("pass2_input_tokens", 0)
                        pass2_total_output_tokens += cached.get("pass2_output_tokens", 0)
                        pass2_total_cost += cached.get("pass2_cost", 0.0)
                    else:
                        pass2_cache_misses += 1

                if not pass2_from_cache:
                    if not use_cache:
                        pass2_cache_misses += 1
                    print(f"→ Pass 2: Running inference...")
                    try:
                        # Build Pass 2 prompt
                        system_prompt, user_prompt = build_pass2_prompt(
                            job_title=job.get("job_title", ""),
                            company_name=job.get("company_name", ""),
                            job_location=job.get("job_location", ""),
                            job_description_text=job.get("job_description_text", ""),
                            pass1_extraction=pass1_extraction,
                        )

                        # Invoke Bedrock for Pass 2
                        response_text, input_tokens, output_tokens, cost = client.invoke(
                            prompt=user_prompt,
                            system=system_prompt,
                            pass_name="pass2",
                        )

                        pass2_total_input_tokens += input_tokens
                        pass2_total_output_tokens += output_tokens
                        pass2_total_cost += cost

                        # Parse JSON response
                        parsed, parse_error = parse_llm_json(response_text)
                        if parse_error:
                            raise ValueError(f"JSON parse error: {parse_error}")

                        # Validate schema
                        is_valid, validation_errors = validate_inference_response(parsed)
                        if not is_valid:
                            print(f"⚠ Pass 2: Validation warnings - {validation_errors}")

                        job_result["pass2_result"] = parsed.get("inference", {})
                        job_result["pass2_success"] = True
                        job_result["pass2_tokens"] = input_tokens + output_tokens
                        job_result["pass2_cost"] = cost

                        print(f"✓ Pass 2: Success (tokens: {input_tokens + output_tokens}, cost: ${cost:.6f})")

                        # Save Pass 2 to cache
                        if use_cache:
                            pass2_cache_data = {
                                "pass2_result_raw": job_result["pass2_result"],
                                "pass2_success": True,
                                "pass2_tokens": input_tokens + output_tokens,
                                "pass2_input_tokens": input_tokens,
                                "pass2_output_tokens": output_tokens,
                                "pass2_cost": cost,
                            }
                            _save_to_cache(job, pass1_result, pass2_result=pass2_cache_data)

                    except Exception as e:
                        print(f"✗ Pass 2: Failed - {e}")
                        job_result["pass2_success"] = False
                        job_result["pass2_error"] = str(e)
            else:
                print(f"⊘ Pass 2: Skipped (Pass 1 failed)")

            results.append(job_result)

        # ═══════════════════════════════════════════════════════════════
        # Print Results
        # ═══════════════════════════════════════════════════════════════
        print("\n" + "=" * 120)
        print("PASS 2 INFERENCE RESULTS")
        print("=" * 120)

        # Summary Statistics
        print(f"\nData Source: {'S3 Silver Bucket' if use_s3 else 'Local Mocks'}")
        if use_s3 and partition_info:
            print(f"Partition: {partition_info['year']}-{partition_info['month']}-{partition_info['day']} Hour {partition_info['hour']}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if use_cache:
            print(f"\nPass 1 Cache Statistics:")
            print(f"  Cache Hits: {pass1_cache_hits}")
            print(f"  Cache Misses: {pass1_cache_misses}")
            if (pass1_cache_hits + pass1_cache_misses) > 0:
                print(f"  Cache Hit Rate: {pass1_cache_hits/(pass1_cache_hits+pass1_cache_misses)*100:.1f}%")

            print(f"\nPass 2 Cache Statistics:")
            print(f"  Cache Hits: {pass2_cache_hits}")
            print(f"  Cache Misses: {pass2_cache_misses}")
            if (pass2_cache_hits + pass2_cache_misses) > 0:
                print(f"  Cache Hit Rate: {pass2_cache_hits/(pass2_cache_hits+pass2_cache_misses)*100:.1f}%")

        pass2_success_count = sum(1 for r in results if r.get('pass2_success'))
        print(f"\nPass 2 Success Rate: {pass2_success_count}/{len(results)} ({pass2_success_count/len(results)*100:.1f}%)")

        print(f"\nPass 2 Token Statistics:")
        print(f"  Input Tokens:  {pass2_total_input_tokens:,}")
        print(f"  Output Tokens: {pass2_total_output_tokens:,}")
        print(f"  Total Tokens:  {pass2_total_input_tokens + pass2_total_output_tokens:,}")

        print(f"\nPass 2 Cost Analysis:")
        print(f"  Total Cost: ${pass2_total_cost:.6f}")
        print(f"  Average Cost per Job: ${pass2_total_cost/len(results):.6f}")

        # Print detailed results for each job
        for i, job_result in enumerate(results, 1):
            print(f"\n{'=' * 120}")
            print(f"[{i}/{len(results)}] {job_result['job']['company_name']} - {job_result['job']['job_title']}")
            print(f"{'=' * 120}")

            if job_result.get('pass2_success'):
                inference = job_result.get('pass2_result', {})

                # Show RAW JSON extraction field by field
                print(f"\n{'━' * 120}")
                print(f"RAW JSON EXTRACTION - Campo a Campo")
                print(f"{'━' * 120}")

                for section_name, section_data in inference.items():
                    print(f"\n### {section_name.upper().replace('_', ' ')} ###")
                    if isinstance(section_data, dict):
                        for field_name, field_value in section_data.items():
                            print(f"  {field_name}:")
                            print(f"    {json.dumps(field_value, indent=6, ensure_ascii=False)}")
                    else:
                        print(f"  {json.dumps(section_data, indent=4, ensure_ascii=False)}")

                print(f"\n{'━' * 120}")
                print(f"FORMATTED VIEW")
                print(f"{'━' * 120}")

                # Seniority and Role
                print(f"\n--- Seniority and Role ---")
                seniority = inference.get('seniority_and_role', {})
                for field_name in ['seniority_level', 'job_family', 'sub_specialty', 'leadership_expectation']:
                    field_data = seniority.get(field_name, {})
                    if isinstance(field_data, dict):
                        value = field_data.get('value')
                        confidence = field_data.get('confidence', 0)
                        evidence = field_data.get('evidence', '')
                        print(f"  {field_name}: {value} (conf: {confidence:.2f})")
                        print(f"    Evidence: {evidence}")

                # Stack and Cloud
                print(f"\n--- Stack and Cloud ---")
                stack = inference.get('stack_and_cloud', {})
                for field_name in ['primary_cloud', 'secondary_clouds', 'processing_paradigm',
                                   'orchestrator_category', 'storage_layer']:
                    field_data = stack.get(field_name, {})
                    if isinstance(field_data, dict):
                        value = field_data.get('value')
                        confidence = field_data.get('confidence', 0)
                        evidence = field_data.get('evidence', '')[:100]
                        print(f"  {field_name}: {value} (conf: {confidence:.2f})")
                        if evidence:
                            print(f"    Evidence: {evidence}...")

                # Geo and Work Model
                print(f"\n--- Geo and Work Model ---")
                geo = inference.get('geo_and_work_model', {})
                for field_name in ['remote_restriction', 'timezone_focus', 'relocation_required']:
                    field_data = geo.get(field_name, {})
                    if isinstance(field_data, dict):
                        value = field_data.get('value')
                        confidence = field_data.get('confidence', 0)
                        evidence = field_data.get('evidence', '')[:100]
                        print(f"  {field_name}: {value} (conf: {confidence:.2f})")
                        if evidence:
                            print(f"    Evidence: {evidence}...")

                # Visa and Authorization
                print(f"\n--- Visa and Authorization ---")
                visa = inference.get('visa_and_authorization', {})
                for field_name in ['h1b_friendly', 'opt_cpt_friendly', 'citizenship_required']:
                    field_data = visa.get(field_name, {})
                    if isinstance(field_data, dict):
                        value = field_data.get('value')
                        confidence = field_data.get('confidence', 0)
                        evidence = field_data.get('evidence', '')[:100]
                        print(f"  {field_name}: {value} (conf: {confidence:.2f})")
                        if evidence:
                            print(f"    Evidence: {evidence}...")

                # Contract and Compensation
                print(f"\n--- Contract and Compensation ---")
                contract = inference.get('contract_and_compensation', {})
                for field_name in ['w2_vs_1099', 'benefits_level']:
                    field_data = contract.get(field_name, {})
                    if isinstance(field_data, dict):
                        value = field_data.get('value')
                        confidence = field_data.get('confidence', 0)
                        evidence = field_data.get('evidence', '')[:100]
                        print(f"  {field_name}: {value} (conf: {confidence:.2f})")
                        if evidence:
                            print(f"    Evidence: {evidence}...")

                # Career Development
                print(f"\n--- Career Development ---")
                career = inference.get('career_development', {})
                for field_name in ['growth_path_clarity', 'mentorship_signals', 'promotion_path_mentioned',
                                   'internal_mobility_mentioned', 'career_tracks_available']:
                    field_data = career.get(field_name, {})
                    if isinstance(field_data, dict):
                        value = field_data.get('value')
                        confidence = field_data.get('confidence', 0)
                        evidence = field_data.get('evidence', '')[:100]
                        print(f"  {field_name}: {value} (conf: {confidence:.2f})")
                        if evidence:
                            print(f"    Evidence: {evidence}...")

                # Requirements Classification
                print(f"\n--- Requirements Classification ---")
                requirements = inference.get('requirements_classification', {})
                for field_name in ['requirement_strictness', 'scope_definition', 'skill_inflation_detected']:
                    field_data = requirements.get(field_name, {})
                    if isinstance(field_data, dict):
                        value = field_data.get('value')
                        confidence = field_data.get('confidence', 0)
                        evidence = field_data.get('evidence', '')[:100]
                        print(f"  {field_name}: {value} (conf: {confidence:.2f})")
                        if evidence:
                            print(f"    Evidence: {evidence}...")
            else:
                error = job_result.get('pass2_error', 'Pass 1 failed')
                print(f"\n✗ Pass 2 Failed: {error}")

        print("\n" + "=" * 120)
        return pass2_success_count == len(results)

    except Exception as e:
        print(f"\n✗ Pass 2 test FAILED: {e}")

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
    parser.add_argument("--compare", action="store_true", help="Test Pass 1 with multiple real LinkedIn jobs and compare")
    parser.add_argument("--s3-source", action="store_true", help="Use real jobs from S3 bucket instead of mocks (requires --compare or --pass2)")
    parser.add_argument("--date", type=str, help="Partition date in YYYY-MM-DD format (uses latest hour of that day). Defaults to most recent partition if not specified. Requires --s3-source.")
    parser.add_argument("--limit", type=int, default=5, help="Number of jobs to process (default: 5). Used with --s3-source.")
    parser.add_argument("--cache", action="store_true", help="Enable caching of Pass 1 and Pass 2 results (saves cost during testing)")
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
            use_cache=args.cache
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
