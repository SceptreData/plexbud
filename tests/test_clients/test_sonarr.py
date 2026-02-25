"""Tests for Sonarr client."""

from __future__ import annotations

import respx
from httpx import Response

from plexbud.clients.sonarr import SonarrClient

SONARR_URL = "http://sonarr:8989"


class TestSonarrClient:
    def test_get_all_series(self, sonarr_mock: respx.MockRouter) -> None:
        series = SonarrClient(SONARR_URL, "test-key").get_all_series()

        assert len(series) == 5
        assert series[0].title == "Breaking Bad"
        assert series[0].external_id == 81189
        assert series[0].media_type == "tv"
        assert series[0].size_bytes == 45426483200

    def test_get_all_series_empty(self) -> None:
        with respx.mock(base_url=SONARR_URL) as mock:
            mock.get("/api/v3/series").mock(return_value=Response(200, json=[]))
            assert SonarrClient(SONARR_URL, "test-key").get_all_series() == []

    def test_delete_series(self) -> None:
        with respx.mock(base_url=SONARR_URL) as mock:
            mock.delete("/api/v3/series/1").mock(return_value=Response(200))
            SonarrClient(SONARR_URL, "test-key").delete_series(1)
            assert mock.calls.call_count == 1
