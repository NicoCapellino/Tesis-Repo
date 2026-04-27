"""
Tests for the extraction module.

Validates pagination logic, URL construction, and data integrity checks
without hitting the real API (uses mocked responses).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from config.settings import NYPD_DATASETS, PipelineSettings
from src.extract.nypd_complaints import NYPDComplaintsExtractor


@pytest.fixture
def settings() -> PipelineSettings:
    """Pipeline settings with small page size for testing."""
    return PipelineSettings(page_size=100, start_year=2024, end_year=2024)


@pytest.fixture
def extractor(settings: PipelineSettings) -> NYPDComplaintsExtractor:
    return NYPDComplaintsExtractor(settings=settings)


class TestNYPDComplaintsExtractor:
    """Tests for pagination and data extraction logic."""

    def test_dataset_endpoints_are_valid(self) -> None:
        """All configured datasets should have proper endpoint URLs."""
        for name, dataset in NYPD_DATASETS.items():
            assert dataset.resource_id, f"Dataset '{name}' has no resource_id"
            assert dataset.endpoint.startswith("https://"), f"Invalid URL for '{name}'"
            assert dataset.endpoint.endswith(".csv"), f"Endpoint should be CSV for '{name}'"

    def test_pagination_stops_on_partial_page(self, extractor: NYPDComplaintsExtractor) -> None:
        """Extractor should stop when a page returns fewer rows than $limit."""
        # Simulate: first page returns 100 rows (full), second returns 50 (partial = last)
        page1_csv = "cmplnt_num,boro_nm\n" + "\n".join(
            f"{i},MANHATTAN" for i in range(100)
        )
        page2_csv = "cmplnt_num,boro_nm\n" + "\n".join(
            f"{i + 100},BROOKLYN" for i in range(50)
        )

        mock_responses = [
            MagicMock(status_code=200, text=page1_csv),
            MagicMock(status_code=200, text=page2_csv),
        ]
        for r in mock_responses:
            r.raise_for_status = MagicMock()

        with patch.object(extractor, "_get_client") as mock_client:
            mock_http = MagicMock()
            mock_http.get.side_effect = mock_responses
            mock_client.return_value = mock_http

            dataset = NYPD_DATASETS["historic"]
            result = extractor._extract_year(dataset=dataset, year=2024)

        assert result is not None
        assert len(result) == 150
        assert mock_http.get.call_count == 2

    def test_pagination_stops_on_empty_response(self, extractor: NYPDComplaintsExtractor) -> None:
        """Extractor should stop when a page returns no data."""
        empty_csv = "cmplnt_num,boro_nm\n"

        mock_response = MagicMock(status_code=200, text=empty_csv)
        mock_response.raise_for_status = MagicMock()

        with patch.object(extractor, "_get_client") as mock_client:
            mock_http = MagicMock()
            mock_http.get.return_value = mock_response
            mock_client.return_value = mock_http

            dataset = NYPD_DATASETS["historic"]
            result = extractor._extract_year(dataset=dataset, year=2024)

        assert result is None

    def test_extract_all_deduplicates(self, extractor: NYPDComplaintsExtractor) -> None:
        """Records appearing in both historic and current_ytd should be deduplicated."""
        csv_data = "cmplnt_num,boro_nm\n1,MANHATTAN\n2,BROOKLYN\n"

        mock_response = MagicMock(status_code=200, text=csv_data)
        mock_response.raise_for_status = MagicMock()

        with patch.object(extractor, "_get_client") as mock_client:
            mock_http = MagicMock()
            mock_http.get.return_value = mock_response
            mock_client.return_value = mock_http

            result = extractor.extract_all(years=[2024])

        # Same 2 records from 2 datasets → should be deduplicated to 2
        assert len(result) == 2

    def test_fetch_page_uses_x_app_token_when_configured(self) -> None:
        """Socrata requests should include X-App-Token when provided in settings."""
        extractor = NYPDComplaintsExtractor(
            settings=PipelineSettings(
                page_size=100,
                start_year=2024,
                end_year=2024,
                socrata_app_token="test-token",
            )
        )
        csv_data = "cmplnt_num,boro_nm\n1,MANHATTAN\n2,BROOKLYN\n"
        mock_response = MagicMock(status_code=200, text=csv_data)
        mock_response.raise_for_status = MagicMock()

        with patch.object(extractor, "_get_client") as mock_client:
            mock_http = MagicMock()
            mock_http.get.return_value = mock_response
            mock_client.return_value = mock_http

            result = extractor._fetch_page(
                endpoint=NYPD_DATASETS["historic"].endpoint,
                date_column="cmplnt_fr_dt",
                start_date="2024-01-01T00:00:00",
                end_date="2024-12-31T23:59:59",
                offset=0,
                limit=100,
            )

        assert result is not None
        assert len(result) == 2
        mock_http.get.assert_called_once()
        _, kwargs = mock_http.get.call_args
        assert kwargs["headers"] == {"X-App-Token": "test-token"}
