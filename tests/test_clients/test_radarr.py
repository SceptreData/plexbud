"""Tests for Radarr client."""

from __future__ import annotations

import respx
from httpx import Response

from plexbud.clients.radarr import RadarrClient

RADARR_URL = "http://radarr:7878"


class TestRadarrClient:
    def test_get_all_movies(self, radarr_mock: respx.MockRouter) -> None:
        movies = RadarrClient(RADARR_URL, "test-key").get_all_movies()

        assert len(movies) == 4
        assert movies[0].title == "Interstellar"
        assert movies[0].external_id == 157336
        assert movies[0].media_type == "movie"

    def test_get_all_movies_empty(self) -> None:
        with respx.mock(base_url=RADARR_URL) as mock:
            mock.get("/api/v3/movie").mock(return_value=Response(200, json=[]))
            assert RadarrClient(RADARR_URL, "test-key").get_all_movies() == []

    def test_delete_movie(self) -> None:
        with respx.mock(base_url=RADARR_URL) as mock:
            mock.delete("/api/v3/movie/1").mock(return_value=Response(200))
            RadarrClient(RADARR_URL, "test-key").delete_movie(1)
            assert mock.calls.call_count == 1
