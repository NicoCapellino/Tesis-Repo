"""
ETL Pipeline Orchestrator.

Coordinates the Extract → Transform → Load workflow:
1. **Extract**: Download raw NYPD complaint data + OSM infrastructure.
2. **Transform**: Normalize, clean, derive temporal features.
3. **Load**: Persist as compressed Parquet partitioned by year.

Can be run as a CLI script or imported and called programmatically.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import polars as pl

from config.settings import DEFAULT_CITY, PROCESSED_DIR, RAW_DIR, PipelineSettings
from src.extract.nypd_complaints import NYPDComplaintsExtractor
from src.extract.osm_infrastructure import OSMInfrastructureExtractor
from src.extract.usgs_structures import USGSStructuresExtractor
from src.transform.complaints import ComplaintsTransformer
from src.transform.geospatial import GeospatialValidator
from src.utils.logging import get_logger, setup_logging

log = get_logger(__name__)


def run_pipeline(
    *,
    settings: PipelineSettings | None = None,
    city: str = DEFAULT_CITY,
    skip_extract: bool = False,
    skip_infrastructure: bool = False,
    skip_usgs: bool = False,
) -> dict[str, Path]:
    """Execute the full ETL pipeline.

    Args:
        settings: Pipeline configuration. Uses defaults if not provided.
        city: City to process. Defaults to ``"new_york"``.
        skip_extract: If ``True``, skip the extraction phase and use existing
            raw files. Useful for re-running transforms without re-downloading.
        skip_infrastructure: If ``True``, skip OSM infrastructure download.
        skip_usgs: If ``True``, skip USGS structures download (healthcare + law enforcement).

    Returns:
        Dictionary with paths to all output artifacts.
    """
    settings = settings or PipelineSettings()
    outputs: dict[str, Path] = {}
    t0 = time.monotonic()

    log.info(
        "pipeline_start",
        city=city,
        years=f"{settings.start_year}-{settings.end_year}",
        skip_extract=skip_extract,
    )

    # ── Step 1: Extract ──────────────────────────────────────────────
    if not skip_extract:
        log.info("phase_extract_start")

        # 1a. NYPD Complaints
        with NYPDComplaintsExtractor(settings=settings) as extractor:
            raw_path = extractor.extract_and_save(
                years=range(settings.start_year, settings.end_year + 1),
            )
            outputs["raw_complaints"] = raw_path
            log.info("phase_extract_complaints_done", path=str(raw_path))

        # 1b. OSM Infrastructure (police + transport)
        if not skip_infrastructure:
            osm_extractor = OSMInfrastructureExtractor(settings=settings)
            infra_paths = osm_extractor.extract_and_save_all(city)
            outputs.update({f"reference_{k}": v for k, v in infra_paths.items()})
            log.info("phase_extract_infrastructure_done")

        # 1c. USGS Structures (healthcare + law enforcement)
        if not skip_usgs:
            usgs_extractor = USGSStructuresExtractor(settings=settings)
            usgs_paths = usgs_extractor.extract_and_save_all(city)
            outputs.update({f"reference_{k}": v for k, v in usgs_paths.items()})
            log.info("phase_extract_usgs_done")
    else:
        log.info("phase_extract_skipped")
        outputs["raw_complaints"] = RAW_DIR / "complaints"

    # ── Step 2: Transform ────────────────────────────────────────────
    log.info("phase_transform_start")

    transformer = ComplaintsTransformer()
    processed_path = transformer.transform_and_save(
        input_dir=outputs.get("raw_complaints", RAW_DIR / "complaints"),
        output_dir=PROCESSED_DIR / "complaints",
    )
    outputs["processed_complaints"] = processed_path

    # 2b. Geospatial validation
    geo_validator = GeospatialValidator(city=city)
    processed_files = sorted(processed_path.glob("*.parquet"))
    total_valid = 0
    total_invalid = 0

    for f in processed_files:
        df = pl.read_parquet(f)
        before = len(df)
        df_valid = geo_validator.filter_valid_coordinates(df)
        after = len(df_valid)
        total_valid += after
        total_invalid += before - after
        # Overwrite with validated data
        df_valid.write_parquet(f, compression="zstd")

    log.info(
        "phase_transform_done",
        valid_records=total_valid,
        invalid_coordinates_removed=total_invalid,
    )

    # ── Step 3: Summary ──────────────────────────────────────────────
    elapsed = time.monotonic() - t0
    log.info(
        "pipeline_complete",
        elapsed_seconds=round(elapsed, 1),
        outputs={k: str(v) for k, v in outputs.items()},
    )

    return outputs


def main() -> None:
    """CLI entry point."""
    setup_logging()
    log.info("nyc_crime_pipeline_v1")

    # Parse simple CLI flags
    skip_extract = "--skip-extract" in sys.argv
    skip_infra = "--skip-infrastructure" in sys.argv
    skip_usgs = "--skip-usgs" in sys.argv

    try:
        run_pipeline(
            skip_extract=skip_extract,
            skip_infrastructure=skip_infra,
            skip_usgs=skip_usgs,
        )
    except KeyboardInterrupt:
        log.info("pipeline_interrupted")
        sys.exit(1)
    except Exception:
        log.exception("pipeline_failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
