"""
Lambda Backfill Bronze to Silver - Processa múltiplas partições pendentes.

Uso:
  1. Processar range de datas:
     {"start_date": "2025-12-01", "end_date": "2025-12-15"}

  2. Processar partições específicas:
     {"partitions": ["2025/12/01/10", "2025/12/01/11"]}

  3. Auto-detectar partições pendentes (Bronze sem Silver):
     {"mode": "auto", "limit": 100}
"""

import os
import json
import time
import boto3
import awswrangler as wr
from datetime import datetime, timedelta
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# Importa o handler principal
from handler import (
    handler as process_partition,
    BRONZE_BUCKET,
    SILVER_BUCKET,
    SOURCE_SYSTEM,
    publish_metrics,
)

# Configuração
MAX_WORKERS = 5  # Processar 5 partições em paralelo
cloudwatch_client = boto3.client("cloudwatch")


def list_bronze_partitions(start_date: str = None, end_date: str = None) -> List[str]:
    """Lista todas as partições no Bronze."""
    prefix = f"s3://{BRONZE_BUCKET}/{SOURCE_SYSTEM}/"

    try:
        files = wr.s3.list_objects(prefix, suffix=".jsonl")
        if not files:
            files = wr.s3.list_objects(prefix, suffix=".json")
    except Exception as e:
        print(f"[backfill] Error listing Bronze: {e}")
        return []

    partitions = set()
    for f in files:
        # Extrai year=X/month=X/day=X/hour=X do path
        parts = f.split("/")
        partition_parts = [p for p in parts if p.startswith(("year=", "month=", "day=", "hour="))]
        if len(partition_parts) >= 4:
            # Converte para formato YYYY/MM/DD/HH
            vals = {p.split("=")[0]: p.split("=")[1] for p in partition_parts[:4]}
            partition = f"{vals['year']}/{vals['month']}/{vals['day']}/{vals['hour']}"

            # Filtrar por data se especificado
            if start_date or end_date:
                partition_date = f"{vals['year']}-{vals['month']}-{vals['day']}"
                if start_date and partition_date < start_date:
                    continue
                if end_date and partition_date > end_date:
                    continue

            partitions.add(partition)

    return sorted(partitions)


def list_silver_partitions() -> set:
    """Lista todas as partições existentes no Silver."""
    prefix = f"s3://{SILVER_BUCKET}/{SOURCE_SYSTEM}/"

    try:
        files = wr.s3.list_objects(prefix, suffix=".parquet")
    except Exception:
        return set()

    partitions = set()
    for f in files:
        parts = f.split("/")
        partition_parts = [p for p in parts if p.startswith(("year=", "month=", "day=", "hour="))]
        if len(partition_parts) >= 4:
            vals = {p.split("=")[0]: p.split("=")[1] for p in partition_parts[:4]}
            partition = f"{vals['year']}/{vals['month']}/{vals['day']}/{vals['hour']}"
            partitions.add(partition)

    return partitions


def find_missing_partitions(limit: int = 100) -> List[str]:
    """Encontra partições no Bronze que não existem no Silver."""
    print("[backfill] Scanning Bronze partitions...")
    bronze_partitions = set(list_bronze_partitions())
    print(f"[backfill] Found {len(bronze_partitions)} partitions in Bronze")

    print("[backfill] Scanning Silver partitions...")
    silver_partitions = list_silver_partitions()
    print(f"[backfill] Found {len(silver_partitions)} partitions in Silver")

    missing = bronze_partitions - silver_partitions
    print(f"[backfill] Found {len(missing)} missing partitions")

    return sorted(missing)[:limit]


def generate_date_range_partitions(start_date: str, end_date: str) -> List[str]:
    """Gera lista de partições para um range de datas (todas as horas)."""
    partitions = []
    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    while current <= end:
        for hour in range(24):
            partition = f"{current.year}/{current.month:02d}/{current.day:02d}/{hour:02d}"
            partitions.append(partition)
        current += timedelta(days=1)

    return partitions


