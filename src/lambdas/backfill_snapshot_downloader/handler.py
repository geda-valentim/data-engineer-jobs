"""
Lambda Backfill Snapshot Downloader

Lista snapshots "ready" do BrightData que ainda não foram baixados
e salva no S3 para backfill.

Usa o timestamp "created" do BrightData para particionamento S3.
"""

import os
import json
import logging
from functools import lru_cache
from typing import Optional

import boto3
import requests
import pendulum
from botocore.exceptions import ClientError

# Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Clients (inicializados no module level para reuso)
s3_client = boto3.client("s3")
s3_resource = boto3.resource("s3")
ssm_client = boto3.client("ssm")
cloudwatch = boto3.client("cloudwatch")

# Constants
LINKEDIN_DATASET_ID = "gd_lpfll7v5hcqtkxl6l"
BRIGHTDATA_SNAPSHOTS_URL = "https://api.brightdata.com/datasets/v3/snapshots"
BRIGHTDATA_SNAPSHOT_URL = "https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"


# =============================================================================
# Helpers - Credentials
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


def get_bronze_bucket_name() -> str:
    """Get bronze bucket name from environment."""
    bucket = os.getenv("BRONZE_BUCKET_NAME") or os.getenv("bronze_bucket_name")
    if not bucket:
        raise ValueError("BRONZE_BUCKET_NAME environment variable not set")
    return bucket


# =============================================================================
# Helpers - BrightData API
# =============================================================================

def list_brightdata_snapshots(api_key: str, params: dict) -> list[dict]:
    """
    Lista snapshots do BrightData API.

    Returns:
        List of snapshot metadata: [{ id, created, status, dataset_id, dataset_size }]
    """
    headers = {"Authorization": f"Bearer {api_key}"}

    query_params = {
        "dataset_id": LINKEDIN_DATASET_ID,
        "status": params.get("status", "ready"),
        "limit": min(params.get("limit", 1000), 5000),
    }

    if params.get("from_date"):
        query_params["from_date"] = params["from_date"]
    if params.get("to_date"):
        query_params["to_date"] = params["to_date"]

    logger.info("Listando snapshots com params: %s", query_params)

    response = requests.get(BRIGHTDATA_SNAPSHOTS_URL, headers=headers, params=query_params)
    response.raise_for_status()

    snapshots = response.json()
    logger.info("Encontrados %d snapshots no BrightData", len(snapshots))
    return snapshots


def download_snapshot(api_key: str, snapshot_id: str) -> tuple[bytes | None, str | None]:
    """
    Download snapshot content from BrightData.

    Returns:
        (content, error) - content se sucesso, error se falha (400, 404, etc.)
    """
    url = BRIGHTDATA_SNAPSHOT_URL.format(snapshot_id=snapshot_id)
    headers = {"Authorization": f"Bearer {api_key}"}

    logger.info("Baixando snapshot: %s", snapshot_id)
    response = requests.get(url, headers=headers)

    if response.status_code >= 400:
        # Snapshot indisponível (expirado, deletado, etc.) - ignorar
        return None, f"HTTP {response.status_code}"

    return response.content, None


# =============================================================================
# Helpers - S3
# =============================================================================

def parse_created_to_partitions(created: str) -> dict:
    """
    Parse BrightData's created timestamp to partition components.

    Input: "2025-12-04T14:30:00.000Z"
    Output: {"year": "2025", "month": "12", "day": "04", "hour": "14"}
    """
    dt = pendulum.parse(created)

    return {
        "year": f"{dt.year:04d}",
        "month": f"{dt.month:02d}",
        "day": f"{dt.day:02d}",
        "hour": f"{dt.hour:02d}",
    }


