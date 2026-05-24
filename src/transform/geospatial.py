"""
Geospatial validation and utility functions.

Provides coordinate validation (filtering rows outside NYC bounding box)
and distance-based enrichment helpers for nearest infrastructure facilities.
"""

from __future__ import annotations

import math

import polars as pl

from config.settings import CITY_CONFIGS, DEFAULT_CITY
from src.utils.logging import get_logger

log = get_logger(__name__)


class GeospatialValidator:
    """Validates and enriches geospatial data.

    Usage::

        validator = GeospatialValidator()
        clean_df = validator.filter_valid_coordinates(crime_df)
        enriched = validator.add_nearest_station(crime_df, stations_df)
    """

    def __init__(self, city: str = DEFAULT_CITY) -> None:
        config = CITY_CONFIGS[city]
        self.bbox = config.bbox  # (min_lat, min_lon, max_lat, max_lon)

    def filter_valid_coordinates(self, df: pl.DataFrame) -> pl.DataFrame:
        """Remove rows with missing or out-of-bounds coordinates.

        Filters out:
        - Null latitude or longitude.
        - Zero coordinates (common placeholder).
        - Coordinates outside the city bounding box.

        Args:
            df: DataFrame with ``latitude`` and ``longitude`` columns.

        Returns:
            Filtered DataFrame with only valid coordinates.
        """
        min_lat, min_lon, max_lat, max_lon = self.bbox
        before = len(df)

        df = df.filter(
            pl.col("latitude").is_not_null()
            & pl.col("longitude").is_not_null()
            & (pl.col("latitude") != 0.0)
            & (pl.col("longitude") != 0.0)
            & (pl.col("latitude") >= min_lat)
            & (pl.col("latitude") <= max_lat)
            & (pl.col("longitude") >= min_lon)
            & (pl.col("longitude") <= max_lon)
        )

        after = len(df)
        removed = before - after
        if removed > 0:
            log.info(
                "coordinates_filtered",
                removed=removed,
                remaining=after,
                pct_removed=round(100 * removed / before, 2) if before > 0 else 0,
            )

        return df

    @staticmethod
    def haversine_distance(
        lat1: float, lon1: float, lat2: float, lon2: float,
    ) -> float:
        """Calculate the Haversine distance between two points in meters.

        Args:
            lat1, lon1: Coordinates of the first point (degrees).
            lat2, lon2: Coordinates of the second point (degrees).

        Returns:
            Distance in meters.
        """
        r = 6_371_000  # Earth radius in meters
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def add_nearest_station(
        self,
        crimes_df: pl.DataFrame,
        stations_df: pl.DataFrame,
        *,
        station_type: str = "police",
        max_distance_km: float = 50.0,
    ) -> pl.DataFrame:
        """Add nearest station distance and name to each crime record.

        Uses a cross-join + Haversine approach. For large datasets, consider
        calling this on a sample or pre-filtering by borough.

        Args:
            crimes_df: Crime DataFrame with ``latitude``, ``longitude``.
            stations_df: Station DataFrame with ``lat``, ``lon``, ``name``.
            station_type: Label for the output columns (e.g. ``"police"``).
            max_distance_km: Ignore stations farther than this.

        Returns:
            Crime DataFrame with two new columns:
            ``nearest_{station_type}_name`` and
            ``nearest_{station_type}_distance_m``.
        """
        log.info(
            "computing_nearest_station",
            station_type=station_type,
            crimes=len(crimes_df),
            stations=len(stations_df),
        )

        # For efficiency, compute using Polars expressions with a cross join
        # We add a temporary index to crimes for the join-back
        crimes_indexed = crimes_df.with_row_index("_crime_idx")

        # Cross join: every crime × every station
        cross = crimes_indexed.select("_crime_idx", "latitude", "longitude").join(
            stations_df.select("name", pl.col("lat").alias("s_lat"), pl.col("lon").alias("s_lon")),
            how="cross",
        )

        # Haversine approximation via Polars expressions
        cross = cross.with_columns(
            (
                6_371_000.0
                * 2
                * (
                    (
                        ((pl.col("s_lat") - pl.col("latitude")) * math.pi / 360).sin().pow(2)
                        + (pl.col("latitude") * math.pi / 180).cos()
                        * (pl.col("s_lat") * math.pi / 180).cos()
                        * ((pl.col("s_lon") - pl.col("longitude")) * math.pi / 360).sin().pow(2)
                    )
                    .sqrt()
                    .arcsin()
                )
            ).alias("_distance_m")
        )

        # Keep only the nearest station per crime
        nearest = (
            cross.filter(pl.col("_distance_m") <= max_distance_km * 1000)
            .sort("_distance_m")
            .group_by("_crime_idx")
            .first()
            .select(
                "_crime_idx",
                pl.col("name").alias(f"nearest_{station_type}_name"),
                pl.col("_distance_m")
                .round(1)
                .alias(f"nearest_{station_type}_distance_m"),
            )
        )

        result = crimes_indexed.join(nearest, on="_crime_idx", how="left").drop("_crime_idx")

        log.info("nearest_station_complete", station_type=station_type)
        return result
