"""
Tests for the extraction module.

Validates pagination logic, URL construction, and data integrity checks
without hitting the real API (uses mocked responses).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from config.settings import MTA_BUS_STOPS, NYPD_DATASETS, PipelineSettings
from src.extract.mta_bus_stops import MTABusStopsExtractor
from src.extract.nypd_complaints import NYPDComplaintsExtractor
from src.extract.usgs_structures import USGSStructuresExtractor


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
        page1_csv = "cmplnt_num,boro_nm\n" + "\n".join(f"{i},MANHATTAN" for i in range(100))
        page2_csv = "cmplnt_num,boro_nm\n" + "\n".join(f"{i + 100},BROOKLYN" for i in range(50))

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


class TestUSGSStructuresExtractor:
    """Tests for USGS WFS parsing and NYC filtering."""

    def test_filter_nyc_includes_queens_111_zip_prefix(self) -> None:
        """ZIP prefix 111 should be retained and mapped to Queens."""
        df = pl.DataFrame(
            {
                "NAME": ["LIC Station", "Manhattan Facility", "Long Island Facility"],
                "FType": ["740", "800", "800"],
                "FCode": ["74034", "80010", "80010"],
                "ADDRESS": ["1 Court Sq", "1 Main St", "1 Other St"],
                "CITY": ["Long Island City", "New York", "Mineola"],
                "STATE": ["NY", "NY", "NY"],
                "ZIPCODE": ["11101", "10001", "11501"],
                "LOADDATE": ["2026-01-01", "2026-01-01", "2026-01-01"],
                "lat": [40.746, 40.75, 40.74],
                "lon": [-73.944, -73.99, -73.64],
            }
        )

        result = USGSStructuresExtractor._filter_nyc(df)

        assert result["ZIPCODE"].to_list() == ["11101", "10001"]
        assert result["borough"].to_list() == ["QUEENS", "MANHATTAN"]

    def test_fetch_ny_parses_gml_geometry_and_drops_missing_geometry(self) -> None:
        """WFS parser should use USGS geometry and omit records without coordinates."""
        xml = """<?xml version="1.0"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
                       xmlns:gml="http://www.opengis.net/gml/3.2"
                       xmlns:structures="https://example.com/structures"
                       numberMatched="2" numberReturned="2">
  <wfs:member>
    <structures:USGS_TNM_Structures>
      <structures:NAME>Valid Police Station</structures:NAME>
      <structures:FType>740</structures:FType>
      <structures:FCode>74034</structures:FCode>
      <structures:ADDRESS>1 Main St</structures:ADDRESS>
      <structures:CITY>New York</structures:CITY>
      <structures:STATE>NY</structures:STATE>
      <structures:ZIPCODE>10001</structures:ZIPCODE>
      <structures:LOADDATE>2026-01-01</structures:LOADDATE>
      <gml:Point><gml:pos>40.7501 -73.9901</gml:pos></gml:Point>
    </structures:USGS_TNM_Structures>
  </wfs:member>
  <wfs:member>
    <structures:USGS_TNM_Structures>
      <structures:NAME>Missing Geometry</structures:NAME>
      <structures:FType>740</structures:FType>
      <structures:FCode>74034</structures:FCode>
      <structures:ADDRESS>2 Main St</structures:ADDRESS>
      <structures:CITY>New York</structures:CITY>
      <structures:STATE>NY</structures:STATE>
      <structures:ZIPCODE>10002</structures:ZIPCODE>
      <structures:LOADDATE>2026-01-01</structures:LOADDATE>
    </structures:USGS_TNM_Structures>
  </wfs:member>
