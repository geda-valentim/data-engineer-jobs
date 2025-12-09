from pathlib import Path

from pyspark.sql.functions import (
    input_file_name,
    regexp_extract,
    col,
    to_json,
    lit,
    get_json_object,
    when,
    coalesce,
)
from src.dev.deltalake.spark_session import get_spark


# Paths (relativos ao projeto)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # src/dev/deltalake -> raiz
BASE_DIR = PROJECT_ROOT / "data" / "local" / "ai_enrichment"
BRONZE_DIR = BASE_DIR / "bronze"
DELTA_SILVER_PATH = BASE_DIR / "silver" / "delta" / "enriched_jobs"

# Colunas comuns para o UNION
COLUMNS = [
    "job_id", "job_title", "company_name", "job_location",
    "model_name", "pass_num", "source_file",
    "tokens", "cost",
    # Pass1
    "salary_min", "salary_max", "salary_currency",
    "work_model", "contract_type", "years_experience_min",
    "education_level", "must_have_skills_json",
    # Pass2
    "seniority_level", "primary_cloud",
    # Pass3
    "recommendation_score", "overall_assessment",
    # Raw
    "result_json"
]


def run_bronze_to_silver_enriched_jobs():
    spark = get_spark("BronzeToSilverEnrichedJobs")

    # === PASS 1: Extração ===
    pass1_pattern = str(BRONZE_DIR / "*" / "pass1-*.json")
    print(f"Lendo Pass1: {pass1_pattern}")

    df1 = spark.read.option("multiLine", True).json(pass1_pattern)
    df1 = (df1
        .withColumn("source_file", input_file_name())
        .withColumn("job_id", regexp_extract(col("source_file"), r"/bronze/([^/]+)/", 1).cast("long"))
        .withColumn("model_name", regexp_extract(col("source_file"), r"pass[0-9]+-(.*?)\.json", 1))
        .withColumn("pass_num", lit(1))
        # Metadata
        .withColumn("job_title", col("metadata.job_title"))
        .withColumn("company_name", col("metadata.company_name"))
        .withColumn("job_location", col("metadata.job_location"))
        # Tokens (pass1 usa total_tokens_used, não tem result.tokens)
        .withColumn("tokens", col("result.total_tokens_used").cast("int"))
        .withColumn("cost", col("result.enrichment_cost_usd"))
        # Pass1 específicos
        .withColumn("salary_min", col("result.ext_salary_min"))
        .withColumn("salary_max", col("result.ext_salary_max"))
        .withColumn("salary_currency", col("result.ext_salary_currency"))
        .withColumn("work_model", col("result.ext_work_model_stated"))
        .withColumn("contract_type", col("result.ext_contract_type"))
        .withColumn("years_experience_min", col("result.ext_years_experience_min"))
        .withColumn("education_level", col("result.ext_education_level"))
        .withColumn("must_have_skills_json", to_json(col("result.ext_must_have_hard_skills")))
        # Pass2/3 específicos (null para pass1)
        .withColumn("seniority_level", lit(None).cast("string"))
        .withColumn("primary_cloud", lit(None).cast("string"))
        .withColumn("recommendation_score", lit(None).cast("double"))
        .withColumn("overall_assessment", lit(None).cast("string"))
        # Raw
        .withColumn("result_json", to_json(col("result")))
    )

    # === PASS 2: Inferências ===
    pass2_pattern = str(BRONZE_DIR / "*" / "pass2-*.json")
    print(f"Lendo Pass2: {pass2_pattern}")

    df2 = spark.read.option("multiLine", True).json(pass2_pattern)
    df2 = (df2
        .withColumn("source_file", input_file_name())
        .withColumn("job_id", regexp_extract(col("source_file"), r"/bronze/([^/]+)/", 1).cast("long"))
        .withColumn("model_name", regexp_extract(col("source_file"), r"pass[0-9]+-(.*?)\.json", 1))
        .withColumn("pass_num", lit(2))
        # Metadata
        .withColumn("job_title", col("metadata.job_title"))
        .withColumn("company_name", col("metadata.company_name"))
        .withColumn("job_location", col("metadata.job_location"))
        # Tokens (pass2 usa result.tokens)
        .withColumn("tokens", col("result.tokens").cast("int"))
        .withColumn("cost", col("result.cost"))
        # Pass1 específicos (null)
        .withColumn("salary_min", lit(None).cast("double"))
        .withColumn("salary_max", lit(None).cast("double"))
        .withColumn("salary_currency", lit(None).cast("string"))
        .withColumn("work_model", lit(None).cast("string"))
        .withColumn("contract_type", lit(None).cast("string"))
        .withColumn("years_experience_min", lit(None).cast("double"))
        .withColumn("education_level", lit(None).cast("string"))
        .withColumn("must_have_skills_json", lit(None).cast("string"))
        # Pass2 específicos
        .withColumn("seniority_level", col("result.inference.seniority_and_role.seniority_level.value"))
        .withColumn("primary_cloud", col("result.inference.stack_and_cloud.primary_cloud.value"))
        # Pass3 específicos (null)
        .withColumn("recommendation_score", lit(None).cast("double"))
        .withColumn("overall_assessment", lit(None).cast("string"))
        # Raw
        .withColumn("result_json", to_json(col("result")))
    )

    # === PASS 3: Análise ===
    pass3_pattern = str(BRONZE_DIR / "*" / "pass3-*.json")
    print(f"Lendo Pass3: {pass3_pattern}")

    df3 = spark.read.option("multiLine", True).json(pass3_pattern)
    df3 = (df3
        .withColumn("source_file", input_file_name())
        .withColumn("job_id", regexp_extract(col("source_file"), r"/bronze/([^/]+)/", 1).cast("long"))
        .withColumn("model_name", regexp_extract(col("source_file"), r"pass[0-9]+-(.*?)\.json", 1))
        .withColumn("pass_num", lit(3))
        # Metadata
        .withColumn("job_title", col("metadata.job_title"))
        .withColumn("company_name", col("metadata.company_name"))
        .withColumn("job_location", col("metadata.job_location"))
        # Tokens
        .withColumn("tokens", col("result.tokens").cast("int"))
        .withColumn("cost", col("result.cost"))
        # Pass1 específicos (null)
        .withColumn("salary_min", lit(None).cast("double"))
        .withColumn("salary_max", lit(None).cast("double"))
        .withColumn("salary_currency", lit(None).cast("string"))
        .withColumn("work_model", lit(None).cast("string"))
        .withColumn("contract_type", lit(None).cast("string"))
        .withColumn("years_experience_min", lit(None).cast("double"))
        .withColumn("education_level", lit(None).cast("string"))
        .withColumn("must_have_skills_json", lit(None).cast("string"))
        # Pass2 específicos (null)
        .withColumn("seniority_level", lit(None).cast("string"))
        .withColumn("primary_cloud", lit(None).cast("string"))
        # Pass3 específicos
        # Os modelos têm schemas muito diferentes para recommendation_score e overall_assessment
        # Vamos extrair via get_json_object do result_json para evitar conflitos de tipo
        .withColumn("result_json", to_json(col("result")))
        # recommendation_score pode ser número direto ou objeto {value:...}
        # Usamos regex para extrair o valor - funciona para ambos os casos:
        # - Número direto: "recommendation_score": 0.78 -> captura 0.78
        # - Objeto: "value": 0.82 -> captura 0.82
        .withColumn("_rec_score_raw", get_json_object(col("result_json"), "$.summary.recommendation_score"))
        # regexp_extract retorna '' quando não há match, precisamos converter para null
        .withColumn("_rec_from_obj", regexp_extract(col("_rec_score_raw"), r'"value"\s*:\s*([0-9.]+)', 1))
        .withColumn("_rec_from_num", regexp_extract(col("_rec_score_raw"), r'^([0-9.]+)$', 1))
        .withColumn("recommendation_score",
            when(col("_rec_from_obj") != "", col("_rec_from_obj").cast("double"))
            .when(col("_rec_from_num") != "", col("_rec_from_num").cast("double"))
            .otherwise(lit(None).cast("double"))
        )
        .withColumn("overall_assessment", get_json_object(col("result_json"), "$.summary.overall_assessment"))
        .drop("_rec_score_raw", "_rec_from_obj", "_rec_from_num")
    )

    # === UNION: Seleciona apenas colunas comuns ===
    print("Fazendo UNION dos 3 passes...")
    df = df1.select(COLUMNS).union(df2.select(COLUMNS)).union(df3.select(COLUMNS))

    print("Schema da Silver (pré-write):")
    df.printSchema()

    # === SALVAR ===
    delta_path = "file://" + str(DELTA_SILVER_PATH)

    (
        df.write
        .format("delta")
        .mode("overwrite")
        .partitionBy("model_name", "pass_num")
        .save(delta_path)
    )

    print(f"Silver Delta criada em: {delta_path}")

    # Registrar como tabela no catálogo Spark
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS ai_enriched_jobs
        USING DELTA
        LOCATION '{delta_path}'
        """
    )

    # Verificar dados
    print("\nAmostra dos dados:")
    spark.sql("""
        SELECT job_id, model_name, pass_num, job_title,
               salary_min, seniority_level, recommendation_score
        FROM ai_enriched_jobs
        ORDER BY job_id, model_name, pass_num
        LIMIT 15
    """).show(truncate=False)

    # Contagem por pass
    print("\nContagem por pass:")
    spark.sql("""
        SELECT pass_num, COUNT(*) as count
        FROM ai_enriched_jobs
        GROUP BY pass_num
        ORDER BY pass_num
    """).show()

    spark.stop()


if __name__ == "__main__":
    run_bronze_to_silver_enriched_jobs()
