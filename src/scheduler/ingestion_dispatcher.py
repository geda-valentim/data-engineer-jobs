# src/scheduler/ingestion_dispatcher.py

import os
import json
import boto3
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource("dynamodb")
sfn = boto3.client("stepfunctions")

TABLE_NAME = os.getenv("INGESTION_SOURCES_TABLE_NAME")
STATE_MACHINE_ARN = os.getenv("STATE_MACHINE_ARN")


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
    if not TABLE_NAME or not STATE_MACHINE_ARN:
        raise RuntimeError(
            f"Env vars faltando. TABLE_NAME={TABLE_NAME}, STATE_MACHINE_ARN={STATE_MACHINE_ARN}"
        )

    table = dynamodb.Table(TABLE_NAME)

    # Por enquanto: scan + filter enabled = true
    # (se a tabela crescer muito, depois dá pra trocar por GSI / queries)
    resp = table.scan(
        FilterExpression=Attr("enabled").eq(True)
    )

    items = resp.get("Items", [])
    started = 0

    for src in items:
        sfn_input = _build_input_from_source(src)

        # Você pode customizar o name, mas deixa o AWS gerar se não quiser conflito
        sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            input=json.dumps(sfn_input),
        )
        started += 1

        print(f"Started execution for source_id={src['source_id']}")

    return {
        "started_executions": started,
        "sources_found": len(items),
        "state_machine": STATE_MACHINE_ARN,
    }


if __name__ == "__main__":
    # Teste local (usando AWS cred local)
    from dotenv import load_dotenv

    load_dotenv()

    fake_event = {}
    print(handler(fake_event, None))
