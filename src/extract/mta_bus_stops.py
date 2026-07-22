"""
Extraction of MTA bus stops from NY State Open Data (Socrata SODA API).

Downloads every MTA bus stop and reduces it to unique physical stops within
New York City, for use as a transit-proximity reference layer alongside the
USGS V2 police, fire, and healthcare layers.

Source: https://data.ny.gov/Transportation/MTA-Bus-Stops/2ucp-7wg5 (data.ny.gov)

The raw dataset is at stop×route×direction granularity (~3.1M rows). We collapse
it to one row per ``stop_id`` server-side via a grouped SoQL query and filter to
the NYC bounding box, so a single request returns the ~17.5k unique NYC stops.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import polars as pl
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import (
    CITY_CONFIGS,
    MTA_BUS_STOPS,
    REFERENCE_DIR,
    PipelineSettings,
)
from src.utils.logging import get_logger

log = get_logger(__name__)

# Normalized schema — mirrors the USGS V2 layers so the dashboard reference-layer
# helpers (distances, maps) can consume every layer uniformly.
OUTPUT_COLUMNS = ["name", "lat", "lon", "facility_type", "stop_id"]
FACILITY_TYPE = "Bus Stop"

# Empty-result schema, so an empty response returns a typed frame instead of crashing.
_EMPTY_SCHEMA: dict[str, pl.DataType] = {
    "name": pl.Utf8,
    "lat": pl.Float64,
    "lon": pl.Float64,
    "facility_type": pl.Utf8,
    "stop_id": pl.Utf8,
}


class MTABusStopsExtractor:
    """Downloads MTA bus stops and reduces them to unique NYC stops.

    Usage::

        extractor = MTABusStopsExtractor()
        df = extractor.extract("new_york")
        # or
        extractor.extract_and_save("new_york")
    """

    def __init__(self, settings: PipelineSettings | None = None) -> None:
        self.settings = settings or PipelineSettings()
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=httpx.Timeout(self.settings.request_timeout_seconds),
                follow_redirects=True,
            )
        return self._client

    def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            self._client.close()

    def __enter__(self) -> MTABusStopsExtractor:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, city: str) -> pl.DataFrame:
        """Fetch unique MTA bus stops within the given city's bounding box.

        Returns a DataFrame with columns ``name``, ``lat``, ``lon``,
        ``facility_type``, ``stop_id`` — matching the shape consumed by the
        dashboard reference-layer helpers.
        """
        log.info("mta_fetch_start", city=city)
        rows = self._fetch_stops(city)
        df = self._normalize(rows, city)
        log.info("mta_fetch_done", city=city, records=len(df))
        return df

    def extract_and_save(
        self,
        city: str,
        output_dir: Path | None = None,
    ) -> Path:
        """Fetch NYC bus stops and save as ``mta_bus_stops.parquet``.

        Args:
            city: City key (currently only ``"new_york"`` is supported).
            output_dir: Output directory. Defaults to ``data/reference/{city}/``.

        Returns:
            Path to the saved Parquet file.
        """
        output_dir = output_dir or REFERENCE_DIR / city
        output_dir.mkdir(parents=True, exist_ok=True)

        df = self.extract(city)
        out_path = output_dir / "mta_bus_stops.parquet"
        df.write_parquet(out_path, compression="zstd")
        log.info("saved_mta_bus_stops", records=len(df), path=str(out_path))
        return out_path

    # ------------------------------------------------------------------
    # HTTP fetch
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        reraise=True,
    )
    def _fetch_stops(self, city: str) -> list[dict[str, object]]:
        """Query Socrata for stops grouped by ``stop_id`` within the NYC bbox.

        The grouped SoQL query collapses stop×route×direction rows to one row
        per physical stop, so a single request returns the full set of stops.
        Aggregate aliases must differ from the source column names (``lat`` not
        ``latitude``); otherwise Socrata resolves the WHERE filter to the
        aggregate and rejects the query.
        """
        min_lat, min_lon, max_lat, max_lon = CITY_CONFIGS[city].bbox
        params = {
            "$select": "stop_id, min(stop_name) as name, min(latitude) as lat, min(longitude) as lon",
            "$where": (
                f"latitude between {min_lat} and {max_lat} "
                f"and longitude between {min_lon} and {max_lon}"
            ),
            "$group": "stop_id",
            "$limit": str(self.settings.page_size),
        }
        client = self._get_client()
        response = client.get(MTA_BUS_STOPS.json_endpoint, params=params)
        response.raise_for_status()
        rows = response.json()
        log.info("mta_response", returned=len(rows))
        if len(rows) >= self.settings.page_size:
            log.warning(
                "mta_possible_truncation",
                returned=len(rows),
                limit=self.settings.page_size,
                message="Returned rows hit the page limit; consider paginating.",
            )
        return rows

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize(self, rows: list[dict[str, object]], city: str) -> pl.DataFrame:
        """Cast types, filter to NYC bbox, dedupe by stop_id, add facility_type.

        The bbox filter and stop_id dedupe are also enforced server-side, but we
        repeat them here so the extractor stays correct even if the raw payload
        changes — mirroring the USGS extractor's client-side ``_filter_nyc``.
        """
        if not rows:
            return pl.DataFrame(schema=_EMPTY_SCHEMA)

        df = pl.DataFrame(rows).with_columns(
            [
                pl.col("name").cast(pl.Utf8),
                pl.col("lat").cast(pl.Float64, strict=False),
                pl.col("lon").cast(pl.Float64, strict=False),
                pl.col("stop_id").cast(pl.Utf8),
            ]
        )

        before = len(df)
        min_lat, min_lon, max_lat, max_lon = CITY_CONFIGS[city].bbox
        df = (
            df.filter(pl.col("lat").is_not_null() & pl.col("lon").is_not_null())
            .filter(
                pl.col("lat").is_between(min_lat, max_lat)
                & pl.col("lon").is_between(min_lon, max_lon)
            )
            .unique(subset=["stop_id"], keep="first")
            .with_columns(pl.lit(FACILITY_TYPE).alias("facility_type"))
            .select(OUTPUT_COLUMNS)
            .sort("stop_id")
        )
        dropped = before - len(df)
        if dropped > 0:
            log.info("mta_normalize_filtered", kept=len(df), dropped=dropped)
        return df
