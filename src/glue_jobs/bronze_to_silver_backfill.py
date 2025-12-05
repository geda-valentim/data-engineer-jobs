"""
Glue Job: Bronze to Silver Backfill

Processa dados do Bronze para o Silver em lote.
Por padrão, só processa partições que ainda NÃO existem no Silver.

Parâmetros:
  --bronze_bucket: Bucket do Bronze
  --silver_bucket: Bucket do Silver
  --source_system: Sistema fonte (ex: linkedin)
  --date_from: Data inicial (YYYY-MM-DD), opcional
  --date_to: Data final (YYYY-MM-DD), opcional
  --force_reprocess: "true" para reprocessar mesmo se já existe no Silver

Uso:
  # Processar todo Bronze pendente (não reprocessa existentes)
  aws glue start-job-run --job-name bronze-to-silver-backfill

  # Processar range específico
  aws glue start-job-run --job-name bronze-to-silver-backfill \
    --arguments='{"--date_from":"2025-12-01","--date_to":"2025-12-05"}'

  # Forçar reprocessamento (sobrescreve Silver existente)
  aws glue start-job-run --job-name bronze-to-silver-backfill \
    --arguments='{"--force_reprocess":"true"}'
"""

import sys
import json

import boto3
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

from pyspark.sql.functions import (
    col,
    lit,
    regexp_replace,
    to_timestamp,
    to_date,
    row_number,
    concat_ws,
    input_file_name,
)
from pyspark.sql.window import Window

from skills_detection.skill_matcher import create_skills_udf, CATALOG_VERSION

# -------------------------------------------------------------------
# Args do Glue Job
# -------------------------------------------------------------------
args = getResolvedOptions(
    sys.argv,
    ["JOB_NAME", "bronze_bucket", "silver_bucket", "source_system"],
)

JOB_NAME = args["JOB_NAME"]
BRONZE_BUCKET = args["bronze_bucket"]
SILVER_BUCKET = args["silver_bucket"]
SOURCE_SYSTEM = args["source_system"]

# Parâmetros opcionais
all_args = {k.lstrip("-"): v for k, v in zip(sys.argv[::2], sys.argv[1::2]) if k.startswith("--")}
DATE_FROM = all_args.get("date_from")
DATE_TO = all_args.get("date_to")
FORCE_REPROCESS = all_args.get("force_reprocess", "false").lower() == "true"

# -------------------------------------------------------------------
# Config do catálogo de skills
# -------------------------------------------------------------------
SKILLS_CATALOG_KEY = "reference/skills/skills_catalog.json"

# -------------------------------------------------------------------
# Contexto Glue / Spark
# -------------------------------------------------------------------
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

job = Job(glueContext)
job.init(JOB_NAME, args)

# -------------------------------------------------------------------
# Caminhos S3
# -------------------------------------------------------------------
bronze_path = f"s3://{BRONZE_BUCKET}/{SOURCE_SYSTEM}/"
silver_path = f"s3://{SILVER_BUCKET}/{SOURCE_SYSTEM}/"

print(f"[backfill] Bronze path: {bronze_path}")
print(f"[backfill] Silver path: {silver_path}")
print(f"[backfill] Date range: {DATE_FROM or 'all'} to {DATE_TO or 'all'}")
print(f"[backfill] Force reprocess: {FORCE_REPROCESS}")

# -------------------------------------------------------------------
# Leitura Bronze
# -------------------------------------------------------------------
try:
    df_bronze = spark.read.json(bronze_path)
except Exception as e:
    print(f"[backfill] ERROR reading bronze path: {e}")
    job.commit()
    sys.exit(0)

if df_bronze.rdd.isEmpty():
    print("[backfill] No records found in Bronze. Exiting.")
    job.commit()
    sys.exit(0)

# Extrai partições do path do arquivo
# Path: s3://bucket/linkedin/year=2025/month=12/day=03/hour=14/file.jsonl
df_bronze = df_bronze.withColumn("_file_path", input_file_name())

# Extrai year/month/day/hour do path
from pyspark.sql.functions import regexp_extract

df_bronze = (
    df_bronze
    .withColumn("year", regexp_extract(col("_file_path"), r"year=(\d+)", 1))
    .withColumn("month", regexp_extract(col("_file_path"), r"month=(\d+)", 1))
    .withColumn("day", regexp_extract(col("_file_path"), r"day=(\d+)", 1))
    .withColumn("hour", regexp_extract(col("_file_path"), r"hour=(\d+)", 1))
    .drop("_file_path")
)

# Zero-pad as partições
from pyspark.sql.functions import lpad

