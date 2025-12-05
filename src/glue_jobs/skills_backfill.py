"""
Glue Job: Skills Backfill

Re-processa dados do Silver para atualizar/adicionar colunas de skills
usando o catálogo mais recente.

Parâmetros:
  --silver_bucket: Bucket do Silver
  --source_system: Sistema fonte (ex: linkedin)
  --date_from: Data inicial (YYYY-MM-DD), opcional
  --date_to: Data final (YYYY-MM-DD), opcional

Uso:
  # Reprocessar todo o histórico
  aws glue start-job-run --job-name skills-backfill \
    --arguments='{"--silver_bucket":"my-silver","--source_system":"linkedin"}'

  # Reprocessar range específico
  aws glue start-job-run --job-name skills-backfill \
    --arguments='{"--silver_bucket":"my-silver","--source_system":"linkedin","--date_from":"2024-01-01","--date_to":"2024-01-31"}'
"""

import sys
import json

import boto3
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

from pyspark.sql.functions import col, row_number
from pyspark.sql.window import Window

from skills_detection.skill_matcher import create_skills_udf, CATALOG_VERSION

# -------------------------------------------------------------------
# Args do Glue Job
# -------------------------------------------------------------------
# Parâmetros obrigatórios
args = getResolvedOptions(
    sys.argv,
    ["JOB_NAME", "silver_bucket", "source_system"],
)

JOB_NAME = args["JOB_NAME"]
SILVER_BUCKET = args["silver_bucket"]
SOURCE_SYSTEM = args["source_system"]

# Parâmetros opcionais (date range)
all_args = {k: v for k, v in zip(sys.argv[::2], sys.argv[1::2])}
DATE_FROM = all_args.get("--date_from")
DATE_TO = all_args.get("--date_to")

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
silver_path = f"s3://{SILVER_BUCKET}/{SOURCE_SYSTEM}/"

print(f"[skills_backfill] Silver path: {silver_path}")
print(f"[skills_backfill] Date range: {DATE_FROM or 'all'} to {DATE_TO or 'all'}")

# -------------------------------------------------------------------
# Leitura do Silver existente
# -------------------------------------------------------------------
try:
    df_silver = spark.read.parquet(silver_path)
except Exception as e:
    print(f"[skills_backfill] ERROR reading silver path: {e}")
    job.commit()
    sys.exit(1)

if df_silver.rdd.isEmpty():
    print("[skills_backfill] No records found. Exiting.")
    job.commit()
    sys.exit(0)

record_count = df_silver.count()
print(f"[skills_backfill] Found {record_count} total records")

# -------------------------------------------------------------------
# Filtro por data (opcional)
# -------------------------------------------------------------------
if DATE_FROM or DATE_TO:
    from pyspark.sql.functions import to_date, concat_ws

    # Cria coluna de data a partir das partições
    df_silver = df_silver.withColumn(
        "_partition_date",
        to_date(
            concat_ws("-", col("year"), col("month"), col("day")),
            "yyyy-M-d"
        )
    )

    if DATE_FROM:
        df_silver = df_silver.filter(col("_partition_date") >= DATE_FROM)
        print(f"[skills_backfill] Filtered from {DATE_FROM}")

    if DATE_TO:
        df_silver = df_silver.filter(col("_partition_date") <= DATE_TO)
        print(f"[skills_backfill] Filtered to {DATE_TO}")

    df_silver = df_silver.drop("_partition_date")

    filtered_count = df_silver.count()
    print(f"[skills_backfill] Records after date filter: {filtered_count}")

# -------------------------------------------------------------------
# Leitura do catálogo de Skills (JSON no S3)
# -------------------------------------------------------------------
print(f"[skills_backfill] Loading skills catalog from s3://{SILVER_BUCKET}/{SKILLS_CATALOG_KEY}")

s3_client = boto3.client("s3")

try:
    obj = s3_client.get_object(Bucket=SILVER_BUCKET, Key=SKILLS_CATALOG_KEY)
    catalog_json = obj["Body"].read().decode("utf-8")
    catalog_dict = json.loads(catalog_json)
except Exception as e:
    print(f"[skills_backfill] ERROR reading skills catalog: {e}")
    job.commit()
    sys.exit(1)

# Cria UDF usando módulo compartilhado
detect_skills_udf = create_skills_udf(sc, catalog_dict, version=CATALOG_VERSION)
print(f"[skills_backfill] Skills UDF created with catalog version {CATALOG_VERSION}")

# -------------------------------------------------------------------
# Remove colunas antigas de skills (se existirem)
# -------------------------------------------------------------------
skills_cols = [
    "skills_canonical",
    "skills_families",
    "skills_raw_hits",
    "skills_catalog_version",
]

existing_cols = df_silver.columns
cols_to_drop = [c for c in skills_cols if c in existing_cols]

if cols_to_drop:
    print(f"[skills_backfill] Dropping existing skills columns: {cols_to_drop}")
    df_silver = df_silver.drop(*cols_to_drop)

# -------------------------------------------------------------------
# Aplica extração de skills
# -------------------------------------------------------------------
print("[skills_backfill] Applying skills detection...")

df_with_skills = df_silver.withColumn(
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
# Dedup por job_posting_id (mantém scrape mais recente)
# -------------------------------------------------------------------
print("[skills_backfill] Applying dedup on job_posting_id...")

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
# Escrita no Silver (overwrite por partição)
# -------------------------------------------------------------------
print("[skills_backfill] Writing updated data...")

(
    df_deduped
    .repartition("year", "month", "day", "hour")
    .write
    .mode("overwrite")
    .format("parquet")
    .partitionBy("year", "month", "day", "hour")
    .option("partitionOverwriteMode", "dynamic")
    .save(silver_path)
)

# -------------------------------------------------------------------
# Relatório final
# -------------------------------------------------------------------
input_count = df_with_skills.count()
final_count = df_deduped.count()
duplicates_removed = input_count - final_count

print("=" * 60)
print("[skills_backfill] RELATÓRIO FINAL")
print("=" * 60)
print(f"  Source system: {SOURCE_SYSTEM}")
print(f"  Date range: {DATE_FROM or 'all'} to {DATE_TO or 'all'}")
print(f"  Registros processados: {input_count}")
print(f"  Duplicatas removidas: {duplicates_removed}")
print(f"  Registros finais: {final_count}")
print(f"  Skills catalog version: {CATALOG_VERSION}")
print("=" * 60)

job.commit()
