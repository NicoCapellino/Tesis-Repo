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

    def test_invalid_sex_codes_are_nulled(self, transformer: ComplaintsTransformer) -> None:
        """Junk sex codes (e.g. 'L') are nulled; valid person/entity codes kept."""
        raw = pl.DataFrame(
            {
                "cmplnt_num": ["1", "2", "3", "4", "5"],
                "cmplnt_fr_dt": ["2024-01-01T00:00:00.000"] * 5,
                "cmplnt_fr_tm": ["10:00:00"] * 5,
                "vic_sex": ["M", "F", "D", "E", "L"],
                "susp_sex": ["M", "U", "F", "X", "L"],
            }
        )
        result = transformer.transform(raw)

        # Victims keep M/F/D/E; the invalid 'L' becomes null.
        assert result["victim_sex"].to_list() == ["M", "F", "D", "E", None]
        # Suspects keep only M/F/U; 'X' and 'L' become null.
        assert result["suspect_sex"].to_list() == ["M", "U", "F", None, None]

    def test_corrupt_end_dates_are_nulled(self, transformer: ComplaintsTransformer) -> None:
        """End dates before the start or with absurd years are nulled."""
        import datetime

        raw = pl.DataFrame(
            {
                "cmplnt_num": ["1", "2", "3"],
                "cmplnt_fr_dt": [
                    "2024-05-10T00:00:00.000",  # valid: end is one day later
                    "2020-10-27T00:00:00.000",  # end in year 1010 (before start)
                    "2025-11-06T00:00:00.000",  # end in year 2052 (absurd future)
                ],
                "cmplnt_fr_tm": ["10:00:00"] * 3,
                "cmplnt_to_dt": [
                    "2024-05-11T00:00:00.000",
                    "1010-10-21T00:00:00.000",
                    "2052-11-08T00:00:00.000",
                ],
            }
        )
        result = transformer.transform(raw)
        ends = result["crime_end_date"].to_list()

        assert ends[0] == datetime.date(2024, 5, 11)  # valid kept
        assert ends[1] is None  # before start → nulled
        assert ends[2] is None  # absurd year → nulled

    def test_invalid_age_groups_are_nulled(self, transformer: ComplaintsTransformer) -> None:
        """Junk age values are nulled; valid bins and the crime row are kept."""
        raw = pl.DataFrame(
            {
                "cmplnt_num": ["1", "2", "3", "4"],
                "cmplnt_fr_dt": ["2024-01-01T00:00:00.000"] * 4,
                "cmplnt_fr_tm": ["10:00:00"] * 4,
                "vic_age_group": ["25-44", "-968", "1023", "65+"],
                "susp_age_group": ["2021", "18-24", "-1", "45-64"],
            }
        )
        result = transformer.transform(raw)

        # Junk values become null; valid bins survive.
        assert result["victim_age_group"].to_list() == ["25-44", None, None, "65+"]
        assert result["suspect_age_group"].to_list() == [None, "18-24", None, "45-64"]
        # No rows dropped — the crimes are preserved.
        assert len(result) == 4
