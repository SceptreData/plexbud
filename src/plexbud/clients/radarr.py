"""Radarr API client."""

from __future__ import annotations

from plexbud.clients.base import ArrClient, parse_datetime
from plexbud.models import MediaItem


class RadarrClient(ArrClient):
    service_name = "Radarr"

    def get_all_movies(self) -> list[MediaItem]:
        """Fetch all movies from Radarr."""
        data = self._get("/api/v3/movie", headers=self._headers)
        if not isinstance(data, list):
            return []

        items: list[MediaItem] = []
        for m in data:
            size = m.get("sizeOnDisk", 0) or m.get("movieFile", {}).get("size", 0)
            items.append(
                MediaItem(
                    title=m.get("title", "Unknown"),
                    arr_id=m.get("id", 0),
                    external_id=m.get("tmdbId", 0),
                    path=m.get("path", ""),
                    size_bytes=size,
                    added=parse_datetime(m.get("added", "")),
                    media_type="movie",
                )
            )
        return items

    def delete_movie(self, movie_id: int, *, delete_files: bool = True) -> None:
        """Delete a movie from Radarr."""
        self._arr_delete(f"/api/v3/movie/{movie_id}", delete_files=delete_files)
