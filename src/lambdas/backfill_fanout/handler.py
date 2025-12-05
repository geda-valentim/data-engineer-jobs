"""
Lambda Backfill Fan-out - Gera payloads e inicia Step Function orquestradora

Lê a configuração de geo_ids e work_types do arquivo linkedin_geo_ids_flat.json,
gera os payloads para cada combinação location × work_type, salva no S3 e
inicia a Step Function orquestradora com Distributed Map.
"""

import os
import json
from pathlib import Path
from datetime import datetime

# Só inicializa boto3 se não for teste local
if __name__ != "__main__":
    import boto3
    s3_client = boto3.client("s3")
    sfn_client = boto3.client("stepfunctions")

BACKFILL_BUCKET = os.environ.get("BACKFILL_BUCKET")
ORCHESTRATOR_STATE_MACHINE_ARN = os.environ.get("ORCHESTRATOR_STATE_MACHINE_ARN")

# Carrega configuração de geo_ids
# No Lambda: /var/task/data_extractor/linkedin/config/linkedin_geo_ids_flat.json
# Local: resolve relativo ao handler.py
if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    # Running in Lambda - arquivo está no mesmo zip
    CONFIG_PATH = Path("/var/task/data_extractor/linkedin/config/linkedin_geo_ids_flat.json")
else:
    # Running locally
    CONFIG_PATH = Path(__file__).parent.parent / "data_extractor/linkedin/config/linkedin_geo_ids_flat.json"

# Template base para mensagens de ingestão LinkedIn
BASE_PAYLOAD = {
    "source_type": "jobs_listing",
    "provider": "brightdata",
    "dataset_kind": "snapshot",
    "brightdata_dataset_id": "gd_lpfll7v5hcqtkxl6l",
    "brightdata_extra_params": {
        "include_errors": "true",
        "type": "discover_new",
        "discover_by": "url"
    },
    "domain": "linkedin",
    "entity": "jobs",
    "file_format": "jsonl"
}

# URL template do LinkedIn com work_type
# f_TPR=rXXXXX onde XXXXX = segundos (ex: r86400 = 24h, r2592000 = 30 dias)
# f_WT=1 (on_site), f_WT=2 (remote), f_WT=3 (hybrid), f_WT=1,2,3 (all)
LINKEDIN_URL_TEMPLATE = (
    "https://www.linkedin.com/jobs/search/?"
    "f_TPR=r{time_filter}&f_WT={work_type_code}&geoId={geo_id}"
    "&keywords=%22data%20engineer%22&origin=JOB_SEARCH_PAGE_JOB_FILTER"
    "&refresh=true&sortBy=DD"
)

# Segundos por dia para cálculo do filtro de tempo
SECONDS_PER_DAY = 86400
DEFAULT_DAYS = 30


def load_geo_config():
    """Carrega a configuração de geo_ids do arquivo JSON."""
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def get_work_type_code(work_type: str, config: dict) -> str:
    """Retorna o código do LinkedIn para o work_type."""
    codes = config.get("work_type_codes", {})
    return codes.get(work_type, "1,2,3")  # default: all


def generate_payloads(event: dict) -> tuple[list[dict], list[str], dict]:
    """
    Gera lista de payloads baseado nos parâmetros do evento.

    Returns:
        tuple: (payloads, errors, details_by_group)
    """
    config = load_geo_config()

    # Lista de todos os region_groups disponíveis (exceto work_type_codes)
    all_region_groups = [k for k in config.keys() if k != "work_type_codes"]

    # Parâmetros do evento
    region_groups = event.get("region_groups") or all_region_groups
    work_types_override = event.get("work_types_override")
    days = event.get("days", DEFAULT_DAYS)
    time_filter = days * SECONDS_PER_DAY
    keywords = event.get("keywords", "data engineer")
    work_type_codes = config.get("work_type_codes", {})

    payloads = []
    errors = []
    details_by_group = {}

    for group_name in region_groups:
        group_config = config.get(group_name)

        if not group_config:
            errors.append(f"Region group not found: {group_name}")
            continue

        work_types = work_types_override if work_types_override else group_config.get("work_types", ["all"])
        locations = group_config.get("locations", [])

        if group_name not in details_by_group:
            details_by_group[group_name] = 0

        print(f"📍 Processing {group_name}: {len(locations)} locations × {len(work_types)} work_types")

        for location in locations:
            geo_id = location.get("id")
            name = location.get("name", "unknown")

            if not geo_id:
                errors.append(f"Missing id for location: {name}")
                continue

            for work_type in work_types:
                work_type_code = work_type_codes.get(work_type, "1,2,3")

                # Monta source_id único incluindo work_type
                name_slug = name.lower().replace(" ", "-").replace(",", "")
                if work_type == "all":
                    source_id = f"linkedin_{group_name}_{name_slug}_{geo_id}"
                else:
                    source_id = f"linkedin_{group_name}_{name_slug}_{work_type}_{geo_id}"

                # Monta URL do LinkedIn
                url = LINKEDIN_URL_TEMPLATE.format(
                    geo_id=geo_id,
                    work_type_code=work_type_code,
                    time_filter=time_filter
                )

                if keywords != "data engineer":
                    url = url.replace("%22data%20engineer%22", keywords.replace(" ", "%20"))

                # Monta payload completo
                payload = {
                    **BASE_PAYLOAD,
                    "source_id": source_id,
                    "request_urls": [url],
                    "bronze_prefix": "linkedin"
                }

                payloads.append(payload)
                details_by_group[group_name] += 1

    return payloads, errors, details_by_group


