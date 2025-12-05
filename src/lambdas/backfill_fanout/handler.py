"""
Lambda Backfill Fan-out - Envia múltiplas mensagens para a fila SQS

Lê a configuração de geo_ids e work_types do arquivo linkedin_geo_ids_flat.json
e envia uma mensagem para cada combinação location × work_type.
"""

import os
import json
from pathlib import Path

# Só inicializa boto3 se não for teste local
if __name__ != "__main__":
    import boto3
    sqs_client = boto3.client("sqs")

QUEUE_URL = os.environ.get("INGESTION_QUEUE_URL")

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


def handler(event, context):
    """
    Dispara mensagens para a fila de ingestão baseado em region_groups.

    Event format:
    {
        "region_groups": ["usa_states", "latin_america", "india"],
        "work_types_override": ["remote"],  # opcional - sobrescreve config do grupo
        "days": 30,  # opcional - filtro de tempo em dias (default: 30)
        "keywords": "data engineer",  # opcional
        "bronze_prefix_base": "linkedin/jobs-listing"  # opcional
    }

    Exemplos de days:
    - days: 1 → últimas 24 horas
    - days: 3 → últimos 3 dias
    - days: 7 → última semana
    - days: 30 → último mês (default)
    - days: 90 → últimos 3 meses

    Cada region_group é processado de acordo com sua configuração de work_types:
    - work_types: ["all"] → 1 chamada por location (f_WT=1,2,3)
    - work_types: ["on_site", "remote", "hybrid"] → 3 chamadas por location

    Se work_types_override for passado, usa esse valor em vez da config do grupo.
    Exemplo: {"region_groups": ["latin_america"], "work_types_override": ["remote"]}
    """
    if not QUEUE_URL:
        raise ValueError("INGESTION_QUEUE_URL environment variable not set")

    # Carrega configuração
    config = load_geo_config()

    # Lista de todos os region_groups disponíveis (exceto work_type_codes)
    all_region_groups = [k for k in config.keys() if k != "work_type_codes"]

    # Se não passar region_groups, usa todos
    region_groups = event.get("region_groups") or all_region_groups
    work_types_override = event.get("work_types_override")  # None = usa config do grupo
    days = event.get("days", DEFAULT_DAYS)  # Default: 30 dias
    time_filter = days * SECONDS_PER_DAY  # Converte dias para segundos
    keywords = event.get("keywords", "data engineer")
    bronze_prefix_base = event.get("bronze_prefix_base", "linkedin/jobs-listing")
    work_type_codes = config.get("work_type_codes", {})

    messages_sent = 0
    errors = []
    details = []

    for group_name in region_groups:
        group_config = config.get(group_name)

        if not group_config:
            errors.append(f"Region group not found: {group_name}")
            continue

        # Usa override se passado, senão usa config do grupo
        work_types = work_types_override if work_types_override else group_config.get("work_types", ["all"])
        locations = group_config.get("locations", [])

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
                    wt_suffix = ""
                else:
                    source_id = f"linkedin_{group_name}_{name_slug}_{work_type}_{geo_id}"
                    wt_suffix = f"/{work_type}"

                # Monta URL do LinkedIn
                url = LINKEDIN_URL_TEMPLATE.format(
                    geo_id=geo_id,
                    work_type_code=work_type_code,
                    time_filter=time_filter
                )

                if keywords != "data engineer":
                    url = url.replace("%22data%20engineer%22", keywords.replace(" ", "%20"))

                # Monta payload completo
                # Mantém estrutura bronze_prefix = "linkedin" para compatibilidade com Athena
                payload = {
                    **BASE_PAYLOAD,
                    "source_id": source_id,
                    "request_urls": [url],
                    "bronze_prefix": "linkedin"
                }

                try:
                    # Envia para SQS (sem MessageGroupId para filas standard)
                    send_params = {
                        "QueueUrl": QUEUE_URL,
                        "MessageBody": json.dumps(payload)
                    }

                    if ".fifo" in QUEUE_URL:
                        send_params["MessageGroupId"] = source_id

                    response = sqs_client.send_message(**send_params)

                    wt_label = f" [{work_type}]" if work_type != "all" else ""
                    print(f"✅ Sent: {name}{wt_label} → {response['MessageId'][:8]}")
                    messages_sent += 1
                    details.append({
                        "location": name,
                        "work_type": work_type,
                        "source_id": source_id
                    })

                except Exception as e:
                    error_msg = f"Failed to send message for {name} [{work_type}]: {str(e)}"
                    print(f"❌ {error_msg}")
                    errors.append(error_msg)

    # Calcula totais esperados (considera override se existir)
    total_expected = 0
    for g in region_groups:
        group_cfg = config.get(g)
        if group_cfg:
            locs = len(group_cfg.get("locations", []))
            wts = len(work_types_override) if work_types_override else len(group_cfg.get("work_types", []))
            total_expected += locs * wts

    # Agrupa detalhes por region_group para o resumo
    details_by_group = {}
    for d in details:
        group = d["source_id"].split("_")[1]  # linkedin_GROUP_name_...
        if group not in details_by_group:
            details_by_group[group] = []
        details_by_group[group].append(d)

    result = {
        "statusCode": 200,
        "messages_sent": messages_sent,
        "total_expected": total_expected,
        "region_groups": region_groups,
        "queue_url": QUEUE_URL,
        "summary_by_group": {g: len(msgs) for g, msgs in details_by_group.items()},
        "errors": errors
    }

    # Print resumo detalhado
    print(f"\n{'='*60}")
    print(f"📊 BACKFILL FAN-OUT SUMMARY")
    print(f"{'='*60}")
    print(f"🎯 Queue: {QUEUE_URL}")
    print(f"📅 Time filter: {days} days (f_TPR=r{time_filter})")
    print(f"📨 Messages sent: {messages_sent}/{total_expected}")
    print(f"\n📍 By Region Group:")
    for group, count in details_by_group.items():
        print(f"   • {group}: {len(count)} messages")

    if work_types_override:
        print(f"\n🔧 Work Types Override: {work_types_override}")

    if errors:
        print(f"\n⚠️  Errors ({len(errors)}):")
        for err in errors[:5]:  # Mostra só os 5 primeiros
            print(f"   • {err}")
        if len(errors) > 5:
            print(f"   ... and {len(errors) - 5} more")

    print(f"{'='*60}\n")

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill Fan-out - Envia mensagens para SQS")
    parser.add_argument("--send", action="store_true", help="Envia para AWS SQS (requer credenciais)")
    parser.add_argument("--region-groups", nargs="+", default=["latin_america"], help="Region groups para processar (ex: usa_states latin_america europe_countries)")
    parser.add_argument("--work-types", nargs="+", help="Override work_types (ex: remote on_site hybrid)")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"Filtro de tempo em dias (default: {DEFAULT_DAYS})")
    args = parser.parse_args()

    test_event = {
        "region_groups": args.region_groups,
        "days": args.days,
    }
    if args.work_types:
        test_event["work_types_override"] = args.work_types

    config = load_geo_config()
    work_types_override = test_event.get("work_types_override")

    if args.send:
        # Modo envio real para AWS
        import boto3
        from dotenv import load_dotenv
        load_dotenv()

        sqs_client = boto3.client("sqs", region_name="us-east-1")
        QUEUE_URL = os.environ.get("INGESTION_QUEUE_URL")

        if not QUEUE_URL:
            print("❌ INGESTION_QUEUE_URL não configurada. Defina no .env ou variável de ambiente.")
            exit(1)

        print(f"🚀 Sending to AWS SQS: {QUEUE_URL}\n")

        result = handler(test_event, None)
        print(f"\n✅ Resultado: {result}")
    else:
        # Modo dry-run (apenas mostra o que seria enviado)
        days = args.days
        time_filter = days * SECONDS_PER_DAY

        print("🧪 Test mode - showing what would be sent:")
        print("   (use --send para enviar de verdade)\n")
        print(f"📅 Time filter: {days} days (f_TPR=r{time_filter})")

        for group_name in test_event["region_groups"]:
            group_config = config.get(group_name, {})
            work_types = work_types_override if work_types_override else group_config.get("work_types", [])
            locations = group_config.get("locations", [])

            print(f"\n📍 {group_name}:")
            print(f"   work_types: {work_types}" + (" (override)" if work_types_override else ""))
            print(f"   locations: {len(locations)}")
            print(f"   total calls: {len(locations) * len(work_types)}")

            for loc in locations[:3]:  # Mostra só os 3 primeiros como exemplo
                for wt in work_types:
                    wt_code = config["work_type_codes"].get(wt, "1,2,3")
                    print(f"   → {loc['name']} [{wt}]: f_WT={wt_code}")

            if len(locations) > 3:
                print(f"   ... e mais {len(locations) - 3} locations")
