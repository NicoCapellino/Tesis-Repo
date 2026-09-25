"""
Extraction of urban infrastructure data from the USGS National Map via OGC WFS 2.0.

Downloads hospitals, police stations, and fire stations for New York City using
authoritative federal data (NSDI/OGC-compliant).

Service: https://carto-wfs.nationalmap.gov/arcgis/services/structures/MapServer/WFSServer
Standard: OGC WFS 2.0.0

FType codes used:
  800 = Hospitals / Medical Centers  → healthcare.parquet
  740 = Law Enforcement & Emergency  → usgs_police.parquet (FCode 74034)
                                     → usgs_fire.parquet   (FCode 74026)

Verified FCodes for NYC (from live WFS, May 2026):
  74034 = Police Station
  74026 = Fire Station
"""

from __future__ import annotations

# NOTA: Usamos xml.etree.ElementTree directamente porque la fuente (USGS)
# es un servicio federal confiable. En un entorno de produccion, se deberia
# usar defusedxml para prevenir ataques de entidad XML.
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
import polars as pl
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from config.settings import REFERENCE_DIR, PipelineSettings
from src.utils.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WFS_URL = "https://carto-wfs.nationalmap.gov/arcgis/services/structures/MapServer/WFSServer"
WFS_NS = "http://www.opengis.net/wfs/2.0"
GML_NS = "http://www.opengis.net/gml/3.2"

ATTR_FIELDS = ["NAME", "FType", "FCode", "ADDRESS", "CITY", "STATE", "ZIPCODE", "LOADDATE"]
OUTPUT_COLUMNS = [
    "name",
    "lat",
    "lon",
    "facility_type",
    "address",
    "zipcode",
    "borough",
    "fcode",
    "loaddate",
]
RENAME_COLUMNS = {
    "NAME": "name",
    "ADDRESS": "address",
    "ZIPCODE": "zipcode",
    "LOADDATE": "loaddate",
}

# ZIP prefix → NYC borough mapping (more reliable than CITY name)
NYC_ZIP_PREFIXES: dict[str, str] = {
    "100": "MANHATTAN",
    "101": "MANHATTAN",
    "102": "MANHATTAN",
    "103": "STATEN ISLAND",
    "104": "BRONX",
    "111": "QUEENS",
    "112": "BROOKLYN",
    "113": "QUEENS",
    "114": "QUEENS",
    "116": "QUEENS",
}

# FCode → human-readable facility_type for healthcare
HEALTHCARE_FCODE_MAP: dict[str, str] = {
    "80010": "Hospital",
    "80011": "Medical Center",
    "80012": "Hospital Building",
    "80013": "Clinic",
    "80014": "Rehabilitation Center",
    "80015": "Urgent Care",
    "80099": "Medical Facility",
}

# Verified FCodes from live WFS (May 2026).
# Prior values 74010/74011/74099 do not exist in the service.
POLICE_FCODES: frozenset[str] = frozenset({"74034"})
FIRE_FCODES: frozenset[str] = frozenset({"74026"})


