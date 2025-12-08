"""
Lambda Companies Fetcher

Consome mensagens SQS com company_id/company_url e busca dados
da empresa via Bright Data Companies Information API.

Usa DynamoDB para evitar buscas duplicadas (cache com TTL de 6 meses).
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from typing import Optional

import boto3
import requests
from botocore.exceptions import ClientError

# Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Clients
dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")
ssm_client = boto3.client("ssm")
cloudwatch = boto3.client("cloudwatch")

# Constants
BRIGHTDATA_COMPANIES_URL = "https://api.brightdata.com/datasets/v3/trigger"
DEFAULT_REFRESH_DAYS = 180  # 6 meses


# =============================================================================
# Helpers - Configuration
# =============================================================================

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
        "companies_status_table": os.getenv("COMPANIES_STATUS_TABLE"),
        "bronze_bucket": os.getenv("BRONZE_BUCKET_NAME"),
        "companies_dataset_id": os.getenv("BRIGHTDATA_COMPANIES_DATASET_ID", "gd_l1vikfnt1wgvvqz95w"),
        "refresh_days": int(os.getenv("REFRESH_DAYS", DEFAULT_REFRESH_DAYS)),
    }


# =============================================================================
# DynamoDB Operations
# =============================================================================

def get_company_status(table, company_id: str) -> Optional[dict]:
    """
    Get company status from DynamoDB.

    Returns None if company not found.
    """
    try:
        response = table.get_item(Key={"company_id": company_id})
        return response.get("Item")
    except ClientError as e:
        logger.error("Erro ao buscar status da company %s: %s", company_id, e)
        raise


def needs_refresh(status: dict) -> bool:
    """
    Check if company needs to be refreshed.

    Returns True if:
    - status is not "success"
    - next_refresh_after has passed
    """
    if status.get("status") != "success":
        return True

    next_refresh = status.get("next_refresh_after")
    if not next_refresh:
        return True

    now = datetime.now(timezone.utc)
    refresh_at = datetime.fromisoformat(next_refresh.replace("Z", "+00:00"))

    return now >= refresh_at


def update_company_status(
    table,
    company_id: str,
    company_url: str,
    company_name: str,
    status: str,
    refresh_days: int,
    error: Optional[str] = None,
):
    """Update company status in DynamoDB."""
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # Se falhou, tenta de novo em 1 dia; se sucesso, em refresh_days
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

    if error:
        item["last_error"] = error[:500]  # Truncate error message

    # Conditional write - only set created_at if new
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


# =============================================================================
# Bright Data API
# =============================================================================

def fetch_company_from_brightdata(api_key: str, dataset_id: str, company_url: str) -> dict:
    """
    Fetch company data from Bright Data Companies Information API.

    This triggers a synchronous collection and returns the data.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    params = {
        "dataset_id": dataset_id,
        "include_errors": "true",
        "format": "json",
    }

    data = [{"url": company_url}]

    logger.info("Buscando company: %s (dataset: %s)", company_url, dataset_id)

    response = requests.post(
        BRIGHTDATA_COMPANIES_URL,
        headers=headers,
        params=params,
        json=data,
        timeout=120,
    )

    response.raise_for_status()

    result = response.json()
    logger.info("Response da Bright Data: %s", json.dumps(result)[:500])

    return result


# =============================================================================
# Bright Data - Polling & Download
# =============================================================================

def check_snapshot_status(api_key: str, snapshot_id: str) -> str:
    """Check snapshot status from Bright Data."""
    url = f"https://api.brightdata.com/datasets/v3/progress/{snapshot_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()

    return (data.get("status") or "").lower()


def download_snapshot(api_key: str, snapshot_id: str) -> bytes:
    """Download snapshot content from Bright Data."""
    url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    response = requests.get(url, headers=headers, timeout=120)
    response.raise_for_status()

    return response.content


def parse_company_data(raw_body: bytes) -> dict | None:
    """Parse company data from snapshot content."""
    text = raw_body.decode("utf-8", errors="replace").strip()
    if not text:
        return None

    try:
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


