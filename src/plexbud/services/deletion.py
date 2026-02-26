"""Deletion planning and execution service."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from plexbud.clients.base import APIError
from plexbud.config import Config
from plexbud.interfaces import QBittorrentAPI, RadarrAPI, SonarrAPI, TautulliAPI
from plexbud.models import DeletionPlan, MediaItem
from plexbud.services.hardlinks import collect_inodes, scan_file_locations


def _is_under_root(path: str, allowed_roots: list[str]) -> bool:
    """Check that a path is under one of the allowed root directories."""
    resolved = Path(path).resolve()
    return any(resolved.is_relative_to(Path(root).resolve()) for root in allowed_roots)


def _safe_size(f: Path) -> int:
    """Get file size, returning 0 if the file vanishes."""
    try:
        return f.stat().st_size
    except OSError:
        return 0


def build_deletion_plan(
    item: MediaItem,
    *,
    qbt: QBittorrentAPI,
    tautulli: TautulliAPI,
    config: Config,
) -> DeletionPlan:
    """Build a plan showing everything that will be removed."""
    plan = DeletionPlan(
        title=item.title,
        media_type=item.media_type,
        arr_id=item.arr_id,
    )

    # Scan filesystem locations
    location = scan_file_locations(
        item.path,
        torrents_root=config.paths.torrents_root,
        usenet_complete=config.paths.usenet_complete,
    )

    # Media directory info
    media_dir = Path(item.path)
    if media_dir.exists():
        plan.media_dir = str(media_dir)
        files = list(media_dir.rglob("*"))
        media_files = [f for f in files if f.is_file()]
        plan.media_file_count = len(media_files)
        plan.media_size_bytes = sum(_safe_size(f) for f in media_files)

    # Find matching torrents
    torrents = qbt.get_torrents()
    media_inodes = collect_inodes(item.path)

    for torrent in torrents:
        torrent_files = qbt.get_torrent_files(torrent.hash)
        torrent_dir = Path(torrent.save_path)
        for tf in torrent_files:
            full_path = torrent_dir / tf
            try:
                st = full_path.stat()
                if (st.st_dev, st.st_ino) in media_inodes:
                    plan.torrent_hashes.append(torrent.hash)
                    plan.torrent_paths.append(str(torrent_dir / tf.split("/")[0]))
                    break
            except OSError:
                continue

    plan.torrent_count = len(plan.torrent_hashes)

    # Find usenet leftovers
    plan.usenet_paths = location.usenet_paths

    # Estimate freed space (simplified - media size as baseline)
    plan.estimated_freed_bytes = plan.media_size_bytes

    # Safety warnings
    plan.warnings = _check_warnings(item, tautulli)

    return plan


def execute_deletion_plan(
    plan: DeletionPlan,
    *,
    qbt: QBittorrentAPI,
    sonarr: SonarrAPI | None = None,
    radarr: RadarrAPI | None = None,
    allowed_roots: list[str] | None = None,
) -> list[str]:
    """Execute a deletion plan in the correct order.

    Order: qBittorrent → usenet files → arr deletion.
    Returns a log of actions taken.
    """
    log: list[str] = []

    # 1. Remove torrents (stops seeding + removes source copies)
    if plan.torrent_hashes:
        qbt.delete_torrents(plan.torrent_hashes, delete_files=True)
        log.append(f"Removed {plan.torrent_count} torrent(s) from qBittorrent")

    # 2. Remove usenet leftovers
    for upath in plan.usenet_paths:
        if allowed_roots and not _is_under_root(upath, allowed_roots):
            log.append(f"Skipped {upath}: outside allowed roots")
            continue
        try:
            p = Path(upath)
            if p.is_file():
                os.unlink(upath)
                log.append(f"Deleted usenet file: {upath}")
        except OSError as e:
            log.append(f"Failed to delete {upath}: {e}")

    # 3. Remove from arr (deletes media files + adds exclusion)
    if plan.media_type == "tv" and sonarr:
        sonarr.delete_series(plan.arr_id)
        log.append(f"Deleted series from Sonarr (id={plan.arr_id})")
    elif plan.media_type == "movie" and radarr:
        radarr.delete_movie(plan.arr_id)
        log.append(f"Deleted movie from Radarr (id={plan.arr_id})")

    return log


def _check_warnings(
    item: MediaItem,
    tautulli: TautulliAPI,
) -> list[str]:
    """Generate safety warnings for a deletion."""
    warnings: list[str] = []

    # Check if currently being watched
    try:
        sessions: list[dict[str, Any]] = tautulli.get_activity()
        for session in sessions:
            titles = (session.get("grandparent_title"), session.get("title"))
            if item.title in titles:
                user = session.get("friendly_name", "someone")
                warnings.append(f'Currently being streamed by user "{user}"')
    except (APIError, httpx.HTTPError, OSError):
        pass

    # Check if recently added (within 14 days)
    age = datetime.now().astimezone() - item.added.astimezone()
    if age < timedelta(days=14):
        warnings.append(f"Added {age.days} days ago")

    return warnings