</wfs:FeatureCollection>"""

        response = MagicMock(text=xml)
        extractor = USGSStructuresExtractor()

        with patch.object(extractor, "_post_wfs", return_value=response):
            result = extractor._fetch_ny(ftype=740)

        assert len(result) == 1
        assert result["NAME"].to_list() == ["Valid Police Station"]
        assert result["lat"].to_list()[0] == pytest.approx(40.7501)
        assert result["lon"].to_list()[0] == pytest.approx(-73.9901)

    def test_extract_law_enforcement_filters_to_police_fcode(self) -> None:
        """Law enforcement extraction should keep only police station FCodes."""
        raw = pl.DataFrame(
            {
                "NAME": ["Police", "Fire"],
                "FType": ["740", "740"],
                "FCode": ["74034", "74026"],
                "ADDRESS": ["1 Main", "2 Main"],
                "CITY": ["New York", "New York"],
                "STATE": ["NY", "NY"],
                "ZIPCODE": ["10001", "10002"],
                "LOADDATE": ["2026-01-01", "2026-01-01"],
                "lat": [40.75, 40.76],
                "lon": [-73.99, -73.98],
            }
        )
        extractor = USGSStructuresExtractor()

        with patch.object(extractor, "_fetch_ny", return_value=raw):
            result = extractor.extract_law_enforcement("new_york")

        assert len(result) == 1
        assert result["name"].to_list() == ["Police"]
        assert result["facility_type"].to_list() == ["Police Station"]

    def test_extract_and_save_all_writes_three_parquet_files(self, tmp_path: Path) -> None:
        """extract_and_save_all should produce healthcare, police, fire parquets."""
        extractor = USGSStructuresExtractor()

        raw_800 = pl.DataFrame(
            {
                "NAME": ["Hospital X"],
                "FType": ["800"],
                "FCode": ["80010"],
                "ADDRESS": ["1 Main"],
                "CITY": ["New York"],
                "STATE": ["NY"],
                "ZIPCODE": ["10001"],
                "LOADDATE": ["2026-01-01"],
                "lat": [40.75],
                "lon": [-73.99],
            }
        )
        raw_740 = pl.DataFrame(
            {
                "NAME": ["Police Y", "Fire Z"],
                "FType": ["740", "740"],
                "FCode": ["74034", "74026"],
                "ADDRESS": ["2 Main", "3 Main"],
                "CITY": ["New York", "New York"],
                "STATE": ["NY", "NY"],
                "ZIPCODE": ["10001", "10002"],
                "LOADDATE": ["2026-01-01", "2026-01-01"],
                "lat": [40.75, 40.76],
                "lon": [-73.99, -73.98],
            }
        )

        def mock_fetch(ftype: int) -> pl.DataFrame:
            return raw_800 if ftype == 800 else raw_740

        with patch.object(extractor, "_fetch_ny", side_effect=mock_fetch):
            result = extractor.extract_and_save_all("new_york", output_dir=tmp_path)

        assert "healthcare" in result
        assert "usgs_police" in result
        assert "usgs_fire" in result
        assert (tmp_path / "healthcare.parquet").exists()
        assert (tmp_path / "usgs_police.parquet").exists()
        assert (tmp_path / "usgs_fire.parquet").exists()

    def test_fetch_ny_handles_empty_feature_collection(self) -> None:
        """An empty WFS response should return an empty DataFrame, not crash."""
        xml = """<?xml version="1.0"?>
        <wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0"
                               numberMatched="0" numberReturned="0">
        </wfs:FeatureCollection>"""
        response = MagicMock(text=xml)
        extractor = USGSStructuresExtractor()

        with patch.object(extractor, "_post_wfs", return_value=response):
            result = extractor._fetch_ny(ftype=800)

        assert len(result) == 0

    def test_filter_nyc_handles_null_zipcode(self) -> None:
        """Records with null ZIPCODE should be filtered out silently."""
        df = pl.DataFrame(
            {
                "NAME": ["Good", "Bad"],
                "ZIPCODE": ["10001", None],
                "lat": [40.75, 40.76],
                "lon": [-73.99, -73.98],
            }
        )
        result = USGSStructuresExtractor._filter_nyc(df)
        assert len(result) == 1


class TestMTABusStopsExtractor:
    """Tests for MTA bus stop normalization, bbox filtering, and dedup."""

    def test_dataset_json_endpoint_is_valid(self) -> None:
        """The MTA descriptor should expose a valid JSON endpoint on data.ny.gov."""
        assert MTA_BUS_STOPS.resource_id == "2ucp-7wg5"
        assert MTA_BUS_STOPS.json_endpoint.startswith("https://data.ny.gov/")
        assert MTA_BUS_STOPS.json_endpoint.endswith(".json")

    def test_normalize_casts_types_and_adds_facility_type(self) -> None:
        """String lat/lon become floats and every row is tagged 'Bus Stop'."""
        rows = [
            {"stop_id": "100014", "name": "BEDFORD PK BL", "lat": "40.8725", "lon": "-73.8881"},
        ]
        result = MTABusStopsExtractor()._normalize(rows, "new_york")

        assert result.columns == ["name", "lat", "lon", "facility_type", "stop_id"]
        assert result.schema["lat"] == pl.Float64
        assert result.schema["lon"] == pl.Float64
        assert result["facility_type"].to_list() == ["Bus Stop"]
        assert result["lat"].to_list()[0] == pytest.approx(40.8725)

    def test_normalize_filters_outside_nyc_bbox(self) -> None:
        """Stops outside the NYC bounding box should be dropped."""
        rows = [
            # Inside NYC
            {"stop_id": "1", "name": "NYC Stop", "lat": "40.75", "lon": "-73.99"},
            # Upstate / outside bbox (latitude too high)
            {"stop_id": "2", "name": "Far Stop", "lat": "42.65", "lon": "-73.75"},
        ]
        result = MTABusStopsExtractor()._normalize(rows, "new_york")

        assert result["stop_id"].to_list() == ["1"]

    def test_normalize_dedupes_by_stop_id(self) -> None:
        """Duplicate stop_id rows should collapse to a single physical stop."""
        rows = [
            {"stop_id": "100014", "name": "HYLAN BL", "lat": "40.60", "lon": "-74.10"},
            {"stop_id": "100014", "name": "HYLAN BLVD", "lat": "40.60", "lon": "-74.10"},
        ]
        result = MTABusStopsExtractor()._normalize(rows, "new_york")

        assert len(result) == 1
        assert result["stop_id"].to_list() == ["100014"]

    def test_normalize_empty_rows_returns_typed_empty_frame(self) -> None:
        """An empty payload should yield a typed empty frame, not crash."""
        result = MTABusStopsExtractor()._normalize([], "new_york")

        assert len(result) == 0
        assert result.columns == ["name", "lat", "lon", "facility_type", "stop_id"]

    def test_extract_and_save_writes_parquet(self, tmp_path: Path) -> None:
        """extract_and_save should persist mta_bus_stops.parquet."""
        rows = [
            {"stop_id": "1", "name": "Stop A", "lat": "40.75", "lon": "-73.99"},
            {"stop_id": "2", "name": "Stop B", "lat": "40.70", "lon": "-73.95"},
        ]
        extractor = MTABusStopsExtractor()

        with patch.object(extractor, "_fetch_stops", return_value=rows):
            out_path = extractor.extract_and_save("new_york", output_dir=tmp_path)

        assert out_path == tmp_path / "mta_bus_stops.parquet"
        assert out_path.exists()

        saved = pl.read_parquet(out_path)
        assert len(saved) == 2
        assert set(saved["facility_type"].unique().to_list()) == {"Bus Stop"}
