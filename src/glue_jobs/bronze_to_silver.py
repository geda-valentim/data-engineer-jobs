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
)
from pyspark.sql.window import Window

from skills_detection.skill_matcher import create_skills_udf, CATALOG_VERSION

# -------------------------------------------------------------------
# Args do Glue Job
# -------------------------------------------------------------------
args = getResolvedOptions(
    sys.argv,
    [
        "JOB_NAME",
        "bronze_bucket",
        "silver_bucket",
        "source_system",
        "year",
        "month",
        "day",
        "hour",
    ],
)

JOB_NAME = args["JOB_NAME"]
BRONZE_BUCKET = args["bronze_bucket"]
SILVER_BUCKET = args["silver_bucket"]
SOURCE_SYSTEM = args["source_system"]

YEAR = args["year"]
MONTH = args["month"]
DAY = args["day"]
HOUR = args["hour"]

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
bronze_path = (
    f"s3://{BRONZE_BUCKET}/{SOURCE_SYSTEM}/"
    f"year={YEAR}/month={MONTH}/day={DAY}/hour={HOUR}/"
)

silver_base_path = f"s3://{SILVER_BUCKET}/{SOURCE_SYSTEM}/"

print(f"[bronze_to_silver] Reading from: {bronze_path}")
print(f"[bronze_to_silver] Writing to: {silver_base_path}")

# -------------------------------------------------------------------
# Leitura Bronze
# -------------------------------------------------------------------
try:
    df_bronze = spark.read.json(bronze_path)
except Exception as e:
    print(f"[bronze_to_silver] ERROR reading bronze path: {e}")
    job.commit()
    sys.exit(0)

if df_bronze.rdd.isEmpty():
    print("[bronze_to_silver] No records found for this partition. Exiting gracefully.")
    job.commit()
    sys.exit(0)

# -------------------------------------------------------------------
# Validação: Detecta se arquivo contém erro de crawl (sem vagas)
# -------------------------------------------------------------------
# Quando não há vagas no LinkedIn, o crawl retorna uma estrutura de erro:
# {"timestamp": "...", "input": {...}, "error": "...", "error_code": "crawl_failed"}
# Isso é um cenário válido de negócio, NÃO uma falha do job
bronze_columns = df_bronze.columns

if "error_code" in bronze_columns or ("error" in bronze_columns and "job_posting_id" not in bronze_columns):
    print("=" * 60)
    print("[bronze_to_silver] CRAWL SEM RESULTADOS DETECTADO")
    print("=" * 60)

    # Mostra amostra dos registros de erro para auditoria
    df_bronze.select("timestamp", "error", "error_code").show(truncate=False)

    print(f"  Partição: year={YEAR}/month={MONTH.zfill(2)}/day={DAY.zfill(2)}/hour={HOUR.zfill(2)}")
    print(f"  Status: Nenhuma vaga encontrada no período")
    print(f"  Motivo: Crawl retornou estrutura de erro (provavelmente sem vagas disponíveis)")
    print(f"  Ação: Job finalizado com SUCESSO - cenário esperado de negócio")
    print(f"  Registros processados: 0")
    print("=" * 60)

    job.commit()
    sys.exit(0)

print(f"[bronze_to_silver] Valid job data detected. Proceeding with transformation...")
print(f"[bronze_to_silver] Record count: {df_bronze.count()}")

# -------------------------------------------------------------------
# Limpeza / Normalização básica
# -------------------------------------------------------------------
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

# Partições de data (strings zero-padded para consistência)
df_clean = (
    df_clean
    .withColumn("year", lit(YEAR))
    .withColumn("month", lit(MONTH.zfill(2)))
    .withColumn("day", lit(DAY.zfill(2)))
    .withColumn("hour", lit(HOUR.zfill(2)))
)

# -------------------------------------------------------------------
# Colunas base do Silver (antes das skills)
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
# Leitura do catálogo de Skills (JSON no S3)
# -------------------------------------------------------------------
print(f"[bronze_to_silver] Loading skills catalog from s3://{SILVER_BUCKET}/{SKILLS_CATALOG_KEY}")

s3_client = boto3.client("s3")

try:
    obj = s3_client.get_object(Bucket=SILVER_BUCKET, Key=SKILLS_CATALOG_KEY)
    catalog_json = obj["Body"].read().decode("utf-8")
    catalog_dict = json.loads(catalog_json)
except Exception as e:
    print(f"[bronze_to_silver] ERROR reading skills catalog: {e}")
    catalog_dict = {}

# Cria UDF usando módulo compartilhado
detect_skills_udf = create_skills_udf(sc, catalog_dict, version=CATALOG_VERSION)
print(f"[bronze_to_silver] Skills UDF created with catalog version {CATALOG_VERSION}")

# -------------------------------------------------------------------
# Aplica extração de skills
# -------------------------------------------------------------------
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

silver_cols_with_skills = silver_cols + [
    "skills_canonical",
    "skills_families",
    "skills_raw_hits",
    "skills_catalog_version",
]

df_silver_enriched = df_with_skills.select(*silver_cols_with_skills)

# -------------------------------------------------------------------
# Dedup técnico por job_posting_id (mantém scrape mais recente)
# -------------------------------------------------------------------
print("[bronze_to_silver] Applying technical dedup on job_posting_id/scraped_at")

w = Window.partitionBy("job_posting_id").orderBy(col("scraped_at").desc())

# Merge com dados existentes na partição para garantir unicidade global
silver_partition_path = (
    f"{silver_base_path}year={YEAR}/month={MONTH.zfill(2)}/day={DAY.zfill(2)}/hour={HOUR.zfill(2)}/"
)

try:
    df_existing = spark.read.parquet(silver_partition_path)
    existing_count = df_existing.count()
    df_combined = df_silver_enriched.unionByName(df_existing)
    print("[bronze_to_silver] Found existing data, merging for dedup")
except Exception:
    df_combined = df_silver_enriched
    existing_count = 0
    print("[bronze_to_silver] No existing data in partition")

df_not_null = df_combined.filter(col("job_posting_id").isNotNull())
df_null = df_combined.filter(col("job_posting_id").isNull())

df_not_null_dedup = (
    df_not_null
    .withColumn("rn", row_number().over(w))
    .filter(col("rn") == 1)
    .drop("rn")
)

df_final = df_not_null_dedup.unionByName(df_null)

# -------------------------------------------------------------------
# Escrita no Silver (overwrite na partição)
# -------------------------------------------------------------------
spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")

(
    df_final
    .repartition("year", "month", "day", "hour")
    .write
    .mode("overwrite")
    .format("parquet")
    .partitionBy("year", "month", "day", "hour")
    .save(silver_base_path)
)

# -------------------------------------------------------------------
# Relatório final
# -------------------------------------------------------------------
new_count = df_silver_enriched.count()
final_count = df_final.count()
combined_count = new_count + existing_count
duplicates_removed = combined_count - final_count

print("=" * 60)
print("[bronze_to_silver] RELATÓRIO FINAL")
print("=" * 60)
print(f"  Partição: year={YEAR}/month={MONTH.zfill(2)}/day={DAY.zfill(2)}/hour={HOUR.zfill(2)}")
print(f"  Registros novos (bronze): {new_count}")
print(f"  Registros existentes (silver): {existing_count}")
print(f"  Total após merge: {combined_count}")
print(f"  Duplicatas removidas: {duplicates_removed}")
print(f"  Registros finais: {final_count}")
print(f"  Skills catalog version: {CATALOG_VERSION}")
print("=" * 60)

job.commit()
