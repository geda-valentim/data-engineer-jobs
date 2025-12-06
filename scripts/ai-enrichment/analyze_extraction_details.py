#!/usr/bin/env python3
"""
Detailed extraction analysis - shows ALL extracted fields for each job
to verify schema v3.3 implementation quality.
"""
import os
import sys

# Add the parent directory to the path so we can import from enrich_partition
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'lambdas', 'ai_enrichment'))


def analyze_extraction_details():
    """Run detailed field-by-field analysis of extraction quality."""

    from enrich_partition.handler import enrich_single_job
    from enrich_partition.bedrock_client import BedrockClient

    # Same 5 jobs from test_enrichment_local.py
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

    region = os.getenv("AWS_REGION", "us-east-1")
    model = os.getenv("BEDROCK_MODEL_PASS1", "openai.gpt-oss-120b-1:0")

    print("\n" + "=" * 120)
    print("DETAILED EXTRACTION ANALYSIS - Pass 1 Schema v3.3")
    print("=" * 120)
    print(f"Model: {model}")
    print(f"Region: {region}\n")

    # Create client
    client = BedrockClient(
        model_ids={"pass1": model, "pass2": model, "pass3": model},
        region=region,
    )

    # Process all jobs
    results = []
    for i, job in enumerate(linkedin_jobs, 1):
        print(f"[{i}/5] Processing {job['company_name']}...")
        try:
            result = enrich_single_job(job, bedrock_client=client)
            results.append((job, result))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append((job, {"pass1_success": False, "error": str(e)}))

    # Print detailed analysis for each job
    for job, result in results:
        print_job_detailed_analysis(job, result)

    # Print comparative analysis
    print_comparative_analysis(results)


def print_job_detailed_analysis(job, result):
    """Print all extracted fields for a single job."""

    company = job['company_name']
    title = job['job_title']

    print("\n" + "=" * 120)
    print(f"{company} - {title}")
    print("=" * 120)

    if not result.get('pass1_success'):
        print(f"❌ EXTRACTION FAILED: {result.get('error', 'Unknown error')}")
        return

    print("✅ EXTRACTION SUCCESSFUL\n")

    # COMPENSATION
    print("📊 COMPENSATION")
    print(f"  salary_disclosed:     {result.get('ext_salary_disclosed', '-')}")
    print(f"  salary_min:           {format_currency(result.get('ext_salary_min'), result.get('ext_salary_currency'))}")
    print(f"  salary_max:           {format_currency(result.get('ext_salary_max'), result.get('ext_salary_currency'))}")
    print(f"  salary_period:        {result.get('ext_salary_period', '-')}")
    print(f"  salary_text_raw:      {truncate(result.get('ext_salary_text_raw'), 60)}")
    print(f"  equity_mentioned:     {result.get('ext_equity_mentioned', '-')}")

    # WORK AUTHORIZATION
    print("\n🛂 WORK AUTHORIZATION")
    print(f"  visa_sponsorship:     {result.get('ext_visa_sponsorship_stated', '-')}")
    print(f"  work_auth_text:       {truncate(result.get('ext_work_auth_text'), 60)}")
    print(f"  security_clearance:   {result.get('ext_security_clearance_stated', '-')}")

    # WORK MODEL
    print("\n🏢 WORK MODEL")
    print(f"  work_model_stated:    {result.get('ext_work_model_stated', '-')}")
    print(f"  employment_type:      {result.get('ext_employment_type_stated', '-')}")

    # CONTRACT DETAILS
    print("\n📝 CONTRACT DETAILS")
    print(f"  contract_type:        {result.get('ext_contract_type', '-')}")
    print(f"  duration_months:      {result.get('ext_contract_duration_months', '-')}")
    print(f"  extension_possible:   {result.get('ext_extension_possible', '-')}")
    print(f"  conversion_to_fte:    {result.get('ext_conversion_to_fte', '-')}")
    print(f"  start_date:           {result.get('ext_start_date', '-')}")

    # SKILLS CLASSIFIED
    print("\n🛠️  SKILLS CLASSIFIED")
    must_hard = result.get('ext_must_have_hard_skills', []) or []
    nice_hard = result.get('ext_nice_to_have_hard_skills', []) or []
    must_soft = result.get('ext_must_have_soft_skills', []) or []
    nice_soft = result.get('ext_nice_to_have_soft_skills', []) or []

    print(f"  must_have_hard ({len(must_hard)}):      {format_skills(must_hard, 10)}")
    print(f"  nice_to_have_hard ({len(nice_hard)}):   {format_skills(nice_hard, 10)}")
    print(f"  must_have_soft ({len(must_soft)}):      {format_skills(must_soft, 10)}")
    print(f"  nice_to_have_soft ({len(nice_soft)}):   {format_skills(nice_soft, 10)}")
    print(f"  years_exp_min:        {result.get('ext_years_experience_min', '-')}")
    print(f"  years_exp_max:        {result.get('ext_years_experience_max', '-')}")
    print(f"  years_exp_text:       {truncate(result.get('ext_years_experience_text'), 60)}")
    print(f"  education_stated:     {truncate(result.get('ext_education_stated'), 60)}")

    # GEOGRAPHIC RESTRICTIONS
    print("\n🌍 GEOGRAPHIC RESTRICTIONS")
    print(f"  geo_restriction_type: {result.get('ext_geo_restriction_type', '-')}")
    print(f"  allowed_countries:    {result.get('ext_allowed_countries', '-')}")
    print(f"  residency_req:        {result.get('ext_residency_requirement', '-')}")

    # BENEFITS
    print("\n💰 BENEFITS STRUCTURED")
    print(f"  learning_budget:      {result.get('ext_learning_budget_mentioned', '-')}")
    print(f"  conference_budget:    {result.get('ext_conference_budget_mentioned', '-')}")
    print(f"  hardware_choice:      {result.get('ext_hardware_choice_mentioned', '-')}")
    print(f"  pto_policy:           {result.get('ext_pto_policy', '-')}")

    # COST
    print(f"\n💵 Cost: ${result.get('enrichment_cost_usd', 0):.6f}")


