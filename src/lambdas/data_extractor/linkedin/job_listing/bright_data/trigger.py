import os
import json
import requests
import shared

BRIGHTDATA_TRIGGER_URL = "https://api.brightdata.com/datasets/v3/trigger"


def fetch_data_bright_jobs(event, context):
    """
    Event esperado (exemplo):

    {
      "source_id": "linkedin_br_nacional",
      "source_type": "jobs_listing",
      "provider": "brightdata",
      "dataset_kind": "snapshot",
      "brightdata_dataset_id": "gd_lpfll7v5hcqtkxl6l",
      "brightdata_extra_params": {
        "include_errors": "true",
        "type": "discover_new",
        "discover_by": "url"
      },
      "request_urls": [
        "https://www.linkedin.com/jobs/search/?..."
      ],
      "domain": "linkedin",
      "entity": "jobs",
      "bronze_prefix": "linkedin/jobs-listing/br/national",
      "file_format": "jsonl"
    }
    """

    api_key = shared.get_brightdata_api_key()

    source_id   = event.get("source_id")
    dataset_id  = event.get("brightdata_dataset_id")
    extra_params = event.get("brightdata_extra_params", {}) or {}
    request_urls = event.get("request_urls", []) or []

    if not dataset_id:
        raise ValueError(f"brightdata_dataset_id não informado no event: {json.dumps(event)}")

    if not request_urls:
        # você pode decidir se isso é erro ou só logar aviso
        raise ValueError("Nenhuma URL em request_urls para disparar coleta no Bright Data.")

    # Monta params: dataset_id + extras
    params = {
        "dataset_id": dataset_id,
        **extra_params,
    }

    # Bright Data espera uma lista de objetos {"url": "..."}
    data = [{"url": url} for url in request_urls]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(
        BRIGHTDATA_TRIGGER_URL,
        headers=headers,
        params=params,
        json=data,
    )
    resp.raise_for_status()
    body = resp.json()

    # Bright Data costuma devolver algo como {"snapshot_id": "...", ...}
    snapshot_id = body.get("snapshot_id")
    if not snapshot_id:
        raise RuntimeError(f"Resposta do Bright Data sem snapshot_id: {body}")

    print("✅ Trigger Bright Data OK:", {
        "source_id": source_id,
        "dataset_id": dataset_id,
        "snapshot_id": snapshot_id,
    })

    # O que volta vira estado da Step Function
    return {
        "status": "TRIGGERED",
        "source_id": source_id,
        "dataset_id": dataset_id,
        "snapshot_id": snapshot_id,

        # repassa config importante pro resto da SFN
        "domain": event.get("domain"),
        "entity": event.get("entity"),
        "bronze_prefix": event.get("bronze_prefix"),
        "file_format": event.get("file_format", "jsonl"),
    }


if __name__ == "__main__":
    # teste local
    from dotenv import load_dotenv
    load_dotenv()

    test_event = {
        "source_id": "linkedin_br_nacional",
        "brightdata_dataset_id": "gd_lpfll7v5hcqtkxl6l",
        "brightdata_extra_params": {
            "include_errors": "true",
            "type": "discover_new",
            "discover_by": "url"
        },
        "request_urls": [
            "https://www.linkedin.com/jobs/search/?currentJobId=4341321856&f_TPR=r86400&geoId=92000000&keywords=%22engenheiro%20de%20dados%22&origin=JOB_SEARCH_PAGE_JOB_FILTER&refresh=true&sortBy=DD"
        ],
        "domain": "linkedin",
        "entity": "jobs",
        "bronze_prefix": "linkedin/jobs-listing/br/national",
        "file_format": "jsonl"
    }

    print(fetch_data_bright_jobs(test_event, None))