def wait_for_snapshot_and_download(
    api_key: str,
    snapshot_id: str,
    max_attempts: int = 30,
    wait_seconds: int = 10,
) -> dict | None:
    """
    Aguarda snapshot ficar pronto e baixa os dados.

    Faz polling síncrono - a função só retorna quando o snapshot
    está pronto ou após timeout.

    Returns:
        dict com dados da empresa ou None se timeout/erro
    """
    import time

    for attempt in range(1, max_attempts + 1):
        logger.info(
            "Verificando snapshot %s (tentativa %d/%d)",
            snapshot_id, attempt, max_attempts
        )

        try:
            status = check_snapshot_status(api_key, snapshot_id)
            logger.info("Snapshot %s status: %s", snapshot_id, status)

            if status == "ready":
                # Baixa os dados
                raw_content = download_snapshot(api_key, snapshot_id)
                logger.info("Snapshot %s baixado: %d bytes", snapshot_id, len(raw_content))

                company_data = parse_company_data(raw_content)
                return company_data

            if status in ("failed", "error"):
                logger.error("Snapshot %s falhou: %s", snapshot_id, status)
                return None

        except Exception as e:
            logger.warning("Erro ao verificar snapshot %s: %s", snapshot_id, e)

        # Aguarda antes da próxima tentativa
        if attempt < max_attempts:
            time.sleep(wait_seconds)

    logger.warning("Timeout esperando snapshot %s após %d tentativas", snapshot_id, max_attempts)
    return None


# =============================================================================
# S3 Operations
# =============================================================================

