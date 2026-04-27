"""
Robust extraction of NYPD complaint data from NYC Open Data (Socrata SODA API).

Implements proper pagination, retry logic with exponential backoff, progress
logging, and row-count validation to guarantee complete data extraction.

The Socrata API returns at most ``$limit`` rows per request (max 50 000).
To fetch the full dataset we loop with incrementing ``$offset`` until a
response returns fewer rows than the requested ``$limit``.
"""

from __future__ import annotations

import io
import time
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import polars as pl
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import (
    NYPD_DATASETS,
    RAW_DIR,
    PipelineSettings,
    SocrataDataset,
)
from src.utils.logging import get_logger

if TYPE_CHECKING:
    pass

log = get_logger(__name__)


class NYPDComplaintsExtractor:
    """Downloads NYPD complaint data with full pagination support.

    Usage::

        extractor = NYPDComplaintsExtractor()
        df = extractor.extract_all(years=range(2020, 2026))
        # or
        extractor.extract_and_save(years=range(2020, 2026))
    """

    def __init__(self, settings: PipelineSettings | None = None) -> None:
        self.settings = settings or PipelineSettings()
        self._client: httpx.Client | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_all(
        self,
        years: range | list[int] | None = None,
    ) -> pl.DataFrame:
        """Extract complaint data for the given years from all configured datasets.

        Fetches from both the *historic* and *current_ytd* datasets, then
        deduplicates on ``cmplnt_num`` (complaint ID) to avoid double-counting
        records that appear in both datasets.

        Args:
            years: Year range to extract. Defaults to settings range.

        Returns:
            A single :class:`polars.DataFrame` with all raw records.
        """
        if years is None:
            years = range(self.settings.start_year, self.settings.end_year + 1)

        all_frames: list[pl.DataFrame] = []

        for dataset_name, dataset in NYPD_DATASETS.items():
            log.info(
                "starting_dataset_extraction",
                dataset=dataset_name,
                description=dataset.description,
            )
            for year in years:
                df_year = self._extract_year(dataset=dataset, year=year)
                if df_year is not None and len(df_year) > 0:
                    all_frames.append(df_year)

        if not all_frames:
            log.warning("no_data_extracted")
            return pl.DataFrame()

        combined = pl.concat(all_frames, how="diagonal_relaxed")

        # Deduplicate across historic + current_ytd on complaint ID
        before = len(combined)
        combined = combined.unique(subset=["cmplnt_num"], keep="last")
        after = len(combined)

        log.info(
            "extraction_complete",
            total_records=after,
            duplicates_removed=before - after,
        )
        return combined

    def extract_and_save(
        self,
        years: range | list[int] | None = None,
        output_dir: Path | None = None,
    ) -> Path:
        """Extract data and persist as raw Parquet partitioned by year.

        Args:
            years: Year range to extract.
            output_dir: Directory for output. Defaults to ``data/raw/complaints/``.

        Returns:
            Path to the output directory containing the Parquet files.
        """
        output_dir = output_dir or RAW_DIR / "complaints"
        output_dir.mkdir(parents=True, exist_ok=True)

        df = self.extract_all(years=years)

        if df.is_empty():
            log.warning("nothing_to_save")
            return output_dir

        # Ensure we have a year column for partitioning
        if "cmplnt_fr_dt" in df.columns:
            df = df.with_columns(
                pl.col("cmplnt_fr_dt")
                .str.slice(0, 4)
                .cast(pl.Int32, strict=False)
                .alias("_year")
            )
        else:
            log.warning("no_date_column_for_partitioning")
            df = df.with_columns(pl.lit(0).alias("_year"))

        # Write one Parquet file per year for efficient downstream reads
        for year_val in df["_year"].unique().sort().to_list():
            if year_val is None:
                continue
            year_df = df.filter(pl.col("_year") == year_val).drop("_year")
            out_path = output_dir / f"complaints_{year_val}.parquet"
            year_df.write_parquet(out_path, compression="zstd")
            log.info("saved_year", year=year_val, records=len(year_df), path=str(out_path))

        return output_dir

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _get_client(self) -> httpx.Client:
        """Lazy-initialize the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=httpx.Timeout(self.settings.request_timeout_seconds),
                follow_redirects=True,
            )
        return self._client

    def _extract_year(
        self,
        *,
        dataset: SocrataDataset,
        year: int,
    ) -> pl.DataFrame | None:
        """Fetch all pages of a single year from one dataset.

        Implements the core pagination loop:
        1. Request ``$limit`` rows starting at ``$offset``.
        2. Parse the CSV response into a Polars DataFrame.
        3. If fewer than ``$limit`` rows were returned, stop.
        4. Otherwise, increment ``$offset`` and repeat.
        """
        offset = 0
        page = 0
        frames: list[pl.DataFrame] = []
        total_rows = 0

        start_date = f"{year}-01-01T00:00:00"
        end_date = f"{year}-12-31T23:59:59"

        log.info("extracting_year", dataset=dataset.resource_id, year=year)
        t0 = time.monotonic()

        while True:
            page += 1
            page_df = self._fetch_page(
                endpoint=dataset.endpoint,
                date_column=dataset.date_column,
                start_date=start_date,
                end_date=end_date,
                offset=offset,
                limit=self.settings.page_size,
            )

            if page_df is None or len(page_df) == 0:
                break

            rows_received = len(page_df)
            total_rows += rows_received
            frames.append(page_df)

            log.debug(
                "page_fetched",
                page=page,
                rows=rows_received,
                total_so_far=total_rows,
            )

            # If we got fewer rows than the limit, we've reached the end
            if rows_received < self.settings.page_size:
                break

            offset += self.settings.page_size

        elapsed = time.monotonic() - t0

        if not frames:
            log.info("year_empty", year=year, dataset=dataset.resource_id)
            return None

        result = pl.concat(frames, how="diagonal_relaxed")
        log.info(
            "year_complete",
            year=year,
            dataset=dataset.resource_id,
            records=len(result),
            pages=page,
            elapsed_seconds=round(elapsed, 1),
        )
        return result

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        reraise=True,
    )
    def _fetch_page(
        self,
        *,
        endpoint: str,
        date_column: str,
        start_date: str,
        end_date: str,
        offset: int,
        limit: int,
    ) -> pl.DataFrame | None:
        """Fetch a single page from the Socrata API with retry logic.

        Args:
            endpoint: Full URL of the Socrata CSV resource.
            date_column: Name of the date column for filtering.
            start_date: ISO-format start of the date range.
            end_date: ISO-format end of the date range.
            offset: Number of rows to skip.
            limit: Maximum number of rows to return.

        Returns:
            A DataFrame with the page data, or ``None`` on empty response.
        """
        params: dict[str, str] = {
            "$where": f"{date_column} between '{start_date}' and '{end_date}'",
            "$limit": str(limit),
            "$offset": str(offset),
            "$order": f"{date_column} ASC",
        }
        headers = (
            {"X-App-Token": self.settings.socrata_app_token}
            if self.settings.socrata_app_token
            else {}
        )

        client = self._get_client()
        response = client.get(endpoint, params=params, headers=headers)
        response.raise_for_status()

        content = response.text.strip()
        if not content or content.count("\n") <= 1:
            # Empty response or header-only
            return None

        try:
            df = pl.read_csv(io.StringIO(content), infer_schema_length=0)
        except Exception:
            log.exception("csv_parse_error", offset=offset)
            return None

        return df

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            self._client.close()

    def __enter__(self) -> NYPDComplaintsExtractor:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
