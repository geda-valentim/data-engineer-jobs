import sys

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
    coalesce,
    sha2,
    row_number,
)
from pyspark.sql.window import Window

# ----------------------------
# Args
# ----------------------------
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

# ----------------------------
# Glue / Spark setup
# ----------------------------
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

job = Job(glueContext)
job.init(JOB_NAME, args)

bronze_path = (
    f"s3://{BRONZE_BUCKET}/{SOURCE_SYSTEM}/"
    f"year={YEAR}/month={MONTH}/day={DAY}/hour={HOUR}/"
)

silver_base_path = f"s3://{SILVER_BUCKET}/{SOURCE_SYSTEM}/"

print(f"[bronze_to_silver] Reading from: {bronze_path}")
print(f"[bronze_to_silver] Writing to: {silver_base_path}")

# ----------------------------
# Read bronze
# ----------------------------
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

# ----------------------------
# Basic cleaning / typing
# ----------------------------
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

df_clean = df_clean.withColumn(
    "job_description_text",
    regexp_replace(col("job_description_html"), html_tag_pattern, " "),
)

df_clean = df_clean.withColumn(
    "job_description_text",
    regexp_replace(col("job_description_text"), r"\s+", " "),
)

df_clean = (
    df_clean
    .withColumn("year", lit(int(YEAR)))
    .withColumn("month", lit(int(MONTH)))
    .withColumn("day", lit(int(DAY)))
    .withColumn("hour", lit(int(HOUR)))
)

# ----------------------------
# Dedup técnico dentro do batch
# ----------------------------
# job_unique_id: chave técnica da vaga
df_with_key = (
    df_clean
    .withColumn(
        "job_unique_id",
        coalesce(
            col("job_posting_id"),
            sha2(col("url"), 256),
        ),
    )
    .withColumn("ingestion_ts", col("scraped_at"))
)

# Janela por (job_unique_id, ingestion_ts) – ou seja,
# mesma vaga no mesmo timestamp de ingestão (batch/hora).
w_batch = Window.partitionBy("job_unique_id", "ingestion_ts").orderBy(
    col("scraped_at").desc()
)

df_dedup = (
    df_with_key
    .withColumn("rn", row_number().over(w_batch))
    .filter(col("rn") == 1)
    .drop("rn")
)

# ----------------------------
# Seleção de colunas finais da silver
# ----------------------------
silver_cols = [
    "job_unique_id",           # <--- chave técnica para gold/ATS
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

df_silver = df_dedup.select(*silver_cols)

# ----------------------------
# Write silver
# ----------------------------
(
    df_silver
    .repartition("year", "month", "day", "hour")
    .write
    .mode("append")
    .format("parquet")
    .partitionBy("year", "month", "day", "hour")
    .save(silver_base_path)
)

print("[bronze_to_silver] Successfully wrote silver data.")

job.commit()
