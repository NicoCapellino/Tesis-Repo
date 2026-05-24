"""
Tests for the transformation module.

Validates column renaming, type casting, null cleaning, and temporal
feature derivation using synthetic data.
"""

from __future__ import annotations

import polars as pl
import pytest

from src.transform.complaints import ComplaintsTransformer


@pytest.fixture
def transformer() -> ComplaintsTransformer:
    return ComplaintsTransformer()


@pytest.fixture
def raw_df() -> pl.DataFrame:
    """Synthetic raw DataFrame mimicking Socrata output (all strings)."""
    return pl.DataFrame(
        {
            "cmplnt_num": ["100001", "100002", "100003"],
            "boro_nm": ["MANHATTAN", "BROOKLYN", "(null)"],
            "cmplnt_fr_dt": [
                "2024-06-15T00:00:00.000",
                "2024-07-20T00:00:00.000",
                "2024-08-01T00:00:00.000",
            ],
            "cmplnt_fr_tm": ["14:30:00", "08:00:00", "23:45:00"],
            "law_cat_cd": ["FELONY", "MISDEMEANOR", "VIOLATION"],
            "ofns_desc": ["GRAND LARCENY", "PETIT LARCENY", "HARRASSMENT 2"],
            "prem_typ_desc": ["STREET", "RESIDENCE-HOUSE", "UNKNOWN"],
            "latitude": ["40.7580", "40.6782", "0"],
            "longitude": ["-73.9855", "-73.9442", "0"],
            "vic_age_group": ["25-44", "UNKNOWN", "18-24"],
            "vic_race": ["WHITE", "(null)", "BLACK"],
            "vic_sex": ["M", "F", "M"],
            "susp_age_group": ["25-44", "18-24", "(null)"],
            "susp_race": ["BLACK", "WHITE", "UNKNOWN"],
            "susp_sex": ["M", "M", "(null)"],
        }
    )


class TestComplaintsTransformer:
    """Tests for the complaints transformation pipeline."""

    def test_column_renaming(
        self,
        transformer: ComplaintsTransformer,
        raw_df: pl.DataFrame,
    ) -> None:
        """Socrata column names should be renamed to descriptive names."""
        result = transformer.transform(raw_df)

        assert "complaint_id" in result.columns
        assert "borough" in result.columns
        assert "offense_level" in result.columns
        assert "offense_description" in result.columns

        # Original names should not be present
        assert "cmplnt_num" not in result.columns
        assert "boro_nm" not in result.columns

    def test_null_cleaning(self, transformer: ComplaintsTransformer, raw_df: pl.DataFrame) -> None:
        """Sentinel values like '(null)' and 'UNKNOWN' should become actual nulls."""
        result = transformer.transform(raw_df)

        # Row with "(null)" borough → should be null
        boroughs = result["borough"].to_list()
        assert boroughs[2] is None

        # "UNKNOWN" premise type → should be null
        premises = result["premise_type"].to_list()
        assert premises[2] is None

    def test_temporal_features(
        self,
        transformer: ComplaintsTransformer,
        raw_df: pl.DataFrame,
    ) -> None:
        """Year, month, day_of_week, and hour should be derived correctly."""
        result = transformer.transform(raw_df)

        assert "year" in result.columns
        assert "month" in result.columns
        assert "day_of_week" in result.columns
        assert "hour" in result.columns

        years = result["year"].to_list()
        assert years == [2024, 2024, 2024]

        months = result["month"].to_list()
        assert months == [6, 7, 8]

        hours = result["hour"].to_list()
        assert hours == [14, 8, 23]

    def test_coordinate_casting(
        self,
        transformer: ComplaintsTransformer,
        raw_df: pl.DataFrame,
    ) -> None:
        """Latitude and longitude should be cast to Float64."""
        result = transformer.transform(raw_df)

        assert result["latitude"].dtype == pl.Float64
        assert result["longitude"].dtype == pl.Float64

        lats = result["latitude"].to_list()
        assert lats[0] == pytest.approx(40.758, abs=0.001)

    def test_output_columns_ordered(
        self,
        transformer: ComplaintsTransformer,
        raw_df: pl.DataFrame,
    ) -> None:
        """Output should contain only the defined output columns, in order."""
        result = transformer.transform(raw_df)

        # Should not contain raw-only columns
        assert "lat_lon" not in result.columns
        assert "geometry_wkt" not in result.columns

        # First column should be complaint_id
        assert result.columns[0] == "complaint_id"

    def test_empty_dataframe(self, transformer: ComplaintsTransformer) -> None:
        """Transformer should handle an empty DataFrame gracefully."""
        empty = pl.DataFrame({"cmplnt_num": [], "boro_nm": [], "latitude": [], "longitude": []})
        result = transformer.transform(empty)
        assert len(result) == 0