def _is_retryable_usgs_error(exc: BaseException) -> bool:
    """Return True for transient USGS WFS errors worth retrying."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500 or exc.response.status_code == 429
    return False


# ---------------------------------------------------------------------------
# Extractor class
# ---------------------------------------------------------------------------


class USGSStructuresExtractor:
    """Downloads infrastructure data from the USGS National Map WFS service.

    For extracting all datasets at once (recommended for the pipeline):
        extractor.extract_and_save_all("new_york")

    For extracting datasets individuales (cada llamada hace un request WFS):
        healthcare_df = extractor.extract_healthcare("new_york")
        # NOTA: extract_law_enforcement y extract_fire_stations hacen
        # requests WFS independientes. Para evitar duplicacion, usar
        # extract_and_save_all() que optimiza con un solo request.
    """

    def __init__(self, settings: PipelineSettings | None = None) -> None:
        self.settings = settings or PipelineSettings()
        self._client: httpx.Client | None = None
        self._cache_740: pl.DataFrame | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=httpx.Timeout(self.settings.request_timeout_seconds),
            )
        return self._client

    def _fetch_740_cached(self, city: str) -> pl.DataFrame:
        if self._cache_740 is None:
            raw = self._fetch_ny(ftype=740)
            self._cache_740 = self._filter_nyc(raw)
        return self._cache_740

    def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            self._client.close()

    def __enter__(self) -> USGSStructuresExtractor:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_healthcare(self, city: str) -> pl.DataFrame:
        """Fetch FType 800 (hospitals/medical centers) for NYC.

        Returns DataFrame with columns:
        ``name``, ``lat``, ``lon``, ``facility_type``, ``address``,
        ``zipcode``, ``borough``, ``fcode``, ``loaddate``.
        """
        log.info("usgs_fetch_start", ftype=800, city=city)
        raw = self._fetch_ny(ftype=800)
        nyc = self._filter_nyc(raw)
        df = (
            nyc.rename(RENAME_COLUMNS)
            .with_columns(
                [
                    pl.col("FCode")
                    .replace_strict(HEALTHCARE_FCODE_MAP, default="Medical Facility")
                    .alias("facility_type"),
                    pl.col("FCode").alias("fcode"),
                ]
            )
            .select(OUTPUT_COLUMNS)
        )
        log.info("usgs_fetch_done", ftype=800, records=len(df))
        return df

    def extract_law_enforcement(self, city: str) -> pl.DataFrame:
        """Fetch FType 740 filtered to police FCodes only (FCode 74034).

        Returns DataFrame with columns:
        ``name``, ``lat``, ``lon``, ``facility_type``, ``address``,
        ``zipcode``, ``borough``, ``fcode``, ``loaddate``.
        """
        log.info("usgs_fetch_start", ftype=740, city=city)
        nyc = self._fetch_740_cached(city)
        police = nyc.filter(pl.col("FCode").is_in(list(POLICE_FCODES)))
        df = (
            police.rename(RENAME_COLUMNS)
            .with_columns(
                [
                    pl.lit("Police Station").alias("facility_type"),
                    pl.col("FCode").alias("fcode"),
                ]
            )
            .select(OUTPUT_COLUMNS)
        )
        log.info("usgs_fetch_done", ftype=740, records=len(df))
        return df

    def extract_fire_stations(self, city: str) -> pl.DataFrame:
        """Fetch FType 740 filtered to fire station FCodes only (FCode 74026).

        Returns DataFrame with columns:
        ``name``, ``lat``, ``lon``, ``facility_type``, ``address``,
        ``zipcode``, ``borough``, ``fcode``, ``loaddate``.
        """
        log.info("usgs_fetch_start", ftype=740, subtype="fire", city=city)
        nyc = self._fetch_740_cached(city)
        fire = nyc.filter(pl.col("FCode").is_in(list(FIRE_FCODES)))
        df = (
            fire.rename(RENAME_COLUMNS)
            .with_columns(
                [
                    pl.lit("Fire Station").alias("facility_type"),
                    pl.col("FCode").alias("fcode"),
                ]
            )
            .select(OUTPUT_COLUMNS)
        )
        log.info("usgs_fetch_done", ftype=740, subtype="fire", records=len(df))
        return df

    def extract_and_save_all(
        self,
        city: str,
        output_dir: Path | None = None,
    ) -> dict[str, Path]:
        """Fetch healthcare, police, and fire datasets and save as Parquet.

        FType 740 is fetched once and split into police (74034) and fire (74026)
        to avoid two round-trips to the WFS.

        Args:
            city: City key (currently only ``"new_york"`` is supported).
            output_dir: Output directory. Defaults to ``data/reference/{city}/``.

        Returns:
            Dict mapping dataset name to saved path.
        """
        output_dir = output_dir or REFERENCE_DIR / city
        output_dir.mkdir(parents=True, exist_ok=True)
        saved: dict[str, Path] = {}

        healthcare_df = self.extract_healthcare(city)
        hc_path = output_dir / "healthcare.parquet"
        healthcare_df.write_parquet(hc_path, compression="zstd")
        log.info("saved_healthcare", records=len(healthcare_df), path=str(hc_path))
        saved["healthcare"] = hc_path

        # Fetch FType 740 once, split into police + fire
        log.info("usgs_fetch_start", ftype=740, city=city)
        raw740 = self._fetch_ny(ftype=740)
        nyc740 = self._filter_nyc(raw740)

        def _normalise(df: pl.DataFrame, facility_type: str) -> pl.DataFrame:
            return (
                df.rename(RENAME_COLUMNS)
                .with_columns(
                    [
                        pl.lit(facility_type).alias("facility_type"),
                        pl.col("FCode").alias("fcode"),
                    ]
                )
                .select(OUTPUT_COLUMNS)
            )

        police_df = _normalise(
            nyc740.filter(pl.col("FCode").is_in(list(POLICE_FCODES))),
            "Police Station",
        )
        police_path = output_dir / "usgs_police.parquet"
        police_df.write_parquet(police_path, compression="zstd")
        log.info("saved_usgs_police", records=len(police_df), path=str(police_path))
        saved["usgs_police"] = police_path

        fire_df = _normalise(
            nyc740.filter(pl.col("FCode").is_in(list(FIRE_FCODES))),
            "Fire Station",
        )
        fire_path = output_dir / "usgs_fire.parquet"
        fire_df.write_parquet(fire_path, compression="zstd")
        log.info("saved_usgs_fire", records=len(fire_df), path=str(fire_path))
        saved["usgs_fire"] = fire_path

        return saved

    # ------------------------------------------------------------------
    # WFS fetch + parse
    # ------------------------------------------------------------------

    def _fetch_ny(self, ftype: int) -> pl.DataFrame:
        """POST WFS request and parse attribute fields + GML geometry."""
        xml_body = self._build_xml_filter(ftype)
        log.info("usgs_wfs_request", ftype=ftype, url=WFS_URL)

        resp = self._post_wfs(xml_body, ftype=ftype)

        root = ET.fromstring(resp.text)
        matched = root.get("numberMatched")
        returned = root.get("numberReturned")
        log.info(
            "usgs_wfs_response",
            matched=matched,
            returned=returned,
        )

        if matched and returned and matched != "unknown":
            try:
                n_matched = int(matched)
                n_returned = int(returned)
                if n_matched > n_returned:
                    log.warning(
                        "usgs_wfs_truncated",
                        ftype=ftype,
                        matched=n_matched,
                        returned=n_returned,
                        message=(
                            f"Se perdieron {n_matched - n_returned} registros. "
                            "Considerar implementar paginacion WFS."
                        ),
                    )
            except ValueError:
                pass

        rows: list[dict[str, object]] = []
        for member in root.iter(f"{{{WFS_NS}}}member"):
            for feat in member:
                row: dict[str, object] = {f: None for f in ATTR_FIELDS}
                row["lat"] = None
                row["lon"] = None

                for child in feat:
                    tag = child.tag.split("}")[-1]
                    if tag in ATTR_FIELDS:
                        row[tag] = child.text

                # Try to extract GML geometry
                point = feat.find(f".//{{{GML_NS}}}pos")
                if point is not None and point.text:
                    parts = point.text.strip().split()
                    if len(parts) >= 2:
                        try:
                            row["lat"] = float(parts[0])
                            row["lon"] = float(parts[1])
                        except ValueError:
                            pass

                rows.append(row)

        df = pl.DataFrame(
            rows,
            schema={f: pl.Utf8 for f in ATTR_FIELDS} | {"lat": pl.Float64, "lon": pl.Float64},
        )

        # Keep the extractor USGS-only: rows without USGS geometry are omitted
        # instead of being geocoded through a secondary provider.
        null_mask = df["lat"].is_null() | df["lon"].is_null()
        n_null = int(null_mask.sum())
        if n_null > 0:
            log.warning("usgs_missing_geometry_dropped", count=n_null)
            df = df.filter(pl.col("lat").is_not_null() & pl.col("lon").is_not_null())

        return df

    # ------------------------------------------------------------------
    # USGS HTTP
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception(_is_retryable_usgs_error),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    def _post_wfs(self, xml_body: bytes, *, ftype: int) -> httpx.Response:
        """POST the WFS request with retries for transient transport/5xx/429 failures."""
        client = self._get_client()
        resp = client.post(
            WFS_URL,
            content=xml_body,
            headers={"Content-Type": "application/xml"},
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            log.warning("usgs_wfs_http_error", ftype=ftype, status_code=resp.status_code)
            raise
        return resp

    # ------------------------------------------------------------------
    # NYC filtering
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_nyc(df: pl.DataFrame) -> pl.DataFrame:
        """Filter to NYC records using ZIP prefix and add borough column."""
        before = len(df)
        result = (
            df.filter(pl.col("ZIPCODE").is_not_null())
            .with_columns(pl.col("ZIPCODE").str.slice(0, 3).alias("zip_prefix"))
            .filter(pl.col("zip_prefix").is_in(list(NYC_ZIP_PREFIXES.keys())))
            .with_columns(pl.col("zip_prefix").replace(NYC_ZIP_PREFIXES).alias("borough"))
            .drop("zip_prefix")
        )
        dropped = before - len(result)
        if dropped > 0:
            log.info("usgs_nyc_filter", kept=len(result), dropped=dropped)
        return result

    # ------------------------------------------------------------------
    # WFS request builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_xml_filter(ftype: int, state: str = "NY") -> bytes:
        """OGC FES 2.0 XML filter — POST required, GET params ignored by this service."""
        xml = f"""<?xml version="1.0"?>
<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs/2.0"
                xmlns:fes="http://www.opengis.net/fes/2.0"
                service="WFS" version="2.0.0" count="5000">
  <wfs:Query typeNames="structures:USGS_TNM_Structures">
    <fes:Filter>
      <fes:And>
        <fes:PropertyIsEqualTo>
          <fes:ValueReference>FType</fes:ValueReference>
          <fes:Literal>{ftype}</fes:Literal>
        </fes:PropertyIsEqualTo>
        <fes:PropertyIsEqualTo>
          <fes:ValueReference>STATE</fes:ValueReference>
          <fes:Literal>{state}</fes:Literal>
        </fes:PropertyIsEqualTo>
      </fes:And>
    </fes:Filter>
  </wfs:Query>
</wfs:GetFeature>"""
        return xml.encode()
