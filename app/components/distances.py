"""
Shared geospatial distance utilities used across multiple dashboard pages.

Provides vectorized Haversine computation via numpy so that nearest-station
distance can be computed efficiently on sampled DataFrames without resorting
to expensive cross-joins.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import streamlit as st


def haversine_np(
    lat1: np.ndarray,
    lon1: np.ndarray,
    lat2: np.ndarray,
    lon2: np.ndarray,
) -> np.ndarray:
    """Vectorized Haversine distance in meters. All inputs in decimal degrees.

    Supports broadcasting: lat1/lon1 can be (n, 1) and lat2/lon2 (1, m) to
    produce an (n, m) distance matrix in one call.

    Args:
        lat1, lon1: Coordinates of the first set of points.
        lat2, lon2: Coordinates of the second set of points.

    Returns:
        Distances in meters, same shape as the broadcast result.
    """
    r = 6_371_000.0
    lat1_r, lat2_r = np.radians(lat1), np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2) ** 2
    return r * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def nearest_distances(
    crime_lats: np.ndarray,
    crime_lons: np.ndarray,
    station_lats: np.ndarray,
    station_lons: np.ndarray,
    *,
    chunk_size: int = 2_000,
) -> np.ndarray:
    """For each crime, return the distance to the nearest station in meters.

    Processes crimes in chunks so the transient (chunk x n_stations) distance
    matrix stays small. A single full (n_crimes x n_stations) broadcast would
    allocate several arrays of that size at once — with large layers such as the
    ~17.5k MTA bus stops and tens of thousands of crimes that peaks at tens of GB
    and OOMs. Chunking bounds peak memory while giving identical results.

    Args:
        crime_lats, crime_lons: 1-D arrays of crime coordinates.
        station_lats, station_lons: 1-D arrays of station coordinates.
        chunk_size: Number of crimes processed per broadcast block.

    Returns:
        1-D numpy array of shape (n_crimes,) with distances in meters.
    """
    c_lats = np.asarray(crime_lats, dtype=np.float64)
    c_lons = np.asarray(crime_lons, dtype=np.float64)
    s_lats = np.asarray(station_lats, dtype=np.float64)
    s_lons = np.asarray(station_lons, dtype=np.float64)

    n = c_lats.shape[0]
    out = np.empty(n, dtype=np.float64)
    if n == 0 or s_lats.shape[0] == 0:
        out.fill(np.nan)
        return out

    for start in range(0, n, chunk_size):
        end = min(start + chunk_size, n)
        block = haversine_np(
            c_lats[start:end, None],
            c_lons[start:end, None],
            s_lats[None, :],
            s_lons[None, :],
        )
        out[start:end] = block.min(axis=1)
    return out


@st.cache_data(ttl=3600, show_spinner="Calculando distancias...")
def compute_nearest_distances(
    crime_lats: tuple[float, ...],
    crime_lons: tuple[float, ...],
    station_lats: tuple[float, ...],
    station_lons: tuple[float, ...],
) -> np.ndarray:
    """Cached wrapper over :func:`nearest_distances` taking hashable tuples.

    Args:
        crime_lats, crime_lons: Tuples of crime coordinates (hashable for cache).
        station_lats, station_lons: Tuples of station coordinates.

    Returns:
        1-D numpy array of shape (n_crimes,) with distances in meters.
    """
    return nearest_distances(
        np.array(crime_lats),
        np.array(crime_lons),
        np.array(station_lats),
        np.array(station_lons),
    )


def add_distance_column(
    df: pl.DataFrame,
    stations_df: pl.DataFrame,
    *,
    col_name: str = "dist_m",
    sample_n: int | None = None,
    seed: int = 42,
) -> pl.DataFrame:
    """Add a distance-to-nearest-station column to a crime DataFrame.

    Args:
        df: Crime DataFrame with ``latitude`` and ``longitude`` columns.
        stations_df: Station DataFrame with ``lat`` and ``lon`` columns.
        col_name: Name of the new distance column (in meters).
        sample_n: If provided, sample this many rows before computing.
        seed: Random seed for reproducible sampling.

    Returns:
        DataFrame (or sample) with the new distance column appended.
    """
    work = df.filter(pl.col("latitude").is_not_null() & pl.col("longitude").is_not_null())
    if sample_n is not None and len(work) > sample_n:
        work = work.sample(n=sample_n, seed=seed)

    distances = compute_nearest_distances(
        tuple(work["latitude"].to_list()),
        tuple(work["longitude"].to_list()),
        tuple(stations_df["lat"].to_list()),
        tuple(stations_df["lon"].to_list()),
    )

    return work.with_columns(pl.Series(col_name, distances))
