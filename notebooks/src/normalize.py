from pyspark.sql.functions import col, to_date, year
from pyspark.sql.types import DoubleType, IntegerType

from .config import NY_CRIMES_RAW, NY_CRIMES_NORMALIZED

COLUMN_MAPPING = {
    # Identifiers
    "cmplnt_num": "complaint_id",
    "addr_pct_cd": "precinct_code",
    # Location
    "boro_nm": "borough",
    "hadevelopt": "housing_development",
    "housing_psa": "housing_psa",
    "parks_nm": "park_name",
    "patrol_boro": "patrol_borough",
    "prem_typ_desc": "premise_type",
    "loc_of_occur_desc": "location_type",
    "station_name": "station_name",
    "transit_district": "transit_district",
    # Date/Time
    "cmplnt_fr_dt": "crime_start_date",
    "cmplnt_fr_tm": "crime_start_time",
    "cmplnt_to_dt": "crime_end_date",
    "cmplnt_to_tm": "crime_end_time",
    "rpt_dt": "report_date",
    # Crime Classification
    "crm_atpt_cptd_cd": "crime_status",
    "jurisdiction_code": "jurisdiction_code",
    "juris_desc": "jurisdiction_description",
    "ky_cd": "offense_key_code",
    "law_cat_cd": "offense_level",
    "ofns_desc": "offense_description",
    "pd_cd": "internal_code",
    "pd_desc": "internal_description",
    # Suspect Info
    "susp_age_group": "suspect_age_group",
    "susp_race": "suspect_race",
    "susp_sex": "suspect_sex",
    # Victim Info
    "vic_age_group": "victim_age_group",
    "vic_race": "victim_race",
    "vic_sex": "victim_sex",
    # Coordinates
    "x_coord_cd": "x_coordinate",
    "y_coord_cd": "y_coordinate",
    "latitude": "latitude",
    "longitude": "longitude",
    "lat_lon": "lat_lon",
    "geocoded_column": "geometry_wkt",
}

COLUMNS_TO_KEEP = [
    "complaint_id",
    "precinct_code",
    "borough",
    "crime_start_date",
    "crime_start_time",
    "crime_end_date",
    "crime_end_time",
    "report_date",
    "crime_status",
    "jurisdiction_description",
    "offense_level",
    "offense_description",
    "internal_description",
    "premise_type",
    "location_type",
    "patrol_borough",
    "suspect_age_group",
    "suspect_race",
    "suspect_sex",
    "victim_age_group",
    "victim_race",
    "victim_sex",
    "latitude",
    "longitude",
    "year",
]


def normalize_ny_crimes(spark, input_path=None, output_path=None):
    """Load raw NY crime CSVs, normalize columns, and save as partitioned parquet.

    Returns the normalized DataFrame.
    """
    input_path = input_path or NY_CRIMES_RAW
    output_path = output_path or NY_CRIMES_NORMALIZED

    # Load all CSVs
    df = spark.read.option("header", True).csv(input_path + "/*.csv")
    total_raw = df.count()
    print(f"Loaded {total_raw:,} raw records from {input_path}")

    # Rename columns
    for old_name, new_name in COLUMN_MAPPING.items():
        if old_name in df.columns:
            df = df.withColumnRenamed(old_name, new_name)

    # Cast types
    df = (
        df
        .withColumn("latitude", col("latitude").cast(DoubleType()))
        .withColumn("longitude", col("longitude").cast(DoubleType()))
        .withColumn("x_coordinate", col("x_coordinate").cast(IntegerType()))
        .withColumn("y_coordinate", col("y_coordinate").cast(IntegerType()))
        .withColumn("precinct_code", col("precinct_code").cast(IntegerType()))
        .withColumn("jurisdiction_code", col("jurisdiction_code").cast(IntegerType()))
        .withColumn("offense_key_code", col("offense_key_code").cast(IntegerType()))
        .withColumn("internal_code", col("internal_code").cast(IntegerType()))
        .withColumn("crime_start_date", to_date(col("crime_start_date")))
        .withColumn("crime_end_date", to_date(col("crime_end_date")))
        .withColumn("report_date", to_date(col("report_date")))
    )

    # Clean null placeholders
    df = df.replace("(null)", None)
    df = df.replace("UNKNOWN", None)

    # Add year column
    df = df.withColumn("year", year(col("crime_start_date")))

    # Filter valid coordinates
    df_clean = (
        df
        .filter(col("latitude").isNotNull())
        .filter(col("longitude").isNotNull())
        .filter(col("latitude") != 0)
        .filter(col("longitude") != 0)
    )

    valid = df_clean.count()
    print(f"Valid coordinates: {valid:,} / {total_raw:,} ({100 * valid / total_raw:.1f}%)")

    # Select and save
    df_export = df_clean.select(COLUMNS_TO_KEEP)
    df_export.write.mode("overwrite").partitionBy("year").parquet(output_path)
    print(f"Saved normalized parquet to {output_path}")

    return df_export
