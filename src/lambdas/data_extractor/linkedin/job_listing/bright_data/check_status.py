import os
import json
import requests
import shared

MAX_ATTEMPTS = 20  # limite lógico de tentativas


def _carry_context(event: dict) -> dict:
    """
    Carrega pro próximo step todos os campos de contexto
    que o restante do fluxo precisa.
    """
    context_fields = [
        "source_id",
        "source_type",
        "dataset_id",
        "provider",
        "dataset_kind",
        "domain",
        "entity",
        "bronze_prefix",
        "file_format",
    ]

    return {k: event.get(k) for k in context_fields if k in event}


def get_snapshot_status(event, context):
    api_key = shared.get_brightdata_api_key()

    # snapshot_id pode vir direto ou aninhado
    snapshot_id = event.get("snapshot_id")
    if isinstance(snapshot_id, dict):
        snapshot_id = snapshot_id.get("snapshot_id")

    if not snapshot_id:
        raise ValueError(f"snapshot_id não encontrado no event: {json.dumps(event)}")

    attempts = event.get("attempts", 0) + 1

    # sempre carrega o contexto base pra frente
    base_context = {
        "snapshot_id": snapshot_id,
        "attempts": attempts,
    }
    base_context.update(_carry_context(event))

    # estourou número máximo de tentativas → TIMEOUT
    if attempts > MAX_ATTEMPTS:
        return {
            **base_context,
            "status": "TIMEOUT",
        }

    url = f"https://api.brightdata.com/datasets/v3/progress/{snapshot_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    print("BrightData progress response:", data)

    # pega status bruto e normaliza
    status_raw = (data.get("status") or "").lower()

    if status_raw == "ready":
        # pronto pra salvar no S3
        return {
            **base_context,
            "status": "READY",           # <-- o que a SFN espera
            "provider_status": status_raw,
        }

    # ainda processando → volta pro loop da Step Function
    return {
        **base_context,
        "status": "PENDING",
        "provider_status": status_raw,
    }


if __name__ == "__main__":
    # Snaps de Teste
    # SUCCESS: sd_mip9cq3kfqddga6h6
    # FAIL:    sd_mihswhkw2kcn0r2qmn
    event = {
        "snapshot_id": "sd_mio2zhxw147a5lamxl",
        "attempts": 0,
        "source_id": "linkedin_brightdata_jobs",
        "domain": "linkedin",
        "entity": "jobs",
        "bronze_prefix": "linkedin/jobs-listing/br/national",
        "file_format": "jsonl",
    }
    context = {}

    print(get_snapshot_status(event, context))
