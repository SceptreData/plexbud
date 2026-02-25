"""Domain models for Plexbud."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from plexbud.domain_types import MediaType


@dataclass
class MediaItem:
    """A media item from Sonarr or Radarr."""

    title: str
    arr_id: int
    external_id: int  # tvdbId for TV, tmdbId for movies
    path: str
    size_bytes: int
    added: datetime
    media_type: MediaType


@dataclass
class WatchStats:
    """Watch statistics from Tautulli."""

    rating_key: int
    last_watched: datetime | None = None
    watch_count_30d: int = 0
    watch_count_all: int = 0


@dataclass
class FileLocation:
    """Where a media item's files live on disk."""

    media_paths: list[str] = field(default_factory=list)
    torrent_paths: list[str] = field(default_factory=list)
    usenet_paths: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        parts: list[str] = []
        if self.media_paths:
            parts.append("Plex")
        if self.torrent_paths:
            parts.append("Torrents")
        if self.usenet_paths:
            parts.append("Usenet")
        return " + ".join(parts) if parts else "Unknown"


@dataclass
class DeletionImpact:
    """How much space would actually be freed by deleting this item."""

    total_bytes: int = 0
    freeable_bytes: int = 0
    shared_inodes: int = 0  # inodes with links surviving outside deletion set

    @property
    def has_shared_links(self) -> bool:
        return self.shared_inodes > 0


@dataclass
class StatsRow:
    """One row in the stats output table."""

    title: str
    size_bytes: int
    last_watched: datetime | None
    watch_count_30d: int
    watch_count_all: int
    added: datetime
    location: FileLocation
    deletion_impact: DeletionImpact
    media_type: MediaType
    arr_id: int
    external_id: int


@dataclass
class TorrentInfo:
    """A torrent entry from qBittorrent."""

    hash: str
    name: str
    save_path: str
    size: int


@dataclass
class DeletionPlan:
    """What will be removed when deleting a media item."""

    title: str
    media_type: MediaType
    arr_id: int

    media_dir: str = ""
    media_file_count: int = 0
    media_size_bytes: int = 0

    torrent_paths: list[str] = field(default_factory=list)
    torrent_hashes: list[str] = field(default_factory=list)
    torrent_count: int = 0

    usenet_paths: list[str] = field(default_factory=list)

    estimated_freed_bytes: int = 0

    warnings: list[str] = field(default_factory=list)


@dataclass
class DiskInfo:
    """Disk usage info for a filesystem path."""

    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int

    @property
    def percent_used(self) -> float:
        if self.total_bytes == 0:
            return 0.0
        return (self.used_bytes / self.total_bytes) * 100
