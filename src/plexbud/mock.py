"""Mock clients for local development (PLEXBUD_MOCK=1)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from plexbud.config import (
    Config,
    PathsConfig,
    PlexConfig,
    QBittorrentConfig,
    RadarrConfig,
    SonarrConfig,
    TautulliConfig,
)
from plexbud.models import MediaItem, TorrentInfo, WatchStats

FIXTURES_DIR = Path(__file__).parent.parent.parent / "tests" / "fixtures"


def mock_config() -> Config:
    return Config(
        plex=PlexConfig(url="http://mock:32400", token="mock-token"),
        tautulli=TautulliConfig(
            url="http://mock:8181",
            api_key="mock-key",
            tv_section_id=1,
            movie_section_id=2,
        ),
        sonarr=SonarrConfig(url="http://mock:8989", api_key="mock-key"),
        radarr=RadarrConfig(url="http://mock:7878", api_key="mock-key"),
        qbittorrent=QBittorrentConfig(url="http://mock:8080", username="admin", password="mock"),
        paths=PathsConfig(
            media_movies="/mock/media/movies",
            media_tv="/mock/media/tv",
        ),
    )


def _load_fixture(service: str, name: str) -> Any:
    path = FIXTURES_DIR / service / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    return []


class MockSonarr:
    service_name = "Sonarr"

    def get_all_series(self) -> list[MediaItem]:
        data = _load_fixture("sonarr", "series")
        items: list[MediaItem] = []
        for s in data:
            stats = s.get("statistics", {})
            items.append(
                MediaItem(
                    title=s.get("title", "Unknown"),
                    arr_id=s.get("id", 0),
                    external_id=s.get("tvdbId", 0),
                    path=s.get("path", ""),
                    size_bytes=stats.get("sizeOnDisk", 0),
                    added=datetime.fromisoformat(s.get("added", "1970-01-01T00:00:00")),
                    media_type="tv",
                )
            )
        return items

    def delete_series(self, series_id: int, *, delete_files: bool = True) -> None:
        pass


class MockRadarr:
    service_name = "Radarr"

    def get_all_movies(self) -> list[MediaItem]:
        data = _load_fixture("radarr", "movies")
        items: list[MediaItem] = []
        for m in data:
            items.append(
                MediaItem(
                    title=m.get("title", "Unknown"),
                    arr_id=m.get("id", 0),
                    external_id=m.get("tmdbId", 0),
                    path=m.get("path", ""),
                    size_bytes=m.get("sizeOnDisk", 0),
                    added=datetime.fromisoformat(m.get("added", "1970-01-01T00:00:00")),
                    media_type="movie",
                )
            )
        return items

    def delete_movie(self, movie_id: int, *, delete_files: bool = True) -> None:
        pass


class MockTautulli:
    service_name = "Tautulli"

    def get_library_media_info(self, section_id: int) -> dict[int, int]:
        data = _load_fixture("tautulli", f"library_{section_id}")
        lookup: dict[int, int] = {}
        if isinstance(data, dict):
            items = data.get("data", [])
        elif isinstance(data, list):
            items = data
        else:
            return lookup
        for item in items:
            ext_id = item.get("external_id", 0)
            rk = item.get("rating_key", 0)
            if ext_id and rk:
                lookup[ext_id] = rk
        return lookup

    def get_watch_stats(self, rating_key: int, *, query_days: str = "30,0") -> WatchStats:
        data = _load_fixture("tautulli", "watch_stats")
        for entry in data:
            if entry.get("rating_key") == rating_key:
                return WatchStats(
                    rating_key=rating_key,
                    watch_count_30d=entry.get("watch_count_30d", 0),
                    watch_count_all=entry.get("watch_count_all", 0),
                )
        return WatchStats(rating_key=rating_key)

    def get_last_watched(self, rating_key: int) -> datetime | None:
        data = _load_fixture("tautulli", "last_watched")
        for entry in data:
            if entry.get("rating_key") == rating_key:
                ts = entry.get("timestamp")
                if ts:
                    return datetime.fromtimestamp(ts, tz=UTC)
        return None

    def get_activity(self) -> list[dict[str, Any]]:
        return []


class MockQBittorrent:
    service_name = "qBittorrent"

    def get_torrents(self) -> list[TorrentInfo]:
        data = _load_fixture("qbittorrent", "torrents")
        return [
            TorrentInfo(
                hash=t.get("hash", ""),
                name=t.get("name", ""),
                save_path=t.get("save_path", ""),
                size=t.get("size", 0),
            )
            for t in data
        ]

    def get_torrent_files(self, torrent_hash: str) -> list[str]:
        return []

    def delete_torrents(self, hashes: list[str], *, delete_files: bool = True) -> None:
        pass


class MockClients:
    def __init__(self) -> None:
        self.sonarr = MockSonarr()
        self.radarr = MockRadarr()
        self.tautulli = MockTautulli()
        self.qbittorrent = MockQBittorrent()
