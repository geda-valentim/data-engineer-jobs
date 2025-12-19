"""
Lambda Bronze to Silver - ETL de dados brutos para camada Silver

Substitui o Glue Job bronze_to_silver para reduzir custos.
Usa pandas/awswrangler ao invés de Spark para workloads pequenos.

Economia estimada: ~96% ($19/mês → ~$0.30/mês)
"""

import os
import json
import re
import time
import boto3
import awswrangler as wr
import pandas as pd
from datetime import datetime

# Importa o SkillMatcher standalone (sem Spark)
import sys
sys.path.insert(0, "/opt/python")  # Lambda Layer path
from skills_detection.skill_matcher import SkillMatcher, CATALOG_VERSION


# =============================================================================
# Configuração
# =============================================================================

BRONZE_BUCKET = os.environ.get("BRONZE_BUCKET", "data-engineer-jobs-bronze")
SILVER_BUCKET = os.environ.get("SILVER_BUCKET", "data-engineer-jobs-silver")
SOURCE_SYSTEM = os.environ.get("SOURCE_SYSTEM", "linkedin")
SKILLS_CATALOG_KEY = "reference/skills/skills_catalog.json"

s3_client = boto3.client("s3")
cloudwatch_client = boto3.client("cloudwatch")


def publish_metrics(records_processed: int, duration_ms: float, status: str) -> None:
    """Publish ETL metrics to CloudWatch."""
    try:
        cloudwatch_client.put_metric_data(
            Namespace="DataEngineerJobs/ETL",
            MetricData=[
                {
                    "MetricName": "RecordsProcessed",
                    "Value": records_processed,
                    "Unit": "Count",
                    "Dimensions": [
                        {"Name": "Job", "Value": "bronze_to_silver"},
                        {"Name": "Status", "Value": status},
                    ],
                },
                {
                    "MetricName": "DurationMs",
                    "Value": duration_ms,
                    "Unit": "Milliseconds",
                    "Dimensions": [
                        {"Name": "Job", "Value": "bronze_to_silver"},
                    ],
                },
            ],
        )
    except Exception as e:
        print(f"[bronze_to_silver] Warning: Failed to publish metrics: {e}")


# =============================================================================
# Skills Detection
# =============================================================================

_skills_matcher = None


def get_skills_matcher() -> SkillMatcher:
    """Carrega o catálogo de skills do S3 (cached)."""
    global _skills_matcher

    if _skills_matcher is None:
        try:
            obj = s3_client.get_object(Bucket=SILVER_BUCKET, Key=SKILLS_CATALOG_KEY)
            catalog_json = obj["Body"].read().decode("utf-8")
            catalog_dict = json.loads(catalog_json)
            _skills_matcher = SkillMatcher.from_dict(catalog_dict, version=CATALOG_VERSION)
            print(f"[bronze_to_silver] Skills catalog loaded: {CATALOG_VERSION}")
        except Exception as e:
            print(f"[bronze_to_silver] WARNING: Could not load skills catalog: {e}")
            _skills_matcher = SkillMatcher.from_dict({}, version=CATALOG_VERSION)

    return _skills_matcher


def detect_skills_row(row: pd.Series, matcher: SkillMatcher) -> dict:
    """Detecta skills para uma linha do DataFrame."""
    title = str(row.get("job_title") or "")
    description = str(row.get("job_description_text") or "")
    text = f"{title} {description}"
    return matcher.detect(text)


# =============================================================================
# Transformações
# =============================================================================

HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_PATTERN = re.compile(r"\s+")


