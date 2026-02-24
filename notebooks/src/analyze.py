from pyspark.sql.functions import (
    col, expr, array, concat, lit,
    hour, dayofweek, month, count, avg, when,
    stddev, year as year_fn, round as spark_round,
)
from pyspark.sql import Window
from pyspark.ml.fpm import FPGrowth
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.clustering import KMeans

from .config import (
    FP_MIN_SUPPORT, FP_MIN_CONFIDENCE,
    KMEANS_K, KMEANS_SEED, PROXIMITY_THRESHOLD_KM,
    ANOMALY_STDDEV_THRESHOLD,
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


# ---------------------------------------------------------------------------
# Temporal Analysis
# ---------------------------------------------------------------------------

def add_temporal_columns(df):
    """Add hour, time_slot, day_of_week, and month columns from crime_start_date/time.

    Returns the enriched DataFrame.
    """
    df = df.withColumn("crime_hour", hour(col("crime_start_time")))
    df = df.withColumn("crime_day_of_week", dayofweek(col("crime_start_date")))
    df = df.withColumn("crime_month", month(col("crime_start_date")))

    # Time slot buckets: MADRUGADA (0-5), MANANA (6-11), TARDE (12-17), NOCHE (18-23)
    df = df.withColumn(
        "time_slot",
        when((col("crime_hour") >= 0) & (col("crime_hour") < 6), "MADRUGADA")
        .when((col("crime_hour") >= 6) & (col("crime_hour") < 12), "MANANA")
        .when((col("crime_hour") >= 12) & (col("crime_hour") < 18), "TARDE")
        .otherwise("NOCHE")
    )

    return df


def analyze_temporal_patterns(df):
    """Compute crime counts grouped by hour, day of week, and month.

    Expects a DataFrame already enriched with add_temporal_columns().
    Returns (crimes_by_hour, crimes_by_day, crimes_by_month, crimes_by_slot).
    """
    crimes_by_hour = (
        df.groupBy("crime_hour")
        .agg(count("*").alias("total_crimes"))
        .orderBy("crime_hour")
    )

    # dayofweek: 1=Sunday, 2=Monday, ..., 7=Saturday
    day_labels = {1: "Domingo", 2: "Lunes", 3: "Martes", 4: "Miercoles",
                  5: "Jueves", 6: "Viernes", 7: "Sabado"}
    crimes_by_day = (
        df.groupBy("crime_day_of_week")
        .agg(count("*").alias("total_crimes"))
        .orderBy("crime_day_of_week")
    )

    crimes_by_month = (
        df.groupBy("crime_month")
        .agg(count("*").alias("total_crimes"))
        .orderBy("crime_month")
    )

    crimes_by_slot = (
        df.groupBy("time_slot")
        .agg(count("*").alias("total_crimes"))
        .orderBy("total_crimes", ascending=False)
    )

    return crimes_by_hour, crimes_by_day, crimes_by_month, crimes_by_slot


def analyze_crime_type_by_time_slot(df):
    """Cross-tabulate crime type vs time slot.

    Returns a DataFrame with offense_description, time_slot, and total_crimes.
    """
    return (
        df.groupBy("offense_description", "time_slot")
        .agg(count("*").alias("total_crimes"))
        .orderBy("offense_description", "total_crimes", ascending=[True, False])
    )


# ---------------------------------------------------------------------------
# Expanded FP-Growth (with temporal and demographic features)
# ---------------------------------------------------------------------------

def run_fp_growth_expanded(df_categorized, min_support=None, min_confidence=None):
    """Run FP-Growth including time slot and demographic items.

    Expects a DataFrame with columns: offense_description, near_police,
    near_transport, time_slot, victim_sex, victim_age_group.
    Returns (freq_itemsets, association_rules).
    """
    min_support = min_support or FP_MIN_SUPPORT
    min_confidence = min_confidence or FP_MIN_CONFIDENCE

    # Build items array — only include non-null demographic values
    df_items = df_categorized.withColumn(
        "items",
        array(
            concat(lit("TIPO="), col("offense_description")),
            col("near_police"),
            col("near_transport"),
            concat(lit("HORARIO="), col("time_slot")),
        )
    )

    # Optionally append demographic items when available
    df_items = df_items.withColumn(
        "items",
        when(
            col("victim_sex").isNotNull(),
            expr("concat(items, array(concat('VICTIMA_SEXO=', victim_sex)))")
        ).otherwise(col("items"))
    ).withColumn(
        "items",
        when(
            col("victim_age_group").isNotNull(),
            expr("concat(items, array(concat('VICTIMA_EDAD=', victim_age_group)))")
        ).otherwise(col("items"))
    )

    transactions = df_items.select("items")

    fp = FPGrowth(
        itemsCol="items",
        minSupport=min_support,
        minConfidence=min_confidence,
    )
    model = fp.fit(transactions)

    return model.freqItemsets, model.associationRules


# ---------------------------------------------------------------------------
# Offense Level Breakdown
# ---------------------------------------------------------------------------

def analyze_offense_level(df):
    """Break down crimes by offense level (FELONY / MISDEMEANOR / VIOLATION).

    Returns (level_counts, level_by_borough, level_by_time_slot).
    Expects df enriched with add_temporal_columns() and having offense_level, borough columns.
    """
    level_counts = (
        df.groupBy("offense_level")
        .agg(count("*").alias("total_crimes"))
        .orderBy("total_crimes", ascending=False)
    )

    level_by_borough = (
        df.filter(col("borough").isNotNull())
        .groupBy("borough", "offense_level")
        .agg(count("*").alias("total_crimes"))
        .orderBy("borough", "total_crimes", ascending=[True, False])
    )

    level_by_time_slot = (
        df.filter(col("time_slot").isNotNull())
        .groupBy("time_slot", "offense_level")
        .agg(count("*").alias("total_crimes"))
        .orderBy("time_slot", "total_crimes", ascending=[True, False])
    )

    return level_counts, level_by_borough, level_by_time_slot


# ---------------------------------------------------------------------------
# Premise Type Analysis
# ---------------------------------------------------------------------------

def analyze_premise_type(df):
    """Analyze which premise types concentrate the most crimes.

    Returns (top_premises, premise_by_crime_type).
    """
    top_premises = (
        df.filter(col("premise_type").isNotNull())
        .groupBy("premise_type")
        .agg(count("*").alias("total_crimes"))
        .orderBy("total_crimes", ascending=False)
    )

    premise_by_crime_type = (
        df.filter(col("premise_type").isNotNull())
        .groupBy("premise_type", "offense_description")
        .agg(count("*").alias("total_crimes"))
        .orderBy("total_crimes", ascending=False)
    )

    return top_premises, premise_by_crime_type


# ---------------------------------------------------------------------------
# Anomaly Detection (statistical z-score based)
# ---------------------------------------------------------------------------

def detect_anomalies_by_borough_month(df, threshold=None):
    """Detect monthly crime count anomalies per borough using z-score method.

    A month is flagged as anomalous if its crime count deviates more than
    `threshold` standard deviations from the borough's mean.

    Returns (df_with_scores, df_anomalies).
    """
    threshold = threshold or ANOMALY_STDDEV_THRESHOLD

    monthly = (
        df.filter(col("borough").isNotNull())
        .withColumn("crime_year", year_fn(col("crime_start_date")))
        .withColumn("crime_month", month(col("crime_start_date")))
        .groupBy("borough", "crime_year", "crime_month")
        .agg(count("*").alias("crime_count"))
    )

    w = Window.partitionBy("borough")
    df_scored = (
        monthly
        .withColumn("borough_mean", avg("crime_count").over(w))
        .withColumn("borough_stddev", stddev("crime_count").over(w))
        .withColumn(
            "z_score",
            when(
                col("borough_stddev") > 0,
                spark_round(
                    (col("crime_count") - col("borough_mean")) / col("borough_stddev"), 2
                )
            ).otherwise(lit(0.0))
        )
        .withColumn("is_anomaly", expr(f"abs(z_score) > {threshold}"))
        .orderBy("borough", "crime_year", "crime_month")
    )

    df_anomalies = df_scored.filter(col("is_anomaly"))

    return df_scored, df_anomalies


def detect_anomalies_by_crime_type_month(df, threshold=None):
    """Detect monthly anomalies per crime type using z-score method.

    Returns (df_with_scores, df_anomalies).
    """
    threshold = threshold or ANOMALY_STDDEV_THRESHOLD

    monthly = (
        df.filter(col("offense_description").isNotNull())
        .withColumn("crime_year", year_fn(col("crime_start_date")))
        .withColumn("crime_month", month(col("crime_start_date")))
        .groupBy("offense_description", "crime_year", "crime_month")
        .agg(count("*").alias("crime_count"))
    )

    w = Window.partitionBy("offense_description")
    df_scored = (
        monthly
        .withColumn("type_mean", avg("crime_count").over(w))
        .withColumn("type_stddev", stddev("crime_count").over(w))
        .withColumn(
            "z_score",
            when(
                col("type_stddev") > 0,
                spark_round(
                    (col("crime_count") - col("type_mean")) / col("type_stddev"), 2
                )
            ).otherwise(lit(0.0))
        )
        .withColumn("is_anomaly", expr(f"abs(z_score) > {threshold}"))
        .orderBy("offense_description", "crime_year", "crime_month")
    )

    df_anomalies = df_scored.filter(col("is_anomaly"))

    return df_scored, df_anomalies
