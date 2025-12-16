from pathlib import Path
from pyspark.sql.functions import input_file_name, lit
from src.dev.deltalake.spark_session import get_spark

BASE_DIR = Path(__file__).resolve().parent.parent / "data" / "local" / "ai_enrichment"
BRONZE_DIR = BASE_DIR / "bronze"
DELTA_SILVER_PATH = BASE_DIR / "silver" / "delta" / "enriched_jobs"

def main():
    spark = get_spark("DeltaLocalTest")

    # 1) Ler todos os JSON de pass3 da bronze (ajusta o glob se quiser outro pass/modelo)
    bronze_pattern = str(BRONZE_DIR / "*" / "pass3-openai-gpt-oss-120b-1-0.json")
    print(f"Lendo arquivos: {bronze_pattern}")

    df = (
        spark.read
        .option("multiLine", True)   # se o JSON for "bonitinho" com quebras de linha
        .json(bronze_pattern)
        .withColumn("source_file", input_file_name())
    )

    # 2) Só pra inspecionar o schema
    df.printSchema()
    df.show(5, truncate=False)

    # 3) Gravar em Delta no HD local
    delta_path = "file://" + str(DELTA_SILVER_PATH)

    (
        df.write
        .format("delta")
        .mode("overwrite")   # depois vamos trocar pra 'append' ou 'merge'
        .save(delta_path)
    )

    print(f"Tabela Delta criada em: {delta_path}")

    # 4) Ler de volta como Delta pra conferir
    df_delta = spark.read.format("delta").load(delta_path)
    df_delta.show(5, truncate=False)

    spark.stop()

if __name__ == "__main__":
    main()
