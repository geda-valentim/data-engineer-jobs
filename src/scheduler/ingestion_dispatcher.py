# src/scheduler/ingestion_dispatcher.py

import os
import json
import boto3
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")

TABLE_NAME = os.getenv("INGESTION_SOURCES_TABLE_NAME")
INGESTION_QUEUE_URL = os.getenv("INGESTION_QUEUE_URL")


def _build_input_from_source(source_item: dict) -> dict:
    """
    Constrói o input da Step Function a partir de um item do DynamoDB.
    Espera o mesmo formato que você usou no JSON de seed.
    """

    return {
        "source_id": source_item["source_id"],
        "source_type": source_item["source_type"],

        "provider": source_item["provider"],
        "dataset_kind": source_item["dataset_kind"],

        "domain": source_item["domain"],
        "entity": source_item["entity"],

        "brightdata_dataset_id": source_item["brightdata_dataset_id"],
        "brightdata_extra_params": source_item.get("brightdata_extra_params", {}),
        "request_urls": source_item.get("request_urls", []),

        "request_url": source_item.get("request_url"),

        "bronze_prefix": source_item["bronze_prefix"],
        "file_format": source_item.get("file_format", "jsonl"),
    }


def handler(event, context):
    if not TABLE_NAME or not INGESTION_QUEUE_URL:
        raise RuntimeError(
            f"Env vars faltando. TABLE_NAME={TABLE_NAME}, INGESTION_QUEUE_URL={INGESTION_QUEUE_URL}"
        )

    table = dynamodb.Table(TABLE_NAME)

    # Por enquanto: scan + filter enabled = true
    # (se a tabela crescer muito, depois dá pra trocar por GSI / queries)
    resp = table.scan(
        FilterExpression=Attr("enabled").eq(True)
    )

    items = resp.get("Items", [])
    queued = 0

    for src in items:
        message_body = _build_input_from_source(src)

        sqs.send_message(
            QueueUrl=INGESTION_QUEUE_URL,
            MessageBody=json.dumps(message_body),
        )
        queued += 1

        print(f"Queued message for source_id={src['source_id']}")

    return {
        "queued_messages": queued,
        "sources_found": len(items),
        "queue_url": INGESTION_QUEUE_URL,
    }


if __name__ == "__main__":
    # Teste local (usando AWS cred local)
    from dotenv import load_dotenv

    load_dotenv()

    fake_event = {}
    print(handler(fake_event, None))
