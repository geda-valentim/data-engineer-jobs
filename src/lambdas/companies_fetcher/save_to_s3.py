"""
Lambda Companies Save to S3

Baixa os dados de company do Bright Data e salva no S3 Bronze.
Atualiza o status no DynamoDB.
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from functools import lru_cache

import boto3
import requests
from botocore.exceptions import ClientError

# Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Clients
s3_resource = boto3.resource("s3")
s3_client = boto3.client("s3")
ssm_client = boto3.client("ssm")
dynamodb = boto3.resource("dynamodb")
cloudwatch = boto3.client("cloudwatch")


@lru_cache
def get_brightdata_api_key() -> str:
    """Get BrightData API key from env or SSM."""
    api_key = os.getenv("BRIGHTDATA_API_KEY")
    if api_key:
        return api_key

    param_name = os.getenv("BRIGHTDATA_API_KEY_PARAM")
    if not param_name:
        raise RuntimeError(
            "Nenhuma cred configurada. "
            "Defina BRIGHTDATA_API_KEY (local) ou BRIGHTDATA_API_KEY_PARAM (AWS)."
        )

    resp = ssm_client.get_parameter(Name=param_name, WithDecryption=True)
    return resp["Parameter"]["Value"]


def get_config() -> dict:
    """Get Lambda configuration from environment."""
    return {
        "bronze_bucket": os.getenv("BRONZE_BUCKET_NAME"),
        "companies_status_table": os.getenv("COMPANIES_STATUS_TABLE"),
        "refresh_days": int(os.getenv("REFRESH_DAYS", 180)),
    }


def download_snapshot(api_key: str, snapshot_id: str) -> bytes:
    """Download snapshot content from Bright Data."""
    url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    logger.info("Baixando snapshot: %s", snapshot_id)

    response = requests.get(url, headers=headers, timeout=120)
    response.raise_for_status()

    logger.info("Snapshot baixado: %d bytes", len(response.content))
    return response.content


def parse_company_data(raw_body: bytes) -> dict | None:
    """Parse company data from snapshot content."""
    text = raw_body.decode("utf-8", errors="replace").strip()
    if not text:
        return None

    try:
        # Pode ser JSON array ou JSONL
        if text.startswith("["):
            data = json.loads(text)
            return data[0] if data else None
        else:
            # JSONL - primeira linha
            first_line = text.split("\n")[0].strip()
            if first_line:
                return json.loads(first_line)
        return None
    except Exception as e:
        logger.warning("Erro ao parsear snapshot: %s", e)
        return None


def save_to_bronze(bucket: str, company_id: str, data: bytes) -> str:
    """Save company data to S3 Bronze layer."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"linkedin_companies/company_id={company_id}/snapshot_{today}.json"

    s3_resource.Object(bucket, key).put(
        Body=data,
        ContentType="application/json",
    )

    logger.info("Company salva em s3://%s/%s", bucket, key)
    return key


def update_company_status(
    table,
    company_id: str,
    company_url: str,
    company_name: str,
    status: str,
    refresh_days: int,
    s3_key: str = None,
    error: str = None,
):
    """Update company status in DynamoDB."""
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    if status == "success":
        next_refresh = now + timedelta(days=refresh_days)
    else:
        next_refresh = now + timedelta(days=1)

    item = {
        "company_id": company_id,
        "company_url": company_url or "",
        "company_name": company_name or "",
        "status": status,
        "last_fetched_at": now_iso,
        "next_refresh_after": next_refresh.isoformat(),
        "updated_at": now_iso,
    }

    if s3_key:
        item["s3_key"] = s3_key
    if error:
        item["last_error"] = error[:500]

    # Preserve created_at
    try:
        existing = table.get_item(Key={"company_id": company_id}).get("Item")
        if existing:
            item["created_at"] = existing.get("created_at", now_iso)
        else:
            item["created_at"] = now_iso
    except ClientError:
        item["created_at"] = now_iso

    table.put_item(Item=item)
    logger.info("Status atualizado para company %s: %s", company_id, status)


