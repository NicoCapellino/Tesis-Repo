"""
Transformation and normalization of raw NYPD complaint data.

Reads raw Parquet files (as-downloaded from Socrata with all-string columns),
renames cryptic column names to descriptive ones, casts data types, cleans
null placeholders, and derives useful temporal features.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from config.settings import PROCESSED_DIR, RAW_DIR
from src.utils.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Column renaming map: Socrata raw name → clean descriptive name
# ---------------------------------------------------------------------------
COLUMN_MAPPING: dict[str, str] = {
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
    # Date / Time
    "cmplnt_fr_dt": "crime_start_date",
    "cmplnt_fr_tm": "crime_start_time",
    "cmplnt_to_dt": "crime_end_date",
    "cmplnt_to_tm": "crime_end_time",
    "rpt_dt": "report_date",
    # Crime classification
    "crm_atpt_cptd_cd": "crime_status",
    "jurisdiction_code": "jurisdiction_code",
    "juris_desc": "jurisdiction_description",
    "ky_cd": "offense_key_code",
    "law_cat_cd": "offense_level",
    "ofns_desc": "offense_description",
    "pd_cd": "internal_code",
    "pd_desc": "internal_description",
    # Suspect info
    "susp_age_group": "suspect_age_group",
    "susp_race": "suspect_race",
    "susp_sex": "suspect_sex",
    # Victim info
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

# Columns to keep in the final processed output (ordered).
OUTPUT_COLUMNS: list[str] = [
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
    # Derived temporal features
    "year",
    "month",
    "day_of_week",
    "hour",
]

# Valid NYPD age-group bins. Anything else — numeric junk like "-968", "1023",
# "2021" — is a data-entry error and is nulled out during transformation.
VALID_AGE_GROUPS: frozenset[str] = frozenset({"<18", "18-24", "25-44", "45-64", "65+"})

# Valid NYPD sex codes. The victim field doubles as a victim-type field, so it
# also allows non-person entities: D = Business/Organization, E = PSNY/People of
# the State of NY (used for victimless/public-order crimes). Suspects are always
# a person or unknown. Anything outside these sets (e.g. the stray "L") is junk.
VALID_VICTIM_SEX: frozenset[str] = frozenset({"M", "F", "D", "E", "U"})
VALID_SUSPECT_SEX: frozenset[str] = frozenset({"M", "F", "U"})

# A crime's end date more than this many years after its start is treated as a
# data-entry error (real absurd values seen: years 1010 and 2052).
MAX_CRIME_SPAN_YEARS = 10


class ComplaintsTransformer:
    """Transforms raw NYPD complaint data into clean, typed, analysis-ready format.

    Usage::

        transformer = ComplaintsTransformer()
        clean_df = transformer.transform(raw_df)
        # or from files:
        transformer.transform_and_save()
    """

    def transform(self, df: pl.DataFrame) -> pl.DataFrame:
        """Apply the full transformation pipeline to a raw DataFrame.

        Steps:
            1. Rename columns to descriptive names.
            2. Cast data types (coordinates, dates, numeric codes).
            3. Clean null placeholders (``"(null)"``, ``"UNKNOWN"``).
            4. Null out invalid victim/suspect age groups.
            5. Null out invalid victim/suspect sex codes.
            6. Null out corrupt crime end dates (before start / absurd year).
            7. Derive temporal features (year, month, day_of_week, hour).
            8. Select and order final output columns.

        Args:
            df: Raw DataFrame with Socrata column names (all strings).

        Returns:
            Cleaned and normalized DataFrame.
        """
        log.info("transform_start", input_rows=len(df), input_cols=len(df.columns))

        df = self._rename_columns(df)
        df = self._cast_types(df)
        df = self._clean_nulls(df)
        df = self._clean_ages(df)
        df = self._clean_sex(df)
        df = self._clean_end_dates(df)
        df = self._derive_temporal_features(df)
        df = self._select_output_columns(df)

        log.info("transform_complete", output_rows=len(df), output_cols=len(df.columns))
        return df

    def transform_and_save(
        self,
        *,
        input_dir: Path | None = None,
        output_dir: Path | None = None,
    ) -> Path:
        """Read raw Parquets, transform, and save as processed Parquets.

        Args:
            input_dir: Directory with raw Parquet files.
                Defaults to ``data/raw/complaints/``.
            output_dir: Directory for processed output.
                Defaults to ``data/processed/complaints/``.

        Returns:
            Path to the output directory.
        """
        input_dir = input_dir or RAW_DIR / "complaints"
        output_dir = output_dir or PROCESSED_DIR / "complaints"
        output_dir.mkdir(parents=True, exist_ok=True)

        parquet_files = sorted(input_dir.glob("*.parquet"))
        if not parquet_files:
            log.warning("no_raw_files_found", path=str(input_dir))
            return output_dir

        log.info("reading_raw_files", count=len(parquet_files))
        df = pl.concat(
            [pl.read_parquet(f) for f in parquet_files],
            how="diagonal_relaxed",
        )

        df_clean = self.transform(df)

        # Save partitioned by year
        if "year" in df_clean.columns:
            for year_val in df_clean["year"].unique().sort().to_list():
                if year_val is None:
                    continue
                year_df = df_clean.filter(pl.col("year") == year_val)
                out_path = output_dir / f"complaints_{year_val}.parquet"
                year_df.write_parquet(out_path, compression="zstd")
                log.info("saved_processed_year", year=year_val, records=len(year_df))
        else:
            out_path = output_dir / "complaints.parquet"
            df_clean.write_parquet(out_path, compression="zstd")

        return output_dir

    # ------------------------------------------------------------------
    # Transformation steps
    # ------------------------------------------------------------------

    @staticmethod
    def _rename_columns(df: pl.DataFrame) -> pl.DataFrame:
        """Rename Socrata's cryptic column names to descriptive ones."""
        # Socrata sometimes returns lowercase, sometimes mixed case
        current_cols = {c.lower(): c for c in df.columns}
        rename_map: dict[str, str] = {}

        for raw_name, clean_name in COLUMN_MAPPING.items():
            actual_col = current_cols.get(raw_name.lower())
            if actual_col is not None:
                rename_map[actual_col] = clean_name

        return df.rename(rename_map)

    @staticmethod
    def _cast_types(df: pl.DataFrame) -> pl.DataFrame:
        """Cast columns to their proper data types."""
        expressions: list[pl.Expr] = []

        # Coordinates → Float64
        for col_name in ("latitude", "longitude"):
            if col_name in df.columns:
                expressions.append(pl.col(col_name).cast(pl.Float64, strict=False).alias(col_name))

        # Integer coordinate system (NY State Plane)
        for col_name in ("x_coordinate", "y_coordinate"):
            if col_name in df.columns:
                expressions.append(pl.col(col_name).cast(pl.Int32, strict=False).alias(col_name))

        # Numeric codes
        for col_name in ("precinct_code", "jurisdiction_code", "offense_key_code", "internal_code"):
            if col_name in df.columns:
                expressions.append(pl.col(col_name).cast(pl.Int32, strict=False).alias(col_name))

        # Dates - Socrata format: "2024-12-13T00:00:00.000"
        for col_name in ("crime_start_date", "crime_end_date", "report_date"):
            if col_name in df.columns:
                expressions.append(
                    pl.col(col_name)
                    .str.slice(0, 10)
                    .str.to_date("%Y-%m-%d", strict=False)
                    .alias(col_name)
                )

        if expressions:
            df = df.with_columns(expressions)

        return df

    @staticmethod
    def _clean_nulls(df: pl.DataFrame) -> pl.DataFrame:
        """Replace sentinel null values with actual nulls."""
        null_sentinels = ["(null)", "UNKNOWN", "null", "NULL", ""]

        string_cols = [c for c in df.columns if df[c].dtype == pl.Utf8]
        if string_cols:
            df = df.with_columns(
                pl.when(pl.col(c).is_in(null_sentinels)).then(None).otherwise(pl.col(c)).alias(c)
                for c in string_cols
            )

        return df

    @staticmethod
    def _clean_ages(df: pl.DataFrame) -> pl.DataFrame:
        """Null out invalid victim/suspect age groups.

        NYPD age fields sometimes contain data-entry garbage (e.g. ``"-968"``,
        ``"1023"``, ``"2021"``). Only the canonical bins are kept; everything
        else becomes null so those records are excluded from age-based analysis
        while the crime itself is preserved.
        """
        age_cols = [c for c in ("victim_age_group", "suspect_age_group") if c in df.columns]
        if age_cols:
            df = df.with_columns(
                pl.when(pl.col(c).is_in(list(VALID_AGE_GROUPS)))
                .then(pl.col(c))
                .otherwise(None)
                .alias(c)
                for c in age_cols
            )
        return df

    @staticmethod
    def _clean_sex(df: pl.DataFrame) -> pl.DataFrame:
        """Null out invalid victim/suspect sex codes.

        Keeps the documented NYPD codes (persons M/F, unknown U, and — for
        victims only — the entity types D/E). Junk such as the stray ``"L"``
        becomes null so it is excluded from demographic breakdowns.
        """
        specs = [("victim_sex", VALID_VICTIM_SEX), ("suspect_sex", VALID_SUSPECT_SEX)]
        exprs = [
            pl.when(pl.col(col).is_in(list(valid)))
            .then(pl.col(col))
            .otherwise(None)
            .alias(col)
            for col, valid in specs
            if col in df.columns
        ]
        if exprs:
            df = df.with_columns(exprs)
        return df

    @staticmethod
    def _clean_end_dates(df: pl.DataFrame) -> pl.DataFrame:
        """Null out corrupt ``crime_end_date`` values.

        An end date before the start date is impossible, and one more than
        ``MAX_CRIME_SPAN_YEARS`` after the start is implausible (real data had
        years like 1010 and 2052). Such values are nulled; the record is kept.
        """
        if "crime_end_date" not in df.columns or "crime_start_date" not in df.columns:
            return df

        start = pl.col("crime_start_date")
        end = pl.col("crime_end_date")
        invalid = (end < start) | (end.dt.year() > start.dt.year() + MAX_CRIME_SPAN_YEARS)
        return df.with_columns(
            pl.when(invalid).then(None).otherwise(end).alias("crime_end_date")
        )

    @staticmethod
    def _derive_temporal_features(df: pl.DataFrame) -> pl.DataFrame:
        """Derive year, month, day_of_week, and hour from date/time columns."""
        expressions: list[pl.Expr] = []

        if "crime_start_date" in df.columns:
            expressions.extend(
                [
                    pl.col("crime_start_date").dt.year().alias("year"),
                    pl.col("crime_start_date").dt.month().alias("month"),
                    pl.col("crime_start_date").dt.weekday().alias("day_of_week"),
                ]
            )

        if "crime_start_time" in df.columns:
            expressions.append(
                pl.col("crime_start_time")
                .str.slice(0, 2)
                .cast(pl.Int32, strict=False)
                .alias("hour")
            )

        if expressions:
            df = df.with_columns(expressions)

        return df

    @staticmethod
    def _select_output_columns(df: pl.DataFrame) -> pl.DataFrame:
        """Select and order the final output columns."""
        available = [c for c in OUTPUT_COLUMNS if c in df.columns]
        return df.select(available)
