from pyspark.sql.functions import col, expr, array, concat, lit
from pyspark.ml.fpm import FPGrowth
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.clustering import KMeans

from .config import (
    FP_MIN_SUPPORT, FP_MIN_CONFIDENCE,
    KMEANS_K, KMEANS_SEED, PROXIMITY_THRESHOLD_KM,
)


def run_fp_growth(df_categorized, min_support=None, min_confidence=None):
    """Run FP-Growth on crime data with proximity categories.

    Expects a DataFrame with columns: offense_description, near_police, near_transport.
    Returns (freq_itemsets, association_rules).
    """
    min_support = min_support or FP_MIN_SUPPORT
    min_confidence = min_confidence or FP_MIN_CONFIDENCE

    transactions = df_categorized.select(
        array(
            concat(lit("TIPO="), col("offense_description")),
            col("near_police"),
            col("near_transport"),
        ).alias("items")
    )

    fp = FPGrowth(
        itemsCol="items",
        minSupport=min_support,
        minConfidence=min_confidence,
    )
    model = fp.fit(transactions)

    return model.freqItemsets, model.associationRules


def run_kmeans(df_geo, k=None, seed=None):
    """Run K-Means clustering on crime locations.

    Expects a DataFrame with longitude/latitude columns (double type).
    Returns (model, predictions).
    """
    k = k or KMEANS_K
    seed = seed or KMEANS_SEED

    assembler = VectorAssembler(
        inputCols=["longitude", "latitude"],
        outputCol="features",
    )
    dataset = assembler.transform(df_geo)

    kmeans = KMeans(k=k, seed=seed)
    model = kmeans.fit(dataset)
    predictions = model.transform(dataset)

    return model, predictions


def compute_spatial_distances(spark, df_crimes_geo, df_police_geo, df_transport_geo):
    """Compute distance from each crime to nearest police and transport station.

    All DataFrames must have a 'geometry' column (Sedona ST_Point).
    Returns a DataFrame with dist_to_nearest_police_km and dist_to_nearest_transport_km.
    """
    df_crimes_geo.createOrReplaceTempView("crimes_ny")
    df_police_geo.createOrReplaceTempView("police_stations")
    df_transport_geo.createOrReplaceTempView("transport_stations")

    # Distance to nearest police station
    df_police_dist = spark.sql("""
        SELECT
            c.complaint_id,
            c.offense_description,
            c.latitude AS crime_lat,
            c.longitude AS crime_lon,
            MIN(ST_Distance(c.geometry, p.geometry) * 111.32) AS dist_to_nearest_police_km,
            c.geometry AS crime_geom
        FROM crimes_ny c
        CROSS JOIN police_stations p
        GROUP BY c.complaint_id, c.offense_description, c.latitude, c.longitude, c.geometry
    """)
    df_police_dist.createOrReplaceTempView("crimes_with_police_dist")

    # Distance to nearest transport station
    df_distances = spark.sql("""
        SELECT
            c.complaint_id,
            c.offense_description,
            c.crime_lat,
            c.crime_lon,
            c.dist_to_nearest_police_km,
            MIN(ST_Distance(c.crime_geom, t.geometry) * 111.32) AS dist_to_nearest_transport_km,
            c.crime_geom
        FROM crimes_with_police_dist c
        CROSS JOIN transport_stations t
        GROUP BY c.complaint_id, c.offense_description, c.crime_lat, c.crime_lon,
                 c.dist_to_nearest_police_km, c.crime_geom
    """)

    return df_distances


def categorize_proximity(df_distances, threshold_km=None):
    """Add near_police / near_transport categorical columns."""
    threshold_km = threshold_km or PROXIMITY_THRESHOLD_KM

    return (
        df_distances
        .withColumn(
            "near_police",
            expr(f"CASE WHEN dist_to_nearest_police_km < {threshold_km} "
                 f"THEN 'CERCA_POLICIA' ELSE 'LEJOS_POLICIA' END")
        )
        .withColumn(
            "near_transport",
            expr(f"CASE WHEN dist_to_nearest_transport_km < {threshold_km} "
                 f"THEN 'CERCA_TRANSPORTE' ELSE 'LEJOS_TRANSPORTE' END")
        )
    )
