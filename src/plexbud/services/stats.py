"""Stats aggregation service - cross-service data joining."""

from __future__ import annotations

from plexbud.config import Config
from plexbud.interfaces import TautulliAPI
from plexbud.models import DeletionImpact, FileLocation, MediaItem, StatsRow
from plexbud.services.hardlinks import (
    build_inode_index,
    calculate_deletion_impact,
    scan_file_locations,
)


def build_stats_rows(
    items: list[MediaItem],
    id_lookup: dict[int, int],
    tautulli: TautulliAPI,
    config: Config,
) -> list[StatsRow]:
    """Build StatsRow list from media items + Tautulli data."""
    rows: list[StatsRow] = []

    # Pre-scan download roots once to avoid O(items * files) walks
    download_index = build_inode_index(config.paths.torrents_root, config.paths.usenet_complete)

    for item in items:
        # Look up Plex rating_key via external ID
        rating_key = id_lookup.get(item.external_id)

        # Fetch watch stats if we found a match
        watch_count_30d = 0
        watch_count_all = 0
        last_watched = None

        if rating_key:
            watch_stats = tautulli.get_watch_stats(rating_key)
            watch_count_30d = watch_stats.watch_count_30d
            watch_count_all = watch_stats.watch_count_all
            last_watched = tautulli.get_last_watched(rating_key)

        # Scan filesystem for file locations
        location = scan_file_locations(
            item.path,
            torrents_root=config.paths.torrents_root,
            usenet_complete=config.paths.usenet_complete,
            download_index=download_index,
        )

        # Calculate deletion impact
        deletion_impact = calculate_deletion_impact(item.path, location)

        # If no filesystem access (e.g. remote/mock), use API size
        if deletion_impact.total_bytes == 0 and item.size_bytes > 0:
            deletion_impact = DeletionImpact(
                total_bytes=item.size_bytes,
                freeable_bytes=item.size_bytes,
            )

        rows.append(
            StatsRow(
                title=item.title,
                size_bytes=item.size_bytes,
                last_watched=last_watched,
                watch_count_30d=watch_count_30d,
                watch_count_all=watch_count_all,
                added=item.added,
                location=location if location.media_paths else FileLocation(),
                deletion_impact=deletion_impact,
                media_type=item.media_type,
                arr_id=item.arr_id,
                external_id=item.external_id,
            )
        )

    return rows