def put_metric(name: str, value: float = 1.0, dimensions: dict = None):
    """Send metric to CloudWatch."""
    dims = [{"Name": k, "Value": str(v)} for k, v in (dimensions or {}).items() if v]

    try:
        cloudwatch.put_metric_data(
            Namespace="LinkedInCompanies",
            MetricData=[{
                "MetricName": name,
                "Value": value,
                "Unit": "Count",
                "Dimensions": dims,
            }],
        )
    except Exception as e:
        logger.warning("Erro ao enviar metrica %s: %s", name, e)


def handler(event, context):
    """
    Lambda handler - Save company to S3.

    Event:
        snapshot_id: str - ID do snapshot no Bright Data
        company_id: str - ID da empresa
        company_url: str - URL da empresa
        company_name: str - Nome da empresa
        status: str - Status do check (deve ser READY)

    Returns:
        {
            status: "SAVED" | "SAVED_EMPTY" | "ERROR",
            company_id: str,
            s3_key: str,
            bucket: str
        }
    """
    logger.info("Evento recebido: %s", json.dumps(event))

    config = get_config()
    api_key = get_brightdata_api_key()

    snapshot_id = event.get("snapshot_id")
    company_id = event.get("company_id")
    company_url = event.get("company_url")
    company_name = event.get("company_name")

    if not snapshot_id:
        raise ValueError("snapshot_id não encontrado no event")

    if not company_id:
        raise ValueError("company_id não encontrado no event")

    bucket = config["bronze_bucket"]
    if not bucket:
        raise ValueError("BRONZE_BUCKET_NAME não configurado")

    # Get DynamoDB table
    table = None
    if config["companies_status_table"]:
        table = dynamodb.Table(config["companies_status_table"])

    try:
        # Download snapshot from Bright Data
        raw_content = download_snapshot(api_key, snapshot_id)

        # Parse to verify it's valid
        company_data = parse_company_data(raw_content)

        if not company_data:
            logger.warning("Snapshot %s retornou vazio", snapshot_id)
            if table:
                update_company_status(
                    table=table,
                    company_id=company_id,
                    company_url=company_url,
                    company_name=company_name,
                    status="empty",
                    refresh_days=config["refresh_days"],
                )
            put_metric("CompanySaveEmpty")
            return {
                "status": "SAVED_EMPTY",
                "company_id": company_id,
                "snapshot_id": snapshot_id,
            }

        # Save to S3
        s3_key = save_to_bronze(bucket, company_id, raw_content)

        # Update DynamoDB status
        if table:
            update_company_status(
                table=table,
                company_id=company_id,
                company_url=company_url,
                company_name=company_name,
                status="success",
                refresh_days=config["refresh_days"],
                s3_key=s3_key,
            )

        put_metric("CompanySaveSuccess")

        return {
            "status": "SAVED",
            "company_id": company_id,
            "company_name": company_name,
            "snapshot_id": snapshot_id,
            "bucket": bucket,
            "s3_key": s3_key,
            "content_length_bytes": len(raw_content),
        }

    except Exception as e:
        error_msg = str(e)[:200]
        logger.error("Erro ao salvar company %s: %s", company_id, error_msg, exc_info=True)

        if table:
            update_company_status(
                table=table,
                company_id=company_id,
                company_url=company_url,
                company_name=company_name,
                status="failed",
                refresh_days=config["refresh_days"],
                error=error_msg,
            )

        put_metric("CompanySaveFailed")
        raise


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    test_event = {
        "snapshot_id": "s_miwjgryf1gu5povbkx",
        "company_id": "2209560",
        "company_url": "https://www.linkedin.com/company/m3bi",
        "company_name": "M3BI",
        "status": "READY",
    }

    print(handler(test_event, None))
