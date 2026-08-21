"""
Tests for the shared geospatial distance utilities.

Focuses on the chunked nearest-distance computation, which bounds peak memory
for large reference layers (e.g. ~17.5k MTA bus stops) and must return results
identical to a single full-matrix broadcast.
"""

from __future__ import annotations

import numpy as np

from app.components.distances import haversine_np, nearest_distances


def _brute_force_nearest(
    c_lats: np.ndarray,
    c_lons: np.ndarray,
    s_lats: np.ndarray,
    s_lons: np.ndarray,
) -> np.ndarray:
    """Reference implementation via a single full (n x m) broadcast."""
    matrix = haversine_np(
        c_lats[:, None],
        c_lons[:, None],
        s_lats[None, :],
        s_lons[None, :],
    )
    return matrix.min(axis=1)


class TestNearestDistances:
    def test_matches_full_matrix_across_chunk_boundaries(self) -> None:
        """Chunked result must equal the full-matrix result for any chunk size."""
        rng = np.random.default_rng(42)
        c_lats = 40.5 + rng.random(1000) * 0.4
        c_lons = -74.2 + rng.random(1000) * 0.5
        s_lats = 40.5 + rng.random(250) * 0.4
        s_lons = -74.2 + rng.random(250) * 0.5

        expected = _brute_force_nearest(c_lats, c_lons, s_lats, s_lons)

        # chunk_size smaller than, equal to, and larger than n — all must agree.
        for chunk in (1, 7, 333, 1000, 5000):
            result = nearest_distances(c_lats, c_lons, s_lats, s_lons, chunk_size=chunk)
            np.testing.assert_allclose(result, expected, rtol=1e-9, atol=1e-6)

    def test_returns_meters_for_known_pair(self) -> None:
        """A ~1 degree of latitude separation is ~111 km."""
        result = nearest_distances(
            np.array([40.0]),
            np.array([-74.0]),
            np.array([41.0]),
            np.array([-74.0]),
        )
        assert result[0] == np.float64(result[0])  # scalar, no matrix returned
        assert 110_000 < result[0] < 112_000

    def test_empty_stations_returns_nan(self) -> None:
        """With no stations there is no nearest distance — return NaN, not crash."""
        result = nearest_distances(
            np.array([40.7, 40.8]),
            np.array([-73.9, -73.8]),
            np.array([]),
            np.array([]),
        )
        assert result.shape == (2,)
        assert np.all(np.isnan(result))

    def test_empty_crimes_returns_empty(self) -> None:
        """With no crimes the result is an empty array."""
        result = nearest_distances(
            np.array([]),
            np.array([]),
            np.array([40.7]),
            np.array([-73.9]),
        )
        assert result.shape == (0,)
