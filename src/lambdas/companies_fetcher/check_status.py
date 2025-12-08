"""
Lambda Companies Check Status

Verifica o status de um snapshot de company no Bright Data.
Retorna READY quando pronto ou PENDING para continuar polling.
"""

import os
import json
import requests
import logging
from functools import lru_cache

import boto3

# Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Clients
ssm_client = boto3.client("ssm")

# Constants
MAX_ATTEMPTS = 20


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


def handler(event, context):
    """
    Lambda handler - Check snapshot status.

    Event:
        snapshot_id: str - ID do snapshot no Bright Data
        company_id: str - ID da empresa
        company_url: str - URL da empresa
        company_name: str - Nome da empresa
        attempts: int - Número de tentativas anteriores

    Returns:
        {
            snapshot_id: str,
            company_id: str,
            company_url: str,
            company_name: str,
            attempts: int,
            status: "READY" | "PENDING" | "TIMEOUT",
            provider_status: str
        }
    """
    logger.info("Evento recebido: %s", json.dumps(event))

    api_key = get_brightdata_api_key()

    # snapshot_id pode vir direto ou aninhado
    snapshot_id = event.get("snapshot_id")
    if isinstance(snapshot_id, dict):
        snapshot_id = snapshot_id.get("snapshot_id")

    if not snapshot_id:
        raise ValueError(f"snapshot_id não encontrado no event: {json.dumps(event)}")

    attempts = event.get("attempts", 0) + 1

    # Contexto base para retorno
    base_context = {
        "snapshot_id": snapshot_id,
        "company_id": event.get("company_id"),
        "company_url": event.get("company_url"),
        "company_name": event.get("company_name"),
        "attempts": attempts,
    }

    # Estourou número máximo de tentativas → TIMEOUT
    if attempts > MAX_ATTEMPTS:
        logger.warning("Timeout após %d tentativas para snapshot %s", attempts, snapshot_id)
        return {
            **base_context,
            "status": "TIMEOUT",
        }

    # Consulta status no Bright Data
    url = f"https://api.brightdata.com/datasets/v3/progress/{snapshot_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    logger.info("Verificando status do snapshot: %s", snapshot_id)

    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    logger.info("BrightData progress response: %s", data)

    # Normaliza status
    status_raw = (data.get("status") or "").lower()

    if status_raw == "ready":
        logger.info("Snapshot %s está pronto!", snapshot_id)
        return {
            **base_context,
            "status": "READY",
            "provider_status": status_raw,
        }

    # Ainda processando → volta pro loop da Step Function
    logger.info("Snapshot %s ainda em processamento: %s", snapshot_id, status_raw)
    return {
        **base_context,
        "status": "PENDING",
        "provider_status": status_raw,
    }


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    test_event = {
        "snapshot_id": "s_miwjgryf1gu5povbkx",
        "company_id": "2209560",
        "company_url": "https://www.linkedin.com/company/m3bi",
        "company_name": "M3BI",
        "attempts": 0,
    }

    print(handler(test_event, None))
