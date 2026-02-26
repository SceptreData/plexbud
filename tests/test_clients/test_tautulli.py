"""Tests for Tautulli client."""

from __future__ import annotations

import respx

from plexbud.clients.tautulli import TautulliClient, _extract_external_ids


class TestTautulliClient:
    def test_get_watch_stats(self, tautulli_mock: respx.MockRouter) -> None:
        client = TautulliClient("http://tautulli:8181", "test-key")
        stats = client.get_watch_stats(1001)

        assert stats.rating_key == 1001
        assert stats.watch_count_30d == 2
        assert stats.watch_count_all == 10

    def test_get_last_watched(self, tautulli_mock: respx.MockRouter) -> None:
        client = TautulliClient("http://tautulli:8181", "test-key")
        dt = client.get_last_watched(1001)

        assert dt is not None
        assert dt.year == 2025

    def test_get_activity(self, tautulli_mock: respx.MockRouter) -> None:
        client = TautulliClient("http://tautulli:8181", "test-key")
        sessions = client.get_activity()
        assert sessions == []


class TestExtractExternalIds:
    def test_modern_format_string(self) -> None:
        ids = _extract_external_ids("", ["tvdb://81189", "tmdb://1396"])
        assert 81189 in ids
        assert 1396 in ids

    def test_modern_format_dict(self) -> None:
        ids = _extract_external_ids("", [{"id": "tvdb://81189"}, {"id": "tmdb://1396"}])
        assert 81189 in ids

    def test_legacy_format(self) -> None:
        ids = _extract_external_ids("com.plexapp.agents.thetvdb://81189?lang=en", [])
        assert 81189 in ids

    def test_empty(self) -> None:
        ids = _extract_external_ids("", [])
        assert ids == []

    def test_provider_filter_tvdb(self) -> None:
        ids = _extract_external_ids("", ["tvdb://81189", "tmdb://1396"], provider="tvdb")
        assert 81189 in ids
        assert 1396 not in ids

    def test_provider_filter_tmdb(self) -> None:
        ids = _extract_external_ids("", ["tvdb://81189", "tmdb://1396"], provider="tmdb")
        assert 1396 in ids
        assert 81189 not in ids

    def test_provider_filter_legacy(self) -> None:
        ids = _extract_external_ids(
            "com.plexapp.agents.thetvdb://81189?lang=en", [], provider="tvdb"
        )
        assert 81189 in ids