def transform_bronze_to_silver(df: pd.DataFrame, year: str, month: str, day: str, hour: str) -> pd.DataFrame:
    """
    Aplica transformações Bronze → Silver.

    Equivalente ao código Spark do Glue Job, mas com pandas.
    """
    # Casting e normalização de tipos
    df = df.copy()

    # Campos básicos
    df["job_posting_id"] = df["job_posting_id"].astype(str)
    df["source_system"] = SOURCE_SYSTEM
    df["url"] = df["url"].astype(str) if "url" in df.columns else None

    # Timestamps
    if "timestamp" in df.columns:
        df["scraped_at"] = pd.to_datetime(df["timestamp"], errors="coerce")

    if "job_posted_date" in df.columns:
        df["job_posted_datetime"] = pd.to_datetime(df["job_posted_date"], errors="coerce")
        # Convert to date, then back to datetime for Parquet DATE compatibility with Glue/Spark
        df["job_posted_date_only"] = pd.to_datetime(df["job_posted_datetime"].dt.date)

    # Campos de empresa
    for col in ["company_name", "company_id", "company_url"]:
        if col in df.columns:
            df[col] = df[col].astype(str)

    # Campos de vaga
    for col in ["job_title", "job_seniority_level", "job_function",
                "job_employment_type", "job_industries", "job_location",
                "country_code", "apply_link", "job_summary"]:
        if col in df.columns:
            df[col] = df[col].astype(str)

    # Campos numéricos
    if "job_num_applicants" in df.columns:
        # Use float64 first (handles NaN), then fillna with 0 and convert to int for Glue compatibility
        df["job_num_applicants"] = pd.to_numeric(df["job_num_applicants"], errors="coerce")

    if "application_availability" in df.columns:
        df["application_availability"] = df["application_availability"].astype(bool)

    # Salário (nested fields) - ensure float64 for Glue/Athena compatibility
    if "base_salary" in df.columns:
        df["salary_min"] = pd.to_numeric(
            df["base_salary"].apply(lambda x: x.get("min_amount") if isinstance(x, dict) else None),
            errors="coerce"
        )
        df["salary_max"] = pd.to_numeric(
            df["base_salary"].apply(lambda x: x.get("max_amount") if isinstance(x, dict) else None),
            errors="coerce"
        )
        df["salary_currency"] = df["base_salary"].apply(lambda x: x.get("currency") if isinstance(x, dict) else None)
        df["salary_period"] = df["base_salary"].apply(lambda x: x.get("payment_period") if isinstance(x, dict) else None)

    # Job poster (nested fields)
    if "job_poster" in df.columns:
        df["job_poster_name"] = df["job_poster"].apply(lambda x: x.get("name") if isinstance(x, dict) else None)
        df["job_poster_title"] = df["job_poster"].apply(lambda x: x.get("title") if isinstance(x, dict) else None)
        df["job_poster_url"] = df["job_poster"].apply(lambda x: x.get("url") if isinstance(x, dict) else None)

    # HTML para texto plano
    if "job_description_formatted" in df.columns:
        df["job_description_html"] = df["job_description_formatted"].astype(str)
        df["job_description_text"] = df["job_description_html"].apply(
            lambda x: WHITESPACE_PATTERN.sub(" ", HTML_TAG_PATTERN.sub(" ", str(x))).strip()
        )

    # Partições (zero-padded)
    df["year"] = year
    df["month"] = month.zfill(2)
    df["day"] = day.zfill(2)
    df["hour"] = hour.zfill(2)

    return df


