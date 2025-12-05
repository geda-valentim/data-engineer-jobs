"""
Lambda SQS Consumer - Consome mensagens da fila e inicia Step Function

Recebe mensagens do SQS com payload de ingestão e dispara a Step Function.
O throttling é controlado pela reserved concurrency da Lambda (5).
"""

import os
import json
import boto3

sfn_client = boto3.client("stepfunctions")

STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN")


def handler(event, context):
    """
    Processa mensagens do SQS e inicia Step Function para cada uma.

    Event format (SQS):
    {
        "Records": [
            {
                "messageId": "...",
                "body": "{...json payload...}",
                ...
            }
        ]
    }
    """
    if not STATE_MACHINE_ARN:
        raise ValueError("STATE_MACHINE_ARN environment variable not set")

    results = []

    for record in event.get("Records", []):
        message_id = record.get("messageId")

        try:
            # Parse do payload da mensagem
            payload = json.loads(record.get("body", "{}"))

            # Gera nome único para a execução
            source_id = payload.get("source_id", "unknown")
            execution_name = f"{source_id}-{message_id[:8]}"

            # Inicia Step Function
            response = sfn_client.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                name=execution_name,
                input=json.dumps(payload)
            )

            print(f"✅ Started execution: {execution_name}")
            print(f"   Execution ARN: {response['executionArn']}")

            results.append({
                "messageId": message_id,
                "status": "SUCCESS",
                "executionArn": response["executionArn"]
            })

        except Exception as e:
            print(f"❌ Error processing message {message_id}: {str(e)}")
            # Re-raise para que a mensagem volte para a fila
            raise

    return {
        "statusCode": 200,
        "processed": len(results),
        "results": results
    }


if __name__ == "__main__":
    # Teste local
    test_event = {
        "Records": [
            {
                "messageId": "test-123",
                "body": json.dumps({
                    "source_id": "linkedin_us_california",
                    "brightdata_dataset_id": "gd_lpfll7v5hcqtkxl6l",
                    "request_urls": [
                        "https://www.linkedin.com/jobs/search/?geoId=102095887&keywords=data%20engineer"
                    ],
                    "domain": "linkedin",
                    "entity": "jobs",
                    "bronze_prefix": "linkedin/jobs-listing/us/california",
                    "file_format": "jsonl"
                })
            }
        ]
    }
    print(json.dumps(test_event, indent=2))