def print_comparative_analysis(results):
    """Print comparative analysis across all jobs."""

    print("\n\n" + "=" * 120)
    print("COMPARATIVE ANALYSIS - Schema v3.3 Field Coverage")
    print("=" * 120)

    # Field groups to analyze
    field_groups = {
        "Compensation": ["ext_salary_min", "ext_salary_max", "ext_equity_mentioned"],
        "Work Auth": ["ext_visa_sponsorship_stated", "ext_security_clearance_stated"],
        "Work Model": ["ext_work_model_stated", "ext_employment_type_stated"],
        "Contract": ["ext_contract_type", "ext_contract_duration_months"],
        "Skills": ["ext_must_have_hard_skills", "ext_nice_to_have_hard_skills",
                   "ext_must_have_soft_skills", "ext_nice_to_have_soft_skills"],
        "Experience": ["ext_years_experience_min", "ext_years_experience_max"],
        "Geographic": ["ext_geo_restriction_type", "ext_allowed_countries"],
        "Benefits": ["ext_pto_policy", "ext_learning_budget_mentioned"]
    }

    print(f"\n{'Field Group':<20} | {'Precision':<12} | {'IntagHire':<12} | {'Eames':<12} | {'Amazon':<12} | {'Microsoft':<12}")
    print("-" * 120)

    for group_name, fields in field_groups.items():
        coverage = []
        for _, result in results:
            if not result.get('pass1_success'):
                coverage.append("FAIL")
                continue

            # Count how many fields in this group have non-null values
            populated = sum(1 for f in fields if is_populated(result.get(f)))
            coverage.append(f"{populated}/{len(fields)}")

        print(f"{group_name:<20} | {coverage[0]:>12} | {coverage[1]:>12} | {coverage[2]:>12} | {coverage[3]:>12} | {coverage[4]:>12}")

    # Skills classification quality analysis
    print("\n" + "=" * 120)
    print("SKILLS CLASSIFICATION QUALITY ANALYSIS")
    print("=" * 120)
    print(f"\n{'Company':<25} | {'Must Hard':<10} | {'Nice Hard':<10} | {'Must Soft':<10} | {'Nice Soft':<10} | {'Assessment'}")
    print("-" * 120)

    for job, result in results:
        if not result.get('pass1_success'):
            continue

        company = job['company_name'][:24]
        must_hard = len(result.get('ext_must_have_hard_skills', []) or [])
        nice_hard = len(result.get('ext_nice_to_have_hard_skills', []) or [])
        must_soft = len(result.get('ext_must_have_soft_skills', []) or [])
        nice_soft = len(result.get('ext_nice_to_have_soft_skills', []) or [])

        # Assess quality
        assessment = assess_skills_classification(job, result)

        print(f"{company:<25} | {must_hard:>10} | {nice_hard:>10} | {must_soft:>10} | {nice_soft:>10} | {assessment}")

    # Summary statistics
    print("\n" + "=" * 120)
    print("SUMMARY STATISTICS")
    print("=" * 120)

    successful = sum(1 for _, r in results if r.get('pass1_success'))
    total_cost = sum(r.get('enrichment_cost_usd', 0) for _, r in results if r.get('pass1_success'))

    print(f"\nSuccess Rate: {successful}/{len(results)} ({successful/len(results)*100:.1f}%)")
    print(f"Total Cost: ${total_cost:.6f}")
    print(f"Average Cost: ${total_cost/len(results):.6f} per job")