def apply_skills_detection(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica detecção de skills em todas as linhas."""
    matcher = get_skills_matcher()

    skills_results = df.apply(lambda row: detect_skills_row(row, matcher), axis=1)
    skills_df = pd.DataFrame(skills_results.tolist())

    df["skills_canonical"] = skills_df["skills_canonical"]
    df["skills_families"] = skills_df["skills_families"]
    df["skills_raw_hits"] = skills_df["skills_raw_hits"]
    df["skills_catalog_version"] = skills_df["catalog_version"]

    return df


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicatas mantendo o registro mais recente."""
    if "scraped_at" not in df.columns or "job_posting_id" not in df.columns:
        return df

    # Normalize timezone to avoid tz-naive vs tz-aware comparison errors
    # Convert to UTC, removing timezone info to ensure consistent comparison
    df["scraped_at"] = pd.to_datetime(df["scraped_at"], utc=True).dt.tz_localize(None)

    df = df.sort_values("scraped_at", ascending=False, na_position="last")
    df = df.drop_duplicates(subset=["job_posting_id"], keep="first")
    return df


# =============================================================================
# Colunas Silver
# =============================================================================

SILVER_COLUMNS = [
    "job_posting_id",
    "source_system",
    "url",
    "scraped_at",
    "company_name",
    "company_id",
    "company_url",
    "job_title",
    "job_seniority_level",
    "job_function",
    "job_employment_type",
    "job_industries",
    "job_location",
    "country_code",
    "job_posted_datetime",
    "job_posted_date_only",
    "application_availability",
    "apply_link",
    "job_num_applicants",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_period",
    "job_poster_name",
    "job_poster_title",
    "job_poster_url",
    "job_summary",
    "job_description_html",
    "job_description_text",
    "skills_canonical",
    "skills_families",
    "skills_raw_hits",
    "skills_catalog_version",
    "year",
    "month",
    "day",
    "hour",
]


# =============================================================================
# Handler Principal
# =============================================================================

def handler(event, context):
    """
    Processa partição Bronze → Silver.

    Event format:
    {
        "year": "2025",
        "month": "12",
        "day": "15",
        "hour": "10"
    }
    """
    start_time = time.time()

    year = str(event.get("year"))
    month = str(event.get("month"))
    day = str(event.get("day"))
    hour = str(event.get("hour"))

    print(f"[bronze_to_silver] Processing partition: {year}/{month}/{day}/{hour}")

    # 1. Ler Bronze (JSONL ou JSON)
    bronze_path = f"s3://{BRONZE_BUCKET}/{SOURCE_SYSTEM}/year={year}/month={month}/day={day}/hour={hour}/"

    try:
        # Tenta .jsonl primeiro (formato Bright Data), depois .json
        try:
            df = wr.s3.read_json(path=bronze_path, path_suffix=".jsonl", lines=True)
            print(f"[bronze_to_silver] Read from .jsonl files")
        except Exception:
            df = wr.s3.read_json(path=bronze_path, path_suffix=".json")
            print(f"[bronze_to_silver] Read from .json files")
    except Exception as e:
        print(f"[bronze_to_silver] No data found or error reading: {e}")
        duration_ms = (time.time() - start_time) * 1000
        publish_metrics(0, duration_ms, "no_data")
        return {
            "status": "no_data",
            "partition": f"{year}/{month}/{day}/{hour}",
            "records_processed": 0,
            "duration_ms": round(duration_ms, 2),
            "bronze_path": bronze_path,
        }

    if df.empty:
        print("[bronze_to_silver] Empty DataFrame, skipping")
        duration_ms = (time.time() - start_time) * 1000
        publish_metrics(0, duration_ms, "no_data")
        return {
            "status": "no_data",
            "partition": f"{year}/{month}/{day}/{hour}",
            "records_processed": 0,
            "duration_ms": round(duration_ms, 2),
            "bronze_path": bronze_path,
        }

    initial_count = len(df)
    print(f"[bronze_to_silver] Read {initial_count} records from Bronze")

    # 2. Filtrar erros de crawl
    if "job_posting_id" in df.columns:
        df = df[df["job_posting_id"].notna()]
        valid_count = len(df)
        print(f"[bronze_to_silver] {valid_count} valid records (filtered {initial_count - valid_count} errors)")

        if df.empty:
            print("[bronze_to_silver] No valid records after filtering")
            duration_ms = (time.time() - start_time) * 1000
            publish_metrics(0, duration_ms, "no_valid_data")
            return {
                "status": "no_valid_data",
                "partition": f"{year}/{month}/{day}/{hour}",
                "records_processed": 0,
                "duration_ms": round(duration_ms, 2),
                "bronze_path": bronze_path,
            }
    else:
        print("[bronze_to_silver] No job_posting_id column - likely crawl error structure")
        duration_ms = (time.time() - start_time) * 1000
        publish_metrics(0, duration_ms, "crawl_error")
        return {
            "status": "crawl_error",
            "partition": f"{year}/{month}/{day}/{hour}",
            "records_processed": 0,
            "duration_ms": round(duration_ms, 2),
            "bronze_path": bronze_path,
        }

    # 3. Transformações
    df = transform_bronze_to_silver(df, year, month, day, hour)

    # 4. Skills detection
    df = apply_skills_detection(df)

    # 5. Ler dados existentes no Silver para merge
    silver_partition_path = f"s3://{SILVER_BUCKET}/{SOURCE_SYSTEM}/year={year}/month={month.zfill(2)}/day={day.zfill(2)}/hour={hour.zfill(2)}/"

    try:
        existing_df = wr.s3.read_parquet(path=silver_partition_path)
        print(f"[bronze_to_silver] Found {len(existing_df)} existing records in Silver")
        df = pd.concat([df, existing_df], ignore_index=True)
    except Exception:
        print("[bronze_to_silver] No existing data in Silver partition")

    # 6. Dedup
    before_dedup = len(df)
    df = deduplicate(df)
    after_dedup = len(df)
    print(f"[bronze_to_silver] Dedup: {before_dedup} → {after_dedup} records")

    # 7. Selecionar colunas Silver (apenas as que existem)
    available_cols = [c for c in SILVER_COLUMNS if c in df.columns]
    df = df[available_cols]

    # 8. Escrever Silver (Parquet particionado)
    silver_base_path = f"s3://{SILVER_BUCKET}/{SOURCE_SYSTEM}/"

    wr.s3.to_parquet(
        df=df,
        path=silver_base_path,
        dataset=True,
        partition_cols=["year", "month", "day", "hour"],
        mode="overwrite_partitions",
    )

    silver_output_path = f"s3://{SILVER_BUCKET}/{SOURCE_SYSTEM}/year={year}/month={month.zfill(2)}/day={day.zfill(2)}/hour={hour.zfill(2)}/"
    print(f"[bronze_to_silver] Wrote {len(df)} records to {silver_output_path}")

    duration_ms = (time.time() - start_time) * 1000
    publish_metrics(len(df), duration_ms, "success")

    return {
        "status": "success",
        "partition": f"{year}/{month}/{day}/{hour}",
        "records_processed": len(df),
        "duration_ms": round(duration_ms, 2),
        "bronze_path": bronze_path,
        "silver_path": silver_output_path,
        "skills_catalog_version": CATALOG_VERSION,
    }