def handler(event, context):
    """
    Gera payloads, salva no S3 e inicia Step Function orquestradora.

    Event format:
    {
        "region_groups": ["usa_states", "latin_america", "india"],
        "work_types_override": ["remote"],  # opcional - sobrescreve config do grupo
        "days": 30,  # opcional - filtro de tempo em dias (default: 30)
        "keywords": "data engineer"  # opcional
    }

    Exemplos de days:
    - days: 1 → últimas 24 horas
    - days: 3 → últimos 3 dias
    - days: 7 → última semana
    - days: 30 → último mês (default)
    - days: 90 → últimos 3 meses
    """
    if not BACKFILL_BUCKET:
        raise ValueError("BACKFILL_BUCKET environment variable not set")
    if not ORCHESTRATOR_STATE_MACHINE_ARN:
        raise ValueError("ORCHESTRATOR_STATE_MACHINE_ARN environment variable not set")

    # Gera todos os payloads
    payloads, errors, details_by_group = generate_payloads(event)

    if not payloads:
        return {
            "statusCode": 400,
            "message": "No payloads generated",
            "errors": errors
        }

    # Gera path único no S3
    timestamp = datetime.utcnow().strftime("%Y/%m/%d/%H%M%S")
    s3_key = f"backfill-manifests/{timestamp}/manifest.json"

    # Salva payloads no S3
    manifest = {
        "created_at": datetime.utcnow().isoformat(),
        "total_items": len(payloads),
        "region_groups": list(details_by_group.keys()),
        "items": payloads
    }

    s3_client.put_object(
        Bucket=BACKFILL_BUCKET,
        Key=s3_key,
        Body=json.dumps(manifest),
        ContentType="application/json"
    )

    print(f"✅ Manifest saved to s3://{BACKFILL_BUCKET}/{s3_key}")
    print(f"   Total items: {len(payloads)}")

    # Inicia Step Function orquestradora
    execution_name = f"backfill-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

    sfn_input = {
        "manifest_bucket": BACKFILL_BUCKET,
        "manifest_key": s3_key,
        "total_items": len(payloads)
    }

    response = sfn_client.start_execution(
        stateMachineArn=ORCHESTRATOR_STATE_MACHINE_ARN,
        name=execution_name,
        input=json.dumps(sfn_input)
    )

    print(f"✅ Started orchestrator: {execution_name}")
    print(f"   Execution ARN: {response['executionArn']}")

    # Print resumo
    print(f"\n{'='*60}")
    print(f"📊 BACKFILL FAN-OUT SUMMARY")
    print(f"{'='*60}")
    print(f"📦 Manifest: s3://{BACKFILL_BUCKET}/{s3_key}")
    print(f"📨 Total payloads: {len(payloads)}")
    print(f"\n📍 By Region Group:")
    for group, count in details_by_group.items():
        print(f"   • {group}: {count} items")

    if errors:
        print(f"\n⚠️  Errors ({len(errors)}):")
        for err in errors[:5]:
            print(f"   • {err}")
        if len(errors) > 5:
            print(f"   ... and {len(errors) - 5} more")

    print(f"{'='*60}\n")

    return {
        "statusCode": 200,
        "execution_arn": response["executionArn"],
        "execution_name": execution_name,
        "manifest_bucket": BACKFILL_BUCKET,
        "manifest_key": s3_key,
        "total_items": len(payloads),
        "summary_by_group": details_by_group,
        "errors": errors
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill Fan-out - Gera payloads para Step Function")
    parser.add_argument("--send", action="store_true", help="Envia para AWS (requer credenciais)")
    parser.add_argument("--region-groups", nargs="+", default=["latin_america"], help="Region groups para processar")
    parser.add_argument("--work-types", nargs="+", help="Override work_types (ex: remote on_site hybrid)")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"Filtro de tempo em dias (default: {DEFAULT_DAYS})")
    args = parser.parse_args()

    test_event = {
        "region_groups": args.region_groups,
        "days": args.days,
    }
    if args.work_types:
        test_event["work_types_override"] = args.work_types

    if args.send:
        # Modo envio real para AWS
        import boto3
        from dotenv import load_dotenv
        load_dotenv()

        s3_client = boto3.client("s3", region_name="us-east-1")
        sfn_client = boto3.client("stepfunctions", region_name="us-east-1")
        BACKFILL_BUCKET = os.environ.get("BACKFILL_BUCKET")
        ORCHESTRATOR_STATE_MACHINE_ARN = os.environ.get("ORCHESTRATOR_STATE_MACHINE_ARN")

        if not BACKFILL_BUCKET or not ORCHESTRATOR_STATE_MACHINE_ARN:
            print("❌ BACKFILL_BUCKET e ORCHESTRATOR_STATE_MACHINE_ARN são necessários.")
            print("   Defina no .env ou variável de ambiente.")
            exit(1)

        print(f"🚀 Sending to AWS...")
        print(f"   Bucket: {BACKFILL_BUCKET}")
        print(f"   State Machine: {ORCHESTRATOR_STATE_MACHINE_ARN}\n")

        result = handler(test_event, None)
        print(f"\n✅ Resultado: {json.dumps(result, indent=2)}")
    else:
        # Modo dry-run (apenas mostra o que seria gerado)
        print("🧪 Test mode - showing what would be generated:")
        print("   (use --send para enviar de verdade)\n")

        payloads, errors, details_by_group = generate_payloads(test_event)

        print(f"\n📊 Summary:")
        print(f"   Total payloads: {len(payloads)}")
        for group, count in details_by_group.items():
            print(f"   • {group}: {count} items")

        if payloads:
            print(f"\n📋 Sample payloads (first 3):")
            for p in payloads[:3]:
                print(f"   • {p['source_id']}")