def build_s3_key(bronze_prefix: str, snapshot_id: str, file_format: str, date_parts: dict) -> str:
    """Build S3 key following existing pattern."""
    return (
        f"{bronze_prefix}/"
        f"year={date_parts['year']}/month={date_parts['month']}/"
        f"day={date_parts['day']}/hour={date_parts['hour']}/"
        f"bright-data-{snapshot_id}.{file_format}"
    )


def check_snapshot_exists(bucket: str, key: str) -> bool:
    """Check if a snapshot file exists at the expected S3 key."""
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        raise


# =============================================================================
# Helpers - Parse & Metrics
# =============================================================================

def parse_snapshot_content(raw_body: bytes, file_format: str) -> tuple[int, Optional[dict]]:
    """Parse snapshot to get record count and first item."""
    text = raw_body.decode("utf-8", errors="replace").strip()
    if not text:
        return 0, None

    try:
        if file_format == "jsonl":
            items = [json.loads(line) for line in text.splitlines() if line.strip()]
        elif file_format == "json":
            data = json.loads(text)
            items = data if isinstance(data, list) else [data]
        else:
            return 0, None

        return len(items), items[0] if items else None
    except Exception as e:
        logger.warning("Falha ao fazer parse do snapshot (%s): %s", file_format, e)
        return 0, None


def put_metric(name: str, value: float, dimensions: dict = None):
    """Send metric to CloudWatch."""
    dims = [{"Name": k, "Value": str(v)} for k, v in (dimensions or {}).items() if v]

    try:
        cloudwatch.put_metric_data(
            Namespace="LinkedInJobs",
            MetricData=[{
                "MetricName": name,
                "Value": value,
                "Unit": "Count",
                "Dimensions": dims,
            }],
        )
        logger.info("Metrica enviada: %s = %s", name, value)
    except Exception as e:
        logger.warning("Erro ao enviar metrica: %s", e)


# =============================================================================
# Lambda Handler
# =============================================================================

