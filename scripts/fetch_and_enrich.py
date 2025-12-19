#!/usr/bin/env python3
"""
Fetch job data from Silver layer and start enrichment.
Usage: python fetch_and_enrich.py <job_id> [--force] [--pass <pass_name>]
"""

import sys
import json
import argparse
import awswrangler as wr
import boto3


def fetch_job_from_silver(job_id: str) -> dict:
    """Fetch complete job data from Silver layer using Athena for efficiency."""
    import boto3
    import time

    # Try Athena first for efficiency
    try:
        athena = boto3.client("athena")
        query = f"""
        SELECT job_posting_id, job_title, company_name, job_location, job_description_text
        FROM data_engineer_jobs_db.linkedin_silver
        WHERE job_posting_id = '{job_id}'
        LIMIT 1
        """

        response = athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={"Database": "data_engineer_jobs_db"},
            ResultConfiguration={"OutputLocation": "s3://data-engineer-jobs-silver/athena-results/"}
        )

        execution_id = response["QueryExecutionId"]

        # Wait for query to complete (max 30s)
        for _ in range(30):
            result = athena.get_query_execution(QueryExecutionId=execution_id)
            state = result["QueryExecution"]["Status"]["State"]
            if state == "SUCCEEDED":
                break
            elif state in ["FAILED", "CANCELLED"]:
                raise Exception(f"Query {state}")
            time.sleep(1)

        # Get results
        results = athena.get_query_results(QueryExecutionId=execution_id)
        rows = results["ResultSet"]["Rows"]

        if len(rows) > 1:  # First row is header
            data = rows[1]["Data"]
            return {
                "job_posting_id": data[0].get("VarCharValue", ""),
                "job_title": data[1].get("VarCharValue", ""),
                "company_name": data[2].get("VarCharValue", ""),
                "job_location": data[3].get("VarCharValue", ""),
                "job_description": data[4].get("VarCharValue", ""),
            }
    except Exception as e:
        print(f"⚠️ Athena query failed ({e}), falling back to S3 scan...")

    # Fallback: Direct S3 scan - check ALL partitions
    bucket = "data-engineer-jobs-silver"
    files = wr.s3.list_objects(f"s3://{bucket}/linkedin/", suffix=".parquet")

    print(f"  📂 Scanning {len(files)} parquet files...")

    for i, f in enumerate(files):
        try:
            # Read without filter (filter doesn't work well with string types)
            df = wr.s3.read_parquet(
                f,
                columns=["job_posting_id", "job_title", "company_name",
                         "job_location", "job_description_text", "job_description"]
            )
            # Filter in pandas (works with string comparison)
            df = df[df["job_posting_id"].astype(str) == str(job_id)]
            if len(df) > 0:
                row = df.iloc[0]
                desc_text = row.get("job_description_text")
                desc = row.get("job_description")
                job_desc = str(desc_text if desc_text and str(desc_text) != "nan" else desc or "")
                return {
                    "job_posting_id": str(row["job_posting_id"]),
                    "job_title": str(row.get("job_title", "") or ""),
                    "company_name": str(row.get("company_name", "") or ""),
                    "job_location": str(row.get("job_location", "") or ""),
                    "job_description": job_desc,
                }
        except Exception as e:
            if i < 3:  # Only print first few errors
                print(f"  ⚠️ Error reading {f.split('/')[-1]}: {e}")
            continue

    return None


def start_step_function(job_data: dict, force: bool = False) -> dict:
    """Start Step Function execution."""
    sfn = boto3.client("stepfunctions")

    # Find AI enrichment state machine
    machines = sfn.list_state_machines()["stateMachines"]
    sm_arn = next(
        (m["stateMachineArn"] for m in machines if "ai-enrichment" in m["name"]),
        None
    )

    if not sm_arn:
        raise ValueError("AI enrichment state machine not found")

    input_data = {"job_data": job_data, "source": "manual"}
    if force:
        input_data["force"] = True

    response = sfn.start_execution(
        stateMachineArn=sm_arn,
        input=json.dumps(input_data)
    )

    return response


def invoke_lambda_pass(job_data: dict, pass_name: str, force: bool = False) -> dict:
    """Invoke Lambda directly for a specific pass."""
    lmb = boto3.client("lambda")

    payload = {
        "pass_name": pass_name,
        "job_data": job_data,
        "execution_id": "manual-test",
    }
    if force:
        payload["force"] = True

    response = lmb.invoke(
        FunctionName="data-engineer-jobs-dev-enrich-partition",
        Payload=json.dumps(payload)
    )

    return json.loads(response["Payload"].read().decode())


def main():
    parser = argparse.ArgumentParser(description="Fetch job and start AI enrichment")
    parser.add_argument("job_id", help="Job posting ID to enrich")
    parser.add_argument("--force", action="store_true", help="Force reprocessing (skip cache)")
    parser.add_argument("--pass", dest="pass_name", help="Execute specific pass (pass1/pass2/pass3)")

    args = parser.parse_args()

    # Fetch job data from Silver
    print(f"🔍 Fetching job {args.job_id} from Silver layer...")
    job_data = fetch_job_from_silver(args.job_id)

    if not job_data:
        print(f"❌ Job {args.job_id} not found in Silver layer")
        sys.exit(1)

    print(f"✅ Found: {job_data['job_title']} @ {job_data['company_name']}")
    print(f"📝 Description: {len(job_data['job_description'])} chars")

    if args.pass_name:
        # Execute specific pass via Lambda
        print(f"\n🤖 Executing {args.pass_name}{'(FORCE)' if args.force else ''}...")
        result = invoke_lambda_pass(job_data, args.pass_name, args.force)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Start Step Function
        print(f"\n🚀 Starting Step Function{'(FORCE)' if args.force else ''}...")
        response = start_step_function(job_data, args.force)
        execution_name = response["executionArn"].split(":")[-1]
        print(f"✅ Execution started: {execution_name}")
        print(f"   ARN: {response['executionArn']}")


if __name__ == "__main__":
    main()