def save_company_to_bronze(bucket: str, company_id: str, data: dict):
    """
    Save company data to S3 Bronze layer.

    Key pattern: linkedin_companies/company_id={id}/snapshot_{date}.json
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"linkedin_companies/company_id={company_id}/snapshot_{today}.json"

    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(data, ensure_ascii=False, indent=2),
        ContentType="application/json",
    )

    logger.info("Company salva em s3://%s/%s", bucket, key)
    return key


# =============================================================================
# CloudWatch Metrics
# =============================================================================

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


# =============================================================================
# Message Processing
# =============================================================================

def process_company_message(msg: dict, config: dict, api_key: str, table) -> dict:
    """
    Process a single company message.

    Returns processing result with status.
    """
    company_id = msg.get("company_id")
    company_url = msg.get("company_url")
    company_name = msg.get("company_name")

    if not company_id and not company_url:
        logger.warning("Mensagem sem company_id ou company_url: %s", msg)
        return {"status": "skipped", "reason": "missing_id_and_url"}

    # Use company_id as primary key, fallback to URL hash
    if not company_id:
        # Generate a stable ID from URL
        import hashlib
        company_id = hashlib.md5(company_url.encode()).hexdigest()[:16]
        logger.info("Gerado company_id a partir da URL: %s", company_id)

    # Check if we already have recent data
    status = get_company_status(table, company_id)

    if status and not needs_refresh(status):
        logger.info("Company %s ja foi buscada recentemente, pulando", company_id)
        put_metric("CompanyFetchSkipped", dimensions={"Reason": "cache_hit"})
        return {"status": "skipped", "reason": "cache_hit", "company_id": company_id}

    # Fetch from Bright Data
    if not company_url:
        logger.warning("Company %s sem URL, nao pode buscar", company_id)
        return {"status": "skipped", "reason": "missing_url", "company_id": company_id}

    try:
        result = fetch_company_from_brightdata(
            api_key=api_key,
            dataset_id=config["companies_dataset_id"],
            company_url=company_url,
        )

        # A Bright Data retorna um snapshot_id, nao os dados diretamente
        # Precisamos aguardar o snapshot ficar pronto
        if isinstance(result, dict) and "snapshot_id" in result:
            snapshot_id = result.get("snapshot_id")
            logger.info("Snapshot triggered: %s", snapshot_id)

            # Aguarda snapshot ficar pronto (polling síncrono na própria Lambda)
            # A concorrência é controlada pela SQS FIFO com MessageGroupId único
            # que garante apenas uma Lambda processando por vez
            company_data = wait_for_snapshot_and_download(
                api_key=api_key,
                snapshot_id=snapshot_id,
                max_attempts=30,  # 30 x 10s = 5 minutos max
                wait_seconds=10,
            )

            if company_data is None:
                # Snapshot não ficou pronto a tempo
                logger.warning("Snapshot %s timeout - marcando como failed", snapshot_id)
                update_company_status(
                    table=table,
                    company_id=company_id,
                    company_url=company_url,
                    company_name=company_name,
                    status="failed",
                    refresh_days=config["refresh_days"],
                    error="Snapshot timeout after 5 minutes",
                )
                put_metric("CompanyFetchFailed", dimensions={"ErrorType": "timeout"})
                return {
                    "status": "timeout",
                    "company_id": company_id,
                    "snapshot_id": snapshot_id,
                }

            # Snapshot pronto - salva no S3
            s3_key = save_company_to_bronze(
                bucket=config["bronze_bucket"],
                company_id=company_id,
                data=company_data,
            )

            update_company_status(
                table=table,
                company_id=company_id,
                company_url=company_url,
                company_name=company_name,
                status="success",
                refresh_days=config["refresh_days"],
            )

            put_metric("CompanyFetchSuccess")
            return {
                "status": "success",
                "company_id": company_id,
                "snapshot_id": snapshot_id,
                "s3_key": s3_key,
            }

        # Se retornou dados diretamente (formato sincrono)
        if isinstance(result, list) and len(result) > 0:
            company_data = result[0]

            # Save to Bronze
            s3_key = save_company_to_bronze(
                bucket=config["bronze_bucket"],
                company_id=company_id,
                data=company_data,
            )

            # Update status
            update_company_status(
                table=table,
                company_id=company_id,
                company_url=company_url,
                company_name=company_name,
                status="success",
                refresh_days=config["refresh_days"],
            )

            put_metric("CompanyFetchSuccess")
            return {
                "status": "success",
                "company_id": company_id,
                "s3_key": s3_key,
            }

        # Resposta inesperada
        logger.warning("Resposta inesperada da Bright Data: %s", result)
        return {"status": "error", "reason": "unexpected_response", "company_id": company_id}

    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        logger.error("Erro ao buscar company %s: %s", company_id, error_msg)

        update_company_status(
            table=table,
            company_id=company_id,
            company_url=company_url,
            company_name=company_name,
            status="failed",
            refresh_days=config["refresh_days"],
            error=error_msg,
        )

        put_metric("CompanyFetchFailed", dimensions={"ErrorType": "http_error"})
        raise

    except Exception as e:
        error_msg = str(e)[:200]
        logger.error("Erro inesperado ao buscar company %s: %s", company_id, error_msg, exc_info=True)

        update_company_status(
            table=table,
            company_id=company_id,
            company_url=company_url,
            company_name=company_name,
            status="failed",
            refresh_days=config["refresh_days"],
            error=error_msg,
        )

        put_metric("CompanyFetchFailed", dimensions={"ErrorType": "unexpected"})
        raise


# =============================================================================
# Lambda Handler
# =============================================================================

def handler(event, context):
    """
    Lambda handler - SQS trigger.

    Processes batch of SQS messages containing company info to fetch.
    Uses partial batch response to handle individual failures.
    """
    logger.info("Evento recebido: %d records", len(event.get("Records", [])))

    config = get_config()
    api_key = get_brightdata_api_key()
    table = dynamodb.Table(config["companies_status_table"])

    batch_item_failures = []
    results = []

    for record in event.get("Records", []):
        message_id = record.get("messageId")

        try:
            body = json.loads(record.get("body", "{}"))
            result = process_company_message(body, config, api_key, table)
            results.append(result)
            logger.info("Processado: %s", result)

        except Exception as e:
            logger.error("Falha ao processar message %s: %s", message_id, e, exc_info=True)
            batch_item_failures.append({"itemIdentifier": message_id})

    # Summary
    success_count = len([r for r in results if r.get("status") in ("success", "triggered")])
    skipped_count = len([r for r in results if r.get("status") == "skipped"])
    failed_count = len(batch_item_failures)

    logger.info(
        "Resumo: %d success, %d skipped, %d failed",
        success_count, skipped_count, failed_count
    )

    # Return partial batch failure response
    return {"batchItemFailures": batch_item_failures}


# =============================================================================
# Local Testing
# =============================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    # Test event simulating SQS message
    test_event = {
        "Records": [
            {
                "messageId": "test-1",
                "body": json.dumps({
                    "company_id": "2209560",
                    "company_url": "https://www.linkedin.com/company/m3bi",
                    "company_name": "M3BI - A Zensar Company",
                    "source": "job_ingestion",
                    "first_seen_at": "2025-12-05T18:21:13Z",
                }),
            }
        ]
    }

    print(f"Running with event: {json.dumps(test_event, indent=2)}")
    result = handler(test_event, None)
    print(f"\nResult:\n{json.dumps(result, indent=2)}")
