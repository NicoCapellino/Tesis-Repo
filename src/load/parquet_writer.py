"""
Parquet persistence layer.

Provides a unified interface for writing DataFrames to Parquet with
consistent compression, partitioning, and metadata.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from src.utils.logging import get_logger

log = get_logger(__name__)

# Default compression – Zstandard offers the best balance of speed and ratio
DEFAULT_COMPRESSION: str = "zstd"


class ParquetWriter:
    """Writes Polars DataFrames to Parquet files.

    Usage::

        writer = ParquetWriter(output_dir=Path("data/processed/complaints"))
        writer.write_partitioned(df, partition_col="year")
        # or single file:
        writer.write(df, filename="all_complaints.parquet")
    """

    def __init__(
        self,
        output_dir: Path,
        *,
        compression: str = DEFAULT_COMPRESSION,
    ) -> None:
        self.output_dir = output_dir
        self.compression = compression
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(self, df: pl.DataFrame, filename: str) -> Path:
        """Write a DataFrame as a single Parquet file.

        Args:
            df: Data to write.
            filename: Output file name (e.g. ``"complaints.parquet"``).

        Returns:
            Full path to the written file.
        """
        path = self.output_dir / filename
        df.write_parquet(path, compression=self.compression)
        log.info("parquet_written", path=str(path), rows=len(df), compression=self.compression)
        return path

    def write_partitioned(
        self,
        df: pl.DataFrame,
        *,
        partition_col: str,
        prefix: str = "data",
    ) -> list[Path]:
        """Write a DataFrame partitioned by a column, one file per partition value.

        Args:
            df: Data to write.
            partition_col: Column to partition on (e.g. ``"year"``).
            prefix: Filename prefix for each partition file.

        Returns:
            List of paths to the written files.
        """
        if partition_col not in df.columns:
            raise ValueError(
                f"Partition column '{partition_col}' not found. "
                f"Available: {df.columns}"
            )

        paths: list[Path] = []
        for value in df[partition_col].unique().sort().to_list():
            if value is None:
                continue
            partition_df = df.filter(pl.col(partition_col) == value)
            filename = f"{prefix}_{value}.parquet"
            path = self.write(partition_df, filename)
            paths.append(path)

        log.info(
            "partitioned_write_complete",
            partition_col=partition_col,
            partitions=len(paths),
            total_rows=len(df),
        )
        return paths