df_bronze = (
    df_bronze
    .withColumn("month", lpad(col("month"), 2, "0"))
    .withColumn("day", lpad(col("day"), 2, "0"))
    .withColumn("hour", lpad(col("hour"), 2, "0"))
)

bronze_count = df_bronze.count()
print(f"[backfill] Total records in Bronze: {bronze_count}")

# -------------------------------------------------------------------
# Filtro por data (opcional)
# -------------------------------------------------------------------
if DATE_FROM or DATE_TO:
    df_bronze = df_bronze.withColumn(
        "_partition_date",
        to_date(concat_ws("-", col("year"), col("month"), col("day")), "yyyy-MM-dd")
    )

    if DATE_FROM:
        df_bronze = df_bronze.filter(col("_partition_date") >= DATE_FROM)
        print(f"[backfill] Filtered from {DATE_FROM}")

    if DATE_TO:
        df_bronze = df_bronze.filter(col("_partition_date") <= DATE_TO)
        print(f"[backfill] Filtered to {DATE_TO}")

    df_bronze = df_bronze.drop("_partition_date")

    filtered_count = df_bronze.count()
    print(f"[backfill] Records after date filter: {filtered_count}")

# -------------------------------------------------------------------
# Identificar partições já existentes no Silver
# -------------------------------------------------------------------
if not FORCE_REPROCESS:
    print("[backfill] Checking existing Silver partitions...")

    # Lista partições únicas no Bronze
    bronze_partitions = (
        df_bronze
        .select("year", "month", "day", "hour")
        .distinct()
        .collect()
    )
    print(f"[backfill] Bronze partitions to check: {len(bronze_partitions)}")

    # Verifica quais já existem no Silver
    s3_client = boto3.client("s3")
    existing_partitions = set()

    for row in bronze_partitions:
        partition_key = f"{SOURCE_SYSTEM}/year={row.year}/month={row.month}/day={row.day}/hour={row.hour}/"
        try:
            response = s3_client.list_objects_v2(
                Bucket=SILVER_BUCKET,
                Prefix=partition_key,
                MaxKeys=1
            )
            if response.get("KeyCount", 0) > 0:
                existing_partitions.add((row.year, row.month, row.day, row.hour))
        except Exception:
            pass

    print(f"[backfill] Existing Silver partitions: {len(existing_partitions)}")

    if existing_partitions:
        # Filtra apenas partições que NÃO existem no Silver
        from pyspark.sql.functions import struct

        df_bronze = df_bronze.withColumn(
            "_partition_key",
            struct(col("year"), col("month"), col("day"), col("hour"))
        )

        # Cria broadcast set para filtragem eficiente
        existing_broadcast = sc.broadcast(existing_partitions)

        from pyspark.sql.functions import udf
        from pyspark.sql.types import BooleanType

        def is_new_partition(year, month, day, hour):
            return (year, month, day, hour) not in existing_broadcast.value

        is_new_udf = udf(is_new_partition, BooleanType())

        df_bronze = df_bronze.filter(
            is_new_udf(col("year"), col("month"), col("day"), col("hour"))
        ).drop("_partition_key")

        new_count = df_bronze.count()
        print(f"[backfill] Records in NEW partitions only: {new_count}")

        if new_count == 0:
            print("[backfill] All partitions already exist in Silver. Nothing to process.")
            job.commit()
            sys.exit(0)

# -------------------------------------------------------------------
# Transformação Bronze -> Silver
# -------------------------------------------------------------------
print("[backfill] Applying transformations...")

html_tag_pattern = "<[^>]+>"

df_clean = (
    df_bronze
    .withColumn("job_posting_id", col("job_posting_id").cast("string"))
    .withColumn("source_system", lit(SOURCE_SYSTEM))
    .withColumn("url", col("url").cast("string"))
    .withColumn("timestamp_raw", col("timestamp").cast("string"))
    .withColumn("company_name", col("company_name").cast("string"))
    .withColumn("company_id", col("company_id").cast("string"))
    .withColumn("company_url", col("company_url").cast("string"))
    .withColumn("job_title", col("job_title").cast("string"))
    .withColumn("job_seniority_level", col("job_seniority_level").cast("string"))
    .withColumn("job_function", col("job_function").cast("string"))
    .withColumn("job_employment_type", col("job_employment_type").cast("string"))
    .withColumn("job_industries", col("job_industries").cast("string"))
    .withColumn("job_location", col("job_location").cast("string"))
    .withColumn("country_code", col("country_code").cast("string"))
    .withColumn("application_availability", col("application_availability").cast("boolean"))
    .withColumn("apply_link", col("apply_link").cast("string"))
    .withColumn("job_num_applicants", col("job_num_applicants").cast("int"))
    .withColumn("salary_min", col("base_salary.min_amount").cast("double"))
    .withColumn("salary_max", col("base_salary.max_amount").cast("double"))
    .withColumn("salary_currency", col("base_salary.currency").cast("string"))
    .withColumn("salary_period", col("base_salary.payment_period").cast("string"))
    .withColumn("job_poster_name", col("job_poster.name").cast("string"))
    .withColumn("job_poster_title", col("job_poster.title").cast("string"))
    .withColumn("job_poster_url", col("job_poster.url").cast("string"))
    .withColumn("job_summary", col("job_summary").cast("string"))
    .withColumn("job_description_html", col("job_description_formatted").cast("string"))
)

