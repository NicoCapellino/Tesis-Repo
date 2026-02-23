from pyspark.sql import SparkSession


def get_or_create_spark(app_name="CrimeAnalysis"):
    """Return existing SparkSession or create a new one with Sedona config."""
    return (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config(
            "spark.jars.packages",
            "org.apache.sedona:sedona-spark-shaded-3.4_2.12:1.6.1"
        )
        .config(
            "spark.sql.extensions",
            "org.apache.sedona.sql.SedonaSqlExtensions"
        )
        .config(
            "spark.serializer",
            "org.apache.spark.serializer.KryoSerializer"
        )
        .config(
            "spark.kryo.registrator",
            "org.apache.sedona.core.serde.SedonaKryoRegistrator"
        )
        .getOrCreate()
    )