def handler(event, context):
    """
    Main Lambda handler.

    Event:
        dry_run: bool (default False) - se True, só lista sem baixar
        status: str (default "ready") - filtro de status BrightData
        from_date: str (opcional, YYYY-MM-DD) - data inicial
        to_date: str (opcional, YYYY-MM-DD) - data final
        limit: int (default 1000, max 5000) - limite de snapshots
        bronze_prefix: str (default "linkedin") - prefixo S3
        file_format: str (default "jsonl") - formato do arquivo

    Returns:
        {
            statusCode: 200,
            dry_run: bool,
            total_snapshots_found: int,
            already_downloaded: int,
            newly_downloaded: int,
            errors: list[str],
            downloaded_snapshots: list[dict],
            would_download: list[dict]  # apenas em dry_run
        }
    """
    logger.info("Evento recebido: %s", json.dumps(event))

    # Parse parameters
    dry_run = event.get("dry_run", False)
    status = event.get("status", "ready")
    from_date = event.get("from_date")
    to_date = event.get("to_date")
    limit = event.get("limit", 1000)
    bronze_prefix = event.get("bronze_prefix", "linkedin")
    file_format = event.get("file_format", "jsonl")

    # Get configuration
    api_key = get_brightdata_api_key()
    bucket = get_bronze_bucket_name()

    logger.info("Bucket: %s, Prefix: %s, DryRun: %s", bucket, bronze_prefix, dry_run)

    # List snapshots from BrightData
    snapshots = list_brightdata_snapshots(api_key, {
        "status": status,
        "from_date": from_date,
        "to_date": to_date,
        "limit": limit,
    })

    # Process each snapshot
    already_downloaded = []
    newly_downloaded = []
    skipped_unavailable = []
    errors = []

    for snapshot in snapshots:
        snapshot_id = snapshot.get("id")
        created = snapshot.get("created")
        dataset_size = snapshot.get("dataset_size", 0)

        if not snapshot_id or not created:
            errors.append(f"Snapshot sem id ou created: {snapshot}")
            continue

        try:
            # Parse created timestamp for partitioning
            date_parts = parse_created_to_partitions(created)
            s3_key = build_s3_key(bronze_prefix, snapshot_id, file_format, date_parts)

            # Check if already exists in S3
            if check_snapshot_exists(bucket, s3_key):
                already_downloaded.append(snapshot_id)
                logger.info("Ja existe no S3: %s", snapshot_id)
                continue

            if dry_run:
                newly_downloaded.append({
                    "snapshot_id": snapshot_id,
                    "s3_key": s3_key,
                    "would_download": True,
                    "created": created,
                    "dataset_size": dataset_size,
                })
                logger.info("[DRY RUN] Baixaria: %s -> %s", snapshot_id, s3_key)
            else:
                # Download snapshot
                content, download_error = download_snapshot(api_key, snapshot_id)

                if download_error:
                    # Snapshot indisponível (expirado, deletado, etc.) - pular silenciosamente
                    skipped_unavailable.append(snapshot_id)
                    logger.info("Snapshot indisponivel (%s): %s - pulando", download_error, snapshot_id)
                    continue

                record_count, first_item = parse_snapshot_content(content, file_format)

                s3_resource.Object(bucket, s3_key).put(Body=content)
                logger.info("Salvo: s3://%s/%s (%d records)", bucket, s3_key, record_count)

                # Send metric
                put_metric("BackfillJobCount", float(record_count), {
                    "BronzePrefix": bronze_prefix,
                    "Operation": "backfill",
                })

                newly_downloaded.append({
                    "snapshot_id": snapshot_id,
                    "s3_key": s3_key,
                    "record_count": record_count,
                    "created": created,
                    "content_length_bytes": len(content),
                })

        except Exception as e:
            error_msg = f"Erro processando {snapshot_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)

    # Build result
    result = {
        "statusCode": 200,
        "dry_run": dry_run,
        "total_snapshots_found": len(snapshots),
        "already_downloaded": len(already_downloaded),
        "skipped_unavailable": len(skipped_unavailable),
        "newly_downloaded": len(newly_downloaded),
        "errors": errors,
    }

    if dry_run:
        result["would_download"] = newly_downloaded
    else:
        result["downloaded_snapshots"] = newly_downloaded

    # Print summary
    print(f"\n{'='*60}")
    print(f"BACKFILL SNAPSHOT DOWNLOADER SUMMARY")
    print(f"{'='*60}")
    print(f"Mode: {'DRY RUN' if dry_run else 'DOWNLOAD'}")
    print(f"Bucket: {bucket}")
    print(f"Total snapshots found: {len(snapshots)}")
    print(f"Already in S3: {len(already_downloaded)}")
    print(f"Skipped (unavailable): {len(skipped_unavailable)}")
    print(f"{'Would download' if dry_run else 'Newly downloaded'}: {len(newly_downloaded)}")
    if errors:
        print(f"Errors: {len(errors)}")
    print(f"{'='*60}\n")

    logger.info("Resultado: %s", json.dumps(result, default=str))
    return result


# =============================================================================
# Local Testing
# =============================================================================

if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="Backfill Snapshot Downloader")
    parser.add_argument("--dry-run", action="store_true", help="Lista sem baixar")
    parser.add_argument("--from-date", type=str, help="Data inicial (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, help="Data final (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=1000, help="Limite de snapshots")
    parser.add_argument("--bronze-prefix", type=str, default="linkedin", help="Prefixo S3")
    args = parser.parse_args()

    test_event = {
        "dry_run": args.dry_run,
        "limit": args.limit,
        "bronze_prefix": args.bronze_prefix,
    }

    if args.from_date:
        test_event["from_date"] = args.from_date
    if args.to_date:
        test_event["to_date"] = args.to_date

    print(f"Running with event: {json.dumps(test_event, indent=2)}")
    result = handler(test_event, None)
    print(f"\nResult:\n{json.dumps(result, indent=2, default=str)}")