df_clean = (
    df_clean
    .withColumn("job_posted_datetime", to_timestamp(col("job_posted_date")))
    .withColumn("job_posted_date_only", to_date(col("job_posted_date")))
    .withColumn("scraped_at", to_timestamp(col("timestamp_raw")))
)

# HTML -> texto plano
df_clean = df_clean.withColumn(
    "job_description_text",
    regexp_replace(col("job_description_html"), html_tag_pattern, " "),
)

df_clean = df_clean.withColumn(
    "job_description_text",
    regexp_replace(col("job_description_text"), r"\s+", " "),
)

# -------------------------------------------------------------------
# Colunas do Silver
# -------------------------------------------------------------------
silver_cols = [
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
    "year",
    "month",
    "day",
    "hour",
]

df_silver_base = df_clean.select(*silver_cols)

# -------------------------------------------------------------------
# Leitura do catálogo de Skills
# -------------------------------------------------------------------
print(f"[backfill] Loading skills catalog from s3://{SILVER_BUCKET}/{SKILLS_CATALOG_KEY}")

s3_client = boto3.client("s3")

try:
    obj = s3_client.get_object(Bucket=SILVER_BUCKET, Key=SKILLS_CATALOG_KEY)
    catalog_json = obj["Body"].read().decode("utf-8")
    catalog_dict = json.loads(catalog_json)
except Exception as e:
    print(f"[backfill] ERROR reading skills catalog: {e}")
    catalog_dict = {}

# Cria UDF
detect_skills_udf = create_skills_udf(sc, catalog_dict, version=CATALOG_VERSION)
print(f"[backfill] Skills UDF created with catalog version {CATALOG_VERSION}")

# -------------------------------------------------------------------
# Aplica extração de skills
# -------------------------------------------------------------------
print("[backfill] Applying skills detection...")

df_with_skills = df_silver_base.withColumn(
    "skills_struct",
    detect_skills_udf(col("job_title"), col("job_description_text")),
).withColumn(
    "skills_canonical", col("skills_struct.skills_canonical")
).withColumn(
    "skills_families", col("skills_struct.skills_families")
).withColumn(
    "skills_raw_hits", col("skills_struct.skills_raw_hits")
).withColumn(
    "skills_catalog_version", col("skills_struct.skills_catalog_version")
).drop("skills_struct")

# -------------------------------------------------------------------
# Dedup por job_posting_id
# -------------------------------------------------------------------
print("[backfill] Applying dedup on job_posting_id...")

w = Window.partitionBy("job_posting_id").orderBy(col("scraped_at").desc())

df_not_null = df_with_skills.filter(col("job_posting_id").isNotNull())
df_null = df_with_skills.filter(col("job_posting_id").isNull())

df_deduped = (
    df_not_null
    .withColumn("rn", row_number().over(w))
    .filter(col("rn") == 1)
    .drop("rn")
).unionByName(df_null)

# -------------------------------------------------------------------
# Escrita no Silver
# -------------------------------------------------------------------
print("[backfill] Writing to Silver...")

spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")

(
    df_deduped
    .repartition("year", "month", "day", "hour")
    .write
    .mode("overwrite")
    .format("parquet")
    .partitionBy("year", "month", "day", "hour")
    .save(silver_path)
)

# -------------------------------------------------------------------
# Relatório final
# -------------------------------------------------------------------
input_count = df_with_skills.count()
final_count = df_deduped.count()
duplicates_removed = input_count - final_count

print("=" * 60)
print("[backfill] RELATÓRIO FINAL")
print("=" * 60)
print(f"  Source system: {SOURCE_SYSTEM}")
print(f"  Date range: {DATE_FROM or 'all'} to {DATE_TO or 'all'}")
print(f"  Force reprocess: {FORCE_REPROCESS}")
print(f"  Registros Bronze processados: {input_count}")
print(f"  Duplicatas removidas: {duplicates_removed}")
print(f"  Registros finais no Silver: {final_count}")
print(f"  Skills catalog version: {CATALOG_VERSION}")
print("=" * 60)

job.commit()