def assess_skills_classification(job, result):
    """Assess the quality of skills classification for a job."""

    company = job['company_name']
    must_hard = len(result.get('ext_must_have_hard_skills', []) or [])
    nice_hard = len(result.get('ext_nice_to_have_hard_skills', []) or [])
    must_soft = len(result.get('ext_must_have_soft_skills', []) or [])
    nice_soft = len(result.get('ext_nice_to_have_soft_skills', []) or [])

    # IntagHire - has explicit "Must Have" and "Good Skills to Have" sections
    if company == "IntagHire":
        if must_hard == 4 and nice_hard > 5:
            return "✅ EXCELLENT - Correctly classified"
        return "⚠️  Check classification"

    # Eames Consulting - has "Preferred" but with STRONG qualifiers inside
    if company == "Eames Consulting":
        if must_hard > 10 and nice_hard < 10:
            return "✅ GOOD - Strong qualifiers recognized"
        elif must_hard == 0 and nice_hard > 20:
            return "❌ FAILED - Ignored internal qualifiers!"
        return "⚠️  Partial - Some qualifiers missed"

    # Amazon - has "Basic Qualifications" and "Preferred Qualifications"
    if company == "Amazon":
        if must_hard > 5 and nice_hard > 0 and must_soft > 0:
            return "✅ GOOD - Clear section-based classification"
        return "⚠️  Review needed"

    # Microsoft - has "Required" and "Preferred" qualifications
    if company == "Microsoft":
        if must_hard > 3 and nice_hard > 5:
            return "✅ ACCEPTABLE - Section-based"
        return "⚠️  Review needed"

    # Precision Technologies - no clear must-have vs nice-to-have distinction
    if company == "Precision Technologies":
        if must_hard > 15 and nice_hard == 0:
            return "✅ EXPECTED - All responsibilities are must-have"
        return "⚠️  Check classification"

    return "❓ Unknown pattern"


def format_currency(amount, currency):
    """Format currency amount."""
    if amount is None:
        return "-"
    curr = currency or "USD"
    return f"${amount:,.0f} {curr}"


def format_skills(skills, max_display=10):
    """Format skills list for display."""
    if not skills:
        return "-"
    if len(skills) <= max_display:
        return ", ".join(skills[:max_display])
    return f"{', '.join(skills[:max_display])}... (+{len(skills)-max_display} more)"


def truncate(text, max_len=60):
    """Truncate text to max length."""
    if not text:
        return "-"
    if len(text) <= max_len:
        return text
    return text[:max_len-3] + "..."


def is_populated(value):
    """Check if a field value is populated (not None, not empty)."""
    if value is None:
        return False
    if isinstance(value, (list, str)) and len(value) == 0:
        return False
    if isinstance(value, str) and value in ["-", "not_mentioned", "none"]:
        return False
    return True


if __name__ == "__main__":
    analyze_extraction_details()
