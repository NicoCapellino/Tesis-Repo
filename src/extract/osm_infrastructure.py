"""
Extraction of urban infrastructure data from OpenStreetMap via Overpass API.

Downloads police stations and public transport stations for a given city
bounding box.  Supports failover across multiple Overpass mirrors.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx
import polars as pl

from config.settings import (
    CITY_CONFIGS,
    OVERPASS_URLS,
    REFERENCE_DIR,
    CityConfig,
    PipelineSettings,
)
from src.utils.logging import get_logger

log = get_logger(__name__)


class OSMInfrastructureExtractor:
    """Downloads infrastructure data (police, transport) from OpenStreetMap.

    Usage::

        extractor = OSMInfrastructureExtractor()
        police_df = extractor.extract_police_stations("new_york")
        transport_df = extractor.extract_transport_stations("new_york")
        extractor.extract_and_save_all("new_york")
    """

    def __init__(self, settings: PipelineSettings | None = None) -> None:
        self.settings = settings or PipelineSettings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_police_stations(self, city: str) -> pl.DataFrame:
        """Download police station locations for a city.

        Args:
            city: City key from ``CITY_CONFIGS`` (e.g. ``"new_york"``).

        Returns:
            DataFrame with columns: ``id``, ``type``, ``name``, ``lat``, ``lon``.
        """
        config = self._get_city_config(city)
        query = self._build_police_query(config.bbox)
        elements = self._query_overpass(query, city_name=city)
        return self._elements_to_police_df(elements)

    def extract_transport_stations(self, city: str) -> pl.DataFrame:
        """Download public transport station locations for a city.

        Args:
            city: City key from ``CITY_CONFIGS``.

        Returns:
            DataFrame with columns: ``id``, ``type``, ``transport_type``,
            ``name``, ``lat``, ``lon``.
        """
        config = self._get_city_config(city)
        query = self._build_transport_query(config.bbox)
        elements = self._query_overpass(query, city_name=city)
        return self._elements_to_transport_df(elements)

    def extract_and_save_all(
        self,
        city: str,
        output_dir: Path | None = None,
    ) -> dict[str, Path]:
        """Download and save both police and transport stations.

        Args:
            city: City key from ``CITY_CONFIGS``.
            output_dir: Output directory. Defaults to ``data/reference/{city}/``.

        Returns:
            Dictionary mapping data type to saved file path.
        """
        output_dir = output_dir or REFERENCE_DIR / city
        output_dir.mkdir(parents=True, exist_ok=True)
        saved: dict[str, Path] = {}

        # Police stations
        police_df = self.extract_police_stations(city)
        police_path = output_dir / "police_stations.parquet"
        police_df.write_parquet(police_path, compression="zstd")
        log.info("saved_police_stations", city=city, records=len(police_df), path=str(police_path))
        saved["police_stations"] = police_path

        # Transport stations
        transport_df = self.extract_transport_stations(city)
        transport_path = output_dir / "transport_stations.parquet"
        transport_df.write_parquet(transport_path, compression="zstd")
        log.info(
            "saved_transport_stations",
            city=city,
            records=len(transport_df),
            path=str(transport_path),
        )
        saved["transport_stations"] = transport_path

        return saved

    # ------------------------------------------------------------------
    # Overpass query builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_police_query(bbox: tuple[float, float, float, float]) -> str:
        min_lat, min_lon, max_lat, max_lon = bbox
        return f"""
        [out:json][timeout:90];
        (
          node["amenity"="police"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["amenity"="police"]({min_lat},{min_lon},{max_lat},{max_lon});
          relation["amenity"="police"]({min_lat},{min_lon},{max_lat},{max_lon});
        );
        out center;
        """

    @staticmethod
    def _build_transport_query(bbox: tuple[float, float, float, float]) -> str:
        min_lat, min_lon, max_lat, max_lon = bbox
        return f"""
        [out:json][timeout:90];
        (
          node["amenity"="bus_station"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["amenity"="bus_station"]({min_lat},{min_lon},{max_lat},{max_lon});
          relation["amenity"="bus_station"]({min_lat},{min_lon},{max_lat},{max_lon});
          node["railway"="station"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["railway"="station"]({min_lat},{min_lon},{max_lat},{max_lon});
          relation["railway"="station"]({min_lat},{min_lon},{max_lat},{max_lon});
          node["railway"="subway_entrance"]({min_lat},{min_lon},{max_lat},{max_lon});
          node["public_transport"="station"]({min_lat},{min_lon},{max_lat},{max_lon});
          way["public_transport"="station"]({min_lat},{min_lon},{max_lat},{max_lon});
        );
        out center;
        """

    # ------------------------------------------------------------------
    # Overpass HTTP with failover
    # ------------------------------------------------------------------

    def _query_overpass(self, query: str, *, city_name: str) -> list[dict[str, Any]]:
        """Execute an Overpass query with failover across mirrors.

        Tries each URL in :data:`OVERPASS_URLS` sequentially.  If all fail,
        raises :class:`RuntimeError`.
        """
        timeout = httpx.Timeout(self.settings.overpass_timeout)

        for url in OVERPASS_URLS:
            try:
                log.info("querying_overpass", url=url, city=city_name)
                with httpx.Client(timeout=timeout) as client:
                    response = client.get(url, params={"data": query})
                    response.raise_for_status()
                    data = response.json()

                elements = data.get("elements", [])
                log.info(
                    "overpass_success",
                    url=url,
                    elements=len(elements),
                )
                return elements

            except Exception:
                log.warning("overpass_mirror_failed", url=url, exc_info=True)
                time.sleep(2)

        raise RuntimeError(
            f"All Overpass mirrors failed for city '{city_name}'. "
            f"Tried: {OVERPASS_URLS}"
        )

    # ------------------------------------------------------------------
    # Data conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _elements_to_police_df(elements: list[dict[str, Any]]) -> pl.DataFrame:
        rows: list[dict[str, Any]] = []
        for el in elements:
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            if lat is None or lon is None:
                continue
            rows.append({
                "id": el.get("id"),
                "type": el.get("type"),
                "name": el.get("tags", {}).get("name", ""),
                "lat": float(lat),
                "lon": float(lon),
            })
        return pl.DataFrame(rows)

    @staticmethod
    def _elements_to_transport_df(elements: list[dict[str, Any]]) -> pl.DataFrame:
        rows: list[dict[str, Any]] = []
        for el in elements:
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            if lat is None or lon is None:
                continue

            tags = el.get("tags", {})

            if tags.get("amenity") == "bus_station":
                transport_type = "bus_station"
            elif tags.get("railway") == "station":
                transport_type = "train_station"
            elif tags.get("railway") == "subway_entrance":
                transport_type = "subway_entrance"
            elif tags.get("public_transport") == "station":
                transport_type = "public_transport_station"
            else:
                transport_type = "unknown"

            rows.append({
                "id": el.get("id"),
                "type": el.get("type"),
                "transport_type": transport_type,
                "name": tags.get("name", ""),
                "lat": float(lat),
                "lon": float(lon),
            })
        return pl.DataFrame(rows)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_city_config(city: str) -> CityConfig:
        if city not in CITY_CONFIGS:
            available = ", ".join(CITY_CONFIGS.keys())
            raise ValueError(
                f"Unknown city '{city}'. Available: {available}. "
                f"Add it to CITY_CONFIGS in config/settings.py."
            )
        return CITY_CONFIGS[city]
