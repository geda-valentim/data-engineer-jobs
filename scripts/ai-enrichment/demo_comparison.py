#!/usr/bin/env python3
"""
Demo script showing expected output for multiple job comparison.
Simulates what the output would look like with AWS credentials.
"""

def demo_comparison_output():
    """Demonstrate the comparison table output with mock data."""

    # Simulated results (what would come from Bedrock)
    jobs = [
        ("Precision Technologies", "United States (Remote)"),
        ("IntagHire", "Houston, TX (100% onsite)"),
        ("Eames Consulting", "United States (Remote)"),
        ("Amazon", "Seattle, WA"),
        ("Microsoft", "New York, NY (Hybrid)"),
    ]

    # Mock extraction results
    results = [
        {
            "pass1_success": True,
            "ext_salary_min": None,
            "ext_salary_max": None,
            "ext_years_experience_min": None,
            "ext_years_experience_max": None,
            "ext_work_model_stated": "remote",
            "ext_visa_sponsorship_stated": "not_mentioned",
            "ext_contract_type": "permanent",
            "ext_must_have_hard_skills": ["Python", "SQL", "Spark", "Kafka", "Airflow", "AWS", "Docker", "Terraform"],
            "ext_nice_to_have_hard_skills": ["dbt", "Kubernetes", "Great Expectations"],
            "ext_must_have_soft_skills": ["Communication", "Team Collaboration", "Problem Solving"],
            "ext_nice_to_have_soft_skills": [],
            "ext_equity_mentioned": False,
            "ext_pto_policy": "not_mentioned",
        },
        {
            "pass1_success": True,
            "ext_salary_min": None,
            "ext_salary_max": None,
            "ext_years_experience_min": None,
            "ext_years_experience_max": None,
            "ext_work_model_stated": "onsite",
            "ext_visa_sponsorship_stated": "will_not_sponsor",
            "ext_contract_type": "permanent",
            "ext_must_have_hard_skills": ["Python", "SQL", "Git"],
            "ext_nice_to_have_hard_skills": ["Psycopg3", "Pydantic", "Docker", "PostgreSQL", "ElasticSearch", "Redis", "DataDog", "GIS"],
            "ext_must_have_soft_skills": [],
            "ext_nice_to_have_soft_skills": [],
            "ext_equity_mentioned": False,
            "ext_pto_policy": "not_mentioned",
        },
        {
            "pass1_success": True,
            "ext_salary_min": 165000,
            "ext_salary_max": 185000,
            "ext_years_experience_min": 6,
            "ext_years_experience_max": 8,
            "ext_work_model_stated": "remote",
            "ext_visa_sponsorship_stated": "not_mentioned",
            "ext_contract_type": "permanent",
            "ext_must_have_hard_skills": ["Python", "SQL", "dbt", "Snowflake", "Redshift", "BigQuery"],
            "ext_nice_to_have_hard_skills": ["Databricks", "Spark"],
            "ext_must_have_soft_skills": ["Communication", "Team Collaboration"],
            "ext_nice_to_have_soft_skills": [],
            "ext_equity_mentioned": True,
            "ext_pto_policy": "unlimited",
        },
        {
            "pass1_success": True,
            "ext_salary_min": 139100,
            "ext_salary_max": 240500,
            "ext_years_experience_min": 5,
            "ext_years_experience_max": None,
            "ext_work_model_stated": "not_mentioned",
            "ext_visa_sponsorship_stated": "not_mentioned",
            "ext_contract_type": "permanent",
            "ext_must_have_hard_skills": ["Python", "SQL", "Data Modeling", "ETL Pipelines"],
            "ext_nice_to_have_hard_skills": ["Hadoop", "Hive", "Spark", "EMR", "Java", "Scala", "NodeJS"],
            "ext_must_have_soft_skills": ["Mentoring", "Leadership"],
            "ext_nice_to_have_soft_skills": [],
            "ext_equity_mentioned": True,
            "ext_pto_policy": "not_mentioned",
        },
        {
            "pass1_success": True,
            "ext_salary_min": 139900,
            "ext_salary_max": 304200,
            "ext_years_experience_min": 4,
            "ext_years_experience_max": None,
            "ext_work_model_stated": "hybrid",
            "ext_visa_sponsorship_stated": "not_mentioned",
            "ext_contract_type": "permanent",
            "ext_must_have_hard_skills": ["Python", "Java", "Spark", "SQL", "Kafka", "Hadoop"],
            "ext_nice_to_have_hard_skills": ["NoSQL", "Azure", "AWS", "GCP"],
            "ext_must_have_soft_skills": ["Communication", "Team Collaboration"],
            "ext_nice_to_have_soft_skills": [],
            "ext_equity_mentioned": True,
            "ext_pto_policy": "not_mentioned",
        },
    ]

    print("\n" + "=" * 120)
    print("DEMO: Pass 1 Extraction - Multiple Jobs Comparison")
    print("=" * 120)
    print("Using model: openai.gpt-oss-120b-1:0")
    print("Region: us-east-1")
    print(f"Processing {len(jobs)} real LinkedIn jobs...\n")

    for i, (company, location) in enumerate(jobs, 1):
        print(f"[{i}/{len(jobs)}] Processing: {company}... ✓")

    print("\n" + "=" * 120)
    print("RESULTS COMPARISON TABLE")
    print("=" * 120)

    # Print header
    fields = ["Success", "Salary Min", "Salary Max", "Yrs Exp Min", "Yrs Exp Max", "Work Model", "Visa", "Contract", "Must Skills", "Nice Skills", "Equity", "PTO"]
    print(f"{'Company':<25} | ", end="")
    for field in fields:
        print(f"{field:>12} | ", end="")
    print()
    print("-" * 120)

    # Print each row
    for (company, location), result in zip(jobs, results):
        company_short = company[:24]
        print(f"{company_short:<25} | ", end="")

        # Success
        print(f"{'✓':>12} | ", end="")

        # Salary Min
        sal_min = f"${result['ext_salary_min']:,.0f}" if result['ext_salary_min'] else "-"
        print(f"{sal_min:>12} | ", end="")

        # Salary Max
        sal_max = f"${result['ext_salary_max']:,.0f}" if result['ext_salary_max'] else "-"
        print(f"{sal_max:>12} | ", end="")

        # Years Exp Min
        yrs_min = result['ext_years_experience_min'] or "-"
        print(f"{str(yrs_min):>12} | ", end="")

        # Years Exp Max
        yrs_max = result['ext_years_experience_max'] or "-"
        print(f"{str(yrs_max):>12} | ", end="")

        # Work Model
        work = result['ext_work_model_stated'] or "-"
        print(f"{work:>12} | ", end="")

        # Visa
        visa = result['ext_visa_sponsorship_stated'] or "-"
        print(f"{visa[:12]:>12} | ", end="")

        # Contract
        contract = result['ext_contract_type'] or "-"
        print(f"{contract:>12} | ", end="")

        # Must Skills count
        must = len(result['ext_must_have_hard_skills'])
        print(f"{must:>12} | ", end="")

        # Nice Skills count
        nice = len(result['ext_nice_to_have_hard_skills'])
        print(f"{nice:>12} | ", end="")

        # Equity
        equity = "Yes" if result['ext_equity_mentioned'] else "No"
        print(f"{equity:>12} | ", end="")

        # PTO
        pto = result['ext_pto_policy'] or "-"
        print(f"{pto:>12} | ", end="")

        print()

    # Detailed skills breakdown
    print("\n" + "=" * 120)
    print("DETAILED SKILLS BREAKDOWN")
    print("=" * 120)

    for (company, location), result in zip(jobs, results):
        print(f"\n{company}")
        print(f"Location: {location}")

        must_hard = result['ext_must_have_hard_skills']
        nice_hard = result['ext_nice_to_have_hard_skills']
        must_soft = result['ext_must_have_soft_skills']
        nice_soft = result['ext_nice_to_have_soft_skills']

        if must_hard:
            print(f"  Must-Have Tech: {', '.join(must_hard)}")
        if nice_hard:
            print(f"  Nice-To-Have Tech: {', '.join(nice_hard)}")
        if must_soft:
            print(f"  Must-Have Soft: {', '.join(must_soft)}")
        if nice_soft:
            print(f"  Nice-To-Have Soft: {', '.join(nice_soft)}")

    # Summary statistics
    print("\n" + "=" * 120)
    print("SUMMARY STATISTICS")
    print("=" * 120)

    successful = sum(1 for r in results if r['pass1_success'])
    total_cost = 0.001193 * len(results)  # ~$0.0012 per job
    avg_cost = total_cost / len(results)

    print(f"Success Rate: {successful}/{len(results)} ({successful/len(results)*100:.1f}%)")
    print(f"Total Cost: ${total_cost:.6f}")
    print(f"Average Cost per Job: ${avg_cost:.6f}")
    print(f"\n✓ All jobs processed successfully!")

    # Key insights
    print("\n" + "=" * 120)
    print("KEY INSIGHTS FROM EXTRACTION")
    print("=" * 120)

    print("\n1. SALARY DISCLOSURE:")
    disclosed = sum(1 for r in results if r['ext_salary_min'] is not None)
    print(f"   - {disclosed}/5 jobs disclose salary ranges")
    print(f"   - Range: $139K - $304K (for disclosed positions)")

    print("\n2. WORK MODEL:")
    work_models = {}
    for r in results:
        model = r['ext_work_model_stated']
        work_models[model] = work_models.get(model, 0) + 1
    for model, count in work_models.items():
        print(f"   - {model}: {count} job(s)")

    print("\n3. VISA SPONSORSHIP:")
    visa_policies = {}
    for r in results:
        policy = r['ext_visa_sponsorship_stated']
        visa_policies[policy] = visa_policies.get(policy, 0) + 1
    for policy, count in visa_policies.items():
        print(f"   - {policy}: {count} job(s)")

    print("\n4. SKILLS REQUIREMENTS:")
    total_must = sum(len(r['ext_must_have_hard_skills']) for r in results)
    total_nice = sum(len(r['ext_nice_to_have_hard_skills']) for r in results)
    avg_must = total_must / len(results)
    avg_nice = total_nice / len(results)
    print(f"   - Average must-have skills: {avg_must:.1f}")
    print(f"   - Average nice-to-have skills: {avg_nice:.1f}")

    print("\n5. BENEFITS:")
    with_equity = sum(1 for r in results if r['ext_equity_mentioned'])
    with_unlimited_pto = sum(1 for r in results if r['ext_pto_policy'] == 'unlimited')
    print(f"   - Jobs offering equity: {with_equity}/5")
    print(f"   - Jobs with unlimited PTO: {with_unlimited_pto}/5")


if __name__ == "__main__":
    demo_comparison_output()
