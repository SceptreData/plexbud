"""Sonarr API client."""

from __future__ import annotations

from plexbud.clients.base import ArrClient, parse_datetime
from plexbud.models import MediaItem


class SonarrClient(ArrClient):
    service_name = "Sonarr"

    def get_all_series(self) -> list[MediaItem]:
        """Fetch all series from Sonarr."""
        data = self._get("/api/v3/series", headers=self._headers)
        if not isinstance(data, list):
            return []

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
                    added=parse_datetime(s.get("added", "")),
                    media_type="tv",
                )
            )
        return items

    def delete_series(self, series_id: int, *, delete_files: bool = True) -> None:
        """Delete a series from Sonarr."""
        self._arr_delete(f"/api/v3/series/{series_id}")
