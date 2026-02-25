"""Protocol interfaces for service clients."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from plexbud.models import MediaItem, TorrentInfo, WatchStats


class SonarrAPI(Protocol):
    def get_all_series(self) -> list[MediaItem]: ...

    def delete_series(self, series_id: int, *, delete_files: bool = True) -> None: ...


class RadarrAPI(Protocol):
    def get_all_movies(self) -> list[MediaItem]: ...

    def delete_movie(self, movie_id: int, *, delete_files: bool = True) -> None: ...


class TautulliAPI(Protocol):
    def get_library_media_info(self, section_id: int) -> dict[int, int]: ...

    def get_watch_stats(self, rating_key: int, *, query_days: str = "30,0") -> WatchStats: ...

    def get_last_watched(self, rating_key: int) -> datetime | None: ...

    def get_activity(self) -> list[dict[str, Any]]: ...


class QBittorrentAPI(Protocol):
    def get_torrents(self) -> list[TorrentInfo]: ...

    def get_torrent_files(self, torrent_hash: str) -> list[str]: ...

    def delete_torrents(self, hashes: list[str], *, delete_files: bool = True) -> None: ...
