from pyspark.sql import SparkSession
from delta import configure_spark_with_delta_pip

def get_spark(app_name: str = "DeltaLocal"):
    builder = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        # Delta configs
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )

    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    return spark
