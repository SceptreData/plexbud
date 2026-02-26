"""Tautulli API client."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from plexbud.clients.base import BaseClient
from plexbud.models import WatchStats


class TautulliClient(BaseClient):
    service_name = "Tautulli"

    def __init__(self, base_url: str, api_key: str) -> None:
        super().__init__(base_url)
        self._api_key = api_key

    def _api(self, cmd: str, **params: str | int) -> Any:
        """Call a Tautulli API command."""
        all_params: dict[str, str | int] = {
            "apikey": self._api_key,
            "cmd": cmd,
        }
        all_params.update(params)
        data = self._get("/api/v2", params=all_params)
        if isinstance(data, dict):
            return data.get("response", {}).get("data", {})
        return data

    def get_library_media_info(self, section_id: int, *, provider: str = "") -> dict[int, int]:
        """Fetch all items in a library and build {external_id: rating_key} lookup.

        Works through pagination to get all items.
        """
        lookup: dict[int, int] = {}
        start = 0
        length = 500

        while True:
            data = self._api(
                "get_library_media_info",
                section_id=section_id,
                length=length,
                start=start,
            )
            items = data.get("data", []) if isinstance(data, dict) else []
            if not items:
                break

            for item in items:
                guids = item.get("guids", [])
                guid = item.get("guid", "")
                rating_key = int(item.get("rating_key", 0))
                if not rating_key:
                    continue

                for ext_id in _extract_external_ids(guid, guids, provider=provider):
                    lookup[ext_id] = rating_key

            total = int(data.get("recordsTotal", 0)) if isinstance(data, dict) else 0
            start += length
            if start >= total:
                break

        return lookup

    def get_watch_stats(self, rating_key: int, *, query_days: str = "30,0") -> WatchStats:
        """Fetch watch time stats for a specific item."""
        data = self._api(
            "get_item_watch_time_stats",
            rating_key=rating_key,
            grouping=1,
            query_days=query_days,
        )

        stats = WatchStats(rating_key=rating_key)
        if not isinstance(data, list):
            return stats

        for entry in data:
            days = entry.get("query_days", 0)
            count = entry.get("total_plays", 0)
            if days == 30:
                stats.watch_count_30d = count
            elif days == 0:
                stats.watch_count_all = count

        return stats

    def get_last_watched(self, rating_key: int) -> datetime | None:
        """Get the last watched date for an item."""
        data = self._api(
            "get_history",
            rating_key=rating_key,
            length=1,
        )
        if not isinstance(data, dict):
            return None

        records = data.get("data", [])
        if not records:
            return None

        timestamp = records[0].get("stopped", 0) or records[0].get("started", 0)
        if not timestamp:
            return None

        return datetime.fromtimestamp(int(timestamp), tz=UTC)

    def get_activity(self) -> list[dict[str, Any]]:
        """Get currently active streams (for safety warnings)."""
        data = self._api("get_activity")
        if isinstance(data, dict):
            sessions = data.get("sessions", [])
            if isinstance(sessions, list):
                return [s for s in sessions if isinstance(s, dict)]
        return []


def _extract_external_ids(guid: str, guids: list[str], *, provider: str = "") -> list[int]:
    """Extract tvdb/tmdb IDs from Plex guid formats.

    Handles both legacy and modern formats:
    - Legacy: "com.plexapp.agents.thetvdb://270408?lang=en"
    - Modern guids list: ["tvdb://12345", "tmdb://67890"]

    When provider is set (e.g. "tvdb" or "tmdb"), only match that
    provider to avoid cross-provider ID collisions.
    """
    ids: list[int] = []

    modern_pattern = rf"(?:{provider})://(\d+)" if provider else r"(?:tvdb|tmdb)://(\d+)"

    # Map modern provider names to legacy agent names
    legacy_map = {"tvdb": "thetvdb", "tmdb": "themoviedb"}
    if provider:
        legacy_name = legacy_map.get(provider, provider)
        legacy_pattern = rf"(?:{legacy_name})://(\d+)"
    else:
        legacy_pattern = r"(?:thetvdb|themoviedb)://(\d+)"

    # Modern format: list of "provider://id" strings
    for g in guids:
        if isinstance(g, str):
            match = re.match(modern_pattern, g)
            if match:
                ids.append(int(match.group(1)))
        elif isinstance(g, dict):
            # Sometimes guids are dicts like {"id": "tvdb://12345"}
            gid = g.get("id", "")
            match = re.match(modern_pattern, gid)
            if match:
                ids.append(int(match.group(1)))

    # Legacy format: agent string with embedded ID
    if guid:
        match = re.search(legacy_pattern, guid)
        if match:
            ids.append(int(match.group(1)))

    return ids