def process_single_partition(partition: str) -> Dict[str, Any]:
    """Processa uma única partição."""
    parts = partition.split("/")
    event = {
        "year": parts[0],
        "month": parts[1],
        "day": parts[2],
        "hour": parts[3],
    }

    try:
        result = process_partition(event, None)
        return {
            "partition": partition,
            "status": result.get("status", "unknown"),
            "records": result.get("records_processed", 0),
            "duration_ms": result.get("duration_ms", 0),
        }
    except Exception as e:
        return {
            "partition": partition,
            "status": "error",
            "error": str(e),
            "records": 0,
        }


def handler(event, context):
    """
    Handler principal do backfill.

    Modos:
    1. {"start_date": "2025-12-01", "end_date": "2025-12-15"}
    2. {"partitions": ["2025/12/01/10", "2025/12/01/11"]}
    3. {"mode": "auto", "limit": 100}
    """
    start_time = time.time()

    mode = event.get("mode", "manual")
    partitions = []

    # Determinar partições a processar
    if "partitions" in event:
        partitions = event["partitions"]
        print(f"[backfill] Processing {len(partitions)} specified partitions")

    elif "start_date" in event and "end_date" in event:
        # Gerar partições para o range E verificar quais existem no Bronze
        all_partitions = generate_date_range_partitions(
            event["start_date"],
            event["end_date"]
        )
        bronze_partitions = set(list_bronze_partitions(
            event["start_date"],
            event["end_date"]
        ))
        partitions = [p for p in all_partitions if p in bronze_partitions]
        print(f"[backfill] Found {len(partitions)} partitions in date range with data")

    elif mode == "auto":
        limit = event.get("limit", 100)
        partitions = find_missing_partitions(limit)
        print(f"[backfill] Auto-detected {len(partitions)} missing partitions")

    else:
        return {
            "status": "error",
            "message": "Invalid event. Use 'partitions', 'start_date/end_date', or 'mode=auto'",
        }

    if not partitions:
        return {
            "status": "no_work",
            "message": "No partitions to process",
            "total": 0,
        }

    # Processar partições em paralelo
    results = []
    success_count = 0
    error_count = 0
    total_records = 0

    print(f"[backfill] Starting parallel processing with {MAX_WORKERS} workers...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_single_partition, p): p
            for p in partitions
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

            if result["status"] == "success":
                success_count += 1
                total_records += result["records"]
            elif result["status"] in ("no_data", "no_valid_data"):
                pass  # Não é erro, apenas sem dados
            else:
                error_count += 1

            print(f"[backfill] {result['partition']}: {result['status']} ({result['records']} records)")

    duration_ms = (time.time() - start_time) * 1000

    # Publicar métricas agregadas
    try:
        cloudwatch_client.put_metric_data(
            Namespace="DataEngineerJobs/ETL",
            MetricData=[
                {
                    "MetricName": "BackfillPartitionsProcessed",
                    "Value": len(partitions),
                    "Unit": "Count",
                    "Dimensions": [{"Name": "Job", "Value": "bronze_to_silver_backfill"}],
                },
                {
                    "MetricName": "BackfillRecordsProcessed",
                    "Value": total_records,
                    "Unit": "Count",
                    "Dimensions": [{"Name": "Job", "Value": "bronze_to_silver_backfill"}],
                },
                {
                    "MetricName": "BackfillDurationMs",
                    "Value": duration_ms,
                    "Unit": "Milliseconds",
                    "Dimensions": [{"Name": "Job", "Value": "bronze_to_silver_backfill"}],
                },
            ],
        )
    except Exception as e:
        print(f"[backfill] Warning: Failed to publish metrics: {e}")

    summary = {
        "status": "completed",
        "total_partitions": len(partitions),
        "success": success_count,
        "errors": error_count,
        "no_data": len(partitions) - success_count - error_count,
        "total_records": total_records,
        "duration_ms": round(duration_ms, 2),
        "results": results if len(results) <= 50 else results[:50],  # Limitar output
    }

    print(f"[backfill] Completed: {success_count} success, {error_count} errors, {total_records} records in {duration_ms:.0f}ms")

    return summary
