"""
Centralized configuration for the NYC Crime Data Pipeline.

All API endpoints, file paths, and tunable parameters are defined here.
The architecture supports adding new cities by extending the CITY_CONFIGS dictionary.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REFERENCE_DIR = DATA_DIR / "reference"


# ---------------------------------------------------------------------------
# NYC Open Data (Socrata SODA API)
# ---------------------------------------------------------------------------
class SocrataDataset:
    """Descriptor for a single Socrata dataset."""

    def __init__(
        self,
        *,
        resource_id: str,
        base_url: str = "https://data.cityofnewyork.us/resource",
        date_column: str = "cmplnt_fr_dt",
        description: str = "",
    ) -> None:
        self.resource_id = resource_id
        self.base_url = base_url
        self.date_column = date_column
        self.description = description

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/{self.resource_id}.csv"


# Datasets we consume – adding a new one is a single line.
NYPD_DATASETS: dict[str, SocrataDataset] = {
    "historic": SocrataDataset(
        resource_id="qgea-i56i",
        description="NYPD Complaint Data Historic (all years)",
    ),
    "current_ytd": SocrataDataset(
        resource_id="5uac-w243",
        description="NYPD Complaint Data Current (Year To Date)",
    ),
}


# ---------------------------------------------------------------------------
# Overpass API (OpenStreetMap)
# ---------------------------------------------------------------------------
OVERPASS_URLS: list[str] = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


# ---------------------------------------------------------------------------
# City configurations – extensible for future cities
# ---------------------------------------------------------------------------
class CityConfig:
    """Geographical and dataset configuration for a city."""

    def __init__(
        self,
        *,
        name: str,
        display_name: str,
        bbox: tuple[float, float, float, float],  # (min_lat, min_lon, max_lat, max_lon)
        datasets: dict[str, SocrataDataset],
        default_center: tuple[float, float],
    ) -> None:
        self.name = name
        self.display_name = display_name
        self.bbox = bbox
        self.datasets = datasets
        self.default_center = default_center


CITY_CONFIGS: dict[str, CityConfig] = {
    "new_york": CityConfig(
        name="new_york",
        display_name="New York City",
        bbox=(40.49, -74.26, 40.92, -73.69),
        datasets=NYPD_DATASETS,
        default_center=(40.7128, -74.0060),
    ),
    # Future cities can be added here:
    # "chicago": CityConfig(name="chicago", ...),
    # "los_angeles": CityConfig(name="los_angeles", ...),
}

DEFAULT_CITY = "new_york"


# ---------------------------------------------------------------------------
# Pipeline settings (overridable via env vars)
# ---------------------------------------------------------------------------
class PipelineSettings(BaseSettings):
    """Runtime-tunable pipeline parameters.

    All values can be overridden via environment variables prefixed with
    ``NYC_PIPELINE_``.  Example: ``NYC_PIPELINE_PAGE_SIZE=20000``.
    """

    # Socrata pagination
    page_size: int = Field(
        default=50_000,
        description="Rows per API request (Socrata max is 50 000).",
    )
    max_retries: int = Field(
        default=5,
        description="Max retries per failed HTTP request.",
    )
    retry_wait_seconds: float = Field(
        default=2.0,
        description="Base wait between retries (exponential backoff).",
    )
    request_timeout_seconds: float = Field(
        default=120.0,
        description="HTTP request timeout in seconds.",
    )

    # Year range for extraction
    start_year: int = Field(default=2020, description="First year to extract.")
    end_year: int = Field(default=2025, description="Last year to extract (inclusive).")

    # Overpass
    overpass_timeout: int = Field(default=120, description="Overpass API timeout in seconds.")

    model_config = {"env_prefix": "NYC_PIPELINE_"}
