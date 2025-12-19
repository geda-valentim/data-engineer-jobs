#!/usr/bin/env python3
"""
Teste local do Lambda bronze_to_silver ETL.

Uso:
    # Com dados do S3 (requer AWS credentials)
    python scripts/test_lambda_etl_local.py --year 2025 --month 12 --day 15 --hour 10

    # Com arquivo local
    python scripts/test_lambda_etl_local.py --local-file data/sample_bronze.json

    # Dry-run (não escreve no Silver)
    python scripts/test_lambda_etl_local.py --year 2025 --month 12 --day 15 --hour 10 --dry-run
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Adiciona o diretório src ao path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src/lambdas/bronze_to_silver"))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Configura variáveis de ambiente antes de importar o handler
os.environ.setdefault("BRONZE_BUCKET", "data-engineer-jobs-bronze")
os.environ.setdefault("SILVER_BUCKET", "data-engineer-jobs-silver")
os.environ.setdefault("SOURCE_SYSTEM", "linkedin")

import pandas as pd


def test_with_s3(year: str, month: str, day: str, hour: str, dry_run: bool = False):
    """Testa com dados reais do S3."""
    print(f"\n{'='*60}")
    print(f"Testing Lambda ETL: {year}/{month}/{day}/{hour}")
    print(f"Dry-run: {dry_run}")
    print(f"{'='*60}\n")

    # Import handler
    from handler import handler, transform_bronze_to_silver, apply_skills_detection

    if dry_run:
        # Em dry-run, apenas lê e transforma sem escrever
        import awswrangler as wr

        bronze_bucket = os.environ["BRONZE_BUCKET"]
        bronze_path = f"s3://{bronze_bucket}/linkedin/year={year}/month={month}/day={day}/hour={hour}/"

        print(f"Reading from: {bronze_path}")

        try:
            # Tenta .jsonl primeiro (formato do Bright Data), depois .json
            try:
                df = wr.s3.read_json(path=bronze_path, path_suffix=".jsonl", lines=True)
            except wr.exceptions.NoFilesFound:
                df = wr.s3.read_json(path=bronze_path, path_suffix=".json")
        except wr.exceptions.NoFilesFound:
            print(f"No files found in partition {year}/{month}/{day}/{hour}")
            print("\nTry listing available partitions with: make test-etl-list")
            return
        except Exception as e:
            print(f"Error reading from S3: {e}")
            raise

        print(f"Read {len(df)} records")

        if not df.empty and "job_posting_id" in df.columns:
            df = df[df["job_posting_id"].notna()]
            print(f"After filtering: {len(df)} valid records")

            df = transform_bronze_to_silver(df, year, month, day, hour)
            print(f"After transform: {len(df)} records")

            df = apply_skills_detection(df)
            print(f"After skills detection: {len(df)} records")

            print("\nSample output:")
            cols = [c for c in ["job_posting_id", "job_title", "skills_canonical"] if c in df.columns]
            print(df[cols].head(3).to_string())

            print(f"\nDry-run complete. Would write {len(df)} records to Silver.")
        else:
            print("No valid data found")

    else:
        # Executa o handler completo
        event = {
            "year": year,
            "month": month,
            "day": day,
            "hour": hour,
        }
        result = handler(event, None)
        print(f"\nResult: {json.dumps(result, indent=2)}")


def test_with_local_file(file_path: str):
    """Testa com arquivo JSON local."""
    print(f"\n{'='*60}")
    print(f"Testing with local file: {file_path}")
    print(f"{'='*60}\n")

    from handler import transform_bronze_to_silver, apply_skills_detection, SILVER_COLUMNS

    # Ler arquivo local
    with open(file_path, "r") as f:
        data = json.load(f)

    # Pode ser lista ou objeto único
    if isinstance(data, dict):
        data = [data]

    df = pd.DataFrame(data)
    print(f"Read {len(df)} records from {file_path}")

    # Filtrar registros válidos
    if "job_posting_id" in df.columns:
        df = df[df["job_posting_id"].notna()]
        print(f"After filtering: {len(df)} valid records")

    # Transformar
    df = transform_bronze_to_silver(df, "2025", "12", "15", "10")
    print(f"After transform: {len(df)} records")

    # Skills detection (pode falhar sem acesso ao S3)
    try:
        df = apply_skills_detection(df)
        print(f"After skills detection: {len(df)} records")
    except Exception as e:
        print(f"Skills detection skipped (no S3 access): {e}")

    # Mostrar resultado
    print("\n" + "="*60)
    print("OUTPUT SAMPLE:")
    print("="*60)

    available_cols = [c for c in ["job_posting_id", "job_title", "company_name",
                                   "job_location", "skills_canonical"] if c in df.columns]
    print(df[available_cols].head(5).to_string())

    # Mostrar schema
    print("\n" + "="*60)
    print("SCHEMA:")
    print("="*60)
    for col in df.columns:
        print(f"  {col}: {df[col].dtype}")

    print(f"\nTotal columns: {len(df.columns)}")
    print(f"Expected Silver columns: {len(SILVER_COLUMNS)}")

    return df


def list_partitions():
    """Lista partições disponíveis no Bronze."""
    import awswrangler as wr

    bronze_bucket = os.environ["BRONZE_BUCKET"]
    prefix = "linkedin/"

    print(f"\nListing partitions in s3://{bronze_bucket}/{prefix}")
    print("="*60)

    try:
        # Lista arquivos JSONL/JSON no bucket
        files = wr.s3.list_objects(f"s3://{bronze_bucket}/{prefix}", suffix=".jsonl")
        if not files:
            files = wr.s3.list_objects(f"s3://{bronze_bucket}/{prefix}", suffix=".json")

        if not files:
            print("No JSON files found in Bronze bucket")
            return

        # Extrai partições únicas dos paths
        partitions = set()
        for f in files:
            # Extrai year=X/month=X/day=X/hour=X do path
            parts = f.split("/")
            partition_parts = [p for p in parts if p.startswith(("year=", "month=", "day=", "hour="))]
            if len(partition_parts) >= 4:
                partitions.add("/".join(partition_parts[:4]))

        print(f"Found {len(partitions)} partitions with data:\n")

        for p in sorted(partitions)[-20:]:  # Últimas 20
            # Parse para mostrar no formato do comando
            parts = dict(x.split("=") for x in p.split("/"))
            print(f"  make test-etl y={parts['year']} m={parts['month']} d={parts['day']} h={parts['hour']}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description="Test Lambda ETL locally")
    parser.add_argument("--year", help="Partition year")
    parser.add_argument("--month", help="Partition month")
    parser.add_argument("--day", help="Partition day")
    parser.add_argument("--hour", help="Partition hour")
    parser.add_argument("--local-file", help="Local JSON file to test")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to Silver")
    parser.add_argument("--list-partitions", action="store_true", help="List available partitions")

    args = parser.parse_args()

    if args.list_partitions:
        list_partitions()
    elif args.local_file:
        test_with_local_file(args.local_file)
    elif all([args.year, args.month, args.day, args.hour]):
        test_with_s3(args.year, args.month, args.day, args.hour, args.dry_run)
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python scripts/test_lambda_etl_local.py --list-partitions")
        print("  python scripts/test_lambda_etl_local.py --year 2025 --month 12 --day 15 --hour 10 --dry-run")
        print("  python scripts/test_lambda_etl_local.py --local-file data/sample.json")


if __name__ == "__main__":
    main()
