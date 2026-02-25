"""Tests for qBittorrent client."""

from __future__ import annotations

import respx

from plexbud.clients.qbittorrent import QBittorrentClient

QBT_URL = "http://qbt:8080"


def _client() -> QBittorrentClient:
    return QBittorrentClient(QBT_URL, "admin", "pass")


class TestQBittorrentClient:
    def test_get_torrents(self, qbt_mock: respx.MockRouter) -> None:
        torrents = _client().get_torrents()

        assert len(torrents) == 3
        assert torrents[0].name == "Breaking.Bad.S01-S05.BluRay.1080p"
        assert torrents[0].hash == "abc123def456"

    def test_delete_torrents(self, qbt_mock: respx.MockRouter) -> None:
        _client().delete_torrents(["abc123def456"])
        post_calls = [c for c in qbt_mock.calls if c.request.method == "POST"]
        assert len(post_calls) == 2
