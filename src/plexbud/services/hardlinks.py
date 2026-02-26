"""Inode-aware size calculation for hardlinked files."""

from __future__ import annotations

import os
from pathlib import Path

from plexbud.models import DeletionImpact, FileLocation


def walk_files(directory: Path) -> list[Path]:
    """Recursively list all files in a directory."""
    files: list[Path] = []
    try:
        for entry in directory.rglob("*"):
            if entry.is_file() and not entry.is_symlink():
                files.append(entry)
    except OSError:
        pass
    return files


def collect_inodes(path: str) -> set[tuple[int, int]]:
    """Collect all file (device, inode) pairs under a path."""
    inodes: set[tuple[int, int]] = set()
    p = Path(path)
    if not p.exists():
        return inodes
    for f in walk_files(p):
        try:
            st = f.lstat()
            inodes.add((st.st_dev, st.st_ino))
        except OSError:
            continue
    return inodes


def build_inode_index(*roots: str) -> dict[tuple[int, int], list[str]]:
    """Walk roots once and build {(dev, ino): [path, ...]} index."""
    index: dict[tuple[int, int], list[str]] = {}
    for root in roots:
        if not root:
            continue
        root_dir = Path(root)
        if not root_dir.exists():
            continue
        for f in walk_files(root_dir):
            try:
                st = f.lstat()
                index.setdefault((st.st_dev, st.st_ino), []).append(str(f))
            except OSError:
                continue
    return index


def _is_subpath(path: str, parent: str) -> bool:
    """Check if path is under parent directory."""
    return Path(path).resolve().is_relative_to(Path(parent).resolve())


def scan_file_locations(
    media_path: str,
    *,
    torrents_root: str = "",
    usenet_complete: str = "",
    download_index: dict[tuple[int, int], list[str]] | None = None,
) -> FileLocation:
    """Scan configured roots to find where a media item's files live.

    Given the media path (e.g. /volume1/data/media/tv/Show Name/), find
    matching files in torrent and usenet directories by comparing inodes.

    When download_index is provided, uses it instead of re-walking the
    download roots (much faster for multiple items).
    """
    location = FileLocation()
    media_dir = Path(media_path)

    if not media_dir.exists():
        return location

    # Collect inodes from media directory
    media_inodes: set[tuple[int, int]] = set()
    for f in walk_files(media_dir):
        location.media_paths.append(str(f))
        try:
            st = f.lstat()
            media_inodes.add((st.st_dev, st.st_ino))
        except OSError:
            continue

    if download_index is not None:
        # Use pre-built index for O(1) lookups
        for ino in media_inodes:
            for match_path in download_index.get(ino, []):
                if torrents_root and _is_subpath(match_path, torrents_root):
                    location.torrent_paths.append(match_path)
                elif usenet_complete and _is_subpath(match_path, usenet_complete):
                    location.usenet_paths.append(match_path)
    else:
        # Fallback: walk download roots directly
        scan_roots = [
            (torrents_root, location.torrent_paths),
            (usenet_complete, location.usenet_paths),
        ]
        for root, target_list in scan_roots:
            if not root:
                continue
            root_dir = Path(root)
            if not root_dir.exists():
                continue
            for f in walk_files(root_dir):
                try:
                    st = f.lstat()
                    if (st.st_dev, st.st_ino) in media_inodes:
                        target_list.append(str(f))
                except OSError:
                    continue

    return location


def calculate_deletion_impact(
    media_path: str,
    location: FileLocation,
) -> DeletionImpact:
    """Calculate how much space would actually be freed by deleting this item.

    Uses inode analysis: space is only freed when ALL hardlinks to an inode
    are removed. If any link survives outside the deletion set, no space
    is freed for that inode.
    """
    impact = DeletionImpact()
    media_dir = Path(media_path)

    if not media_dir.exists():
        return impact

    # Build inode count map from deletion set in a single pass
    deletion_inode_counts: dict[tuple[int, int], int] = {}
    all_deletion_paths = (
        list(location.media_paths) + list(location.torrent_paths) + list(location.usenet_paths)
    )
    for p in all_deletion_paths:
        try:
            st = os.lstat(p)
            key = (st.st_dev, st.st_ino)
            deletion_inode_counts[key] = deletion_inode_counts.get(key, 0) + 1
        except OSError:
            continue

    # Analyze each file's inode
    seen_inodes: set[tuple[int, int]] = set()

    for f in walk_files(media_dir):
        try:
            stat = f.lstat()
        except OSError:
            continue

        ino = (stat.st_dev, stat.st_ino)
        if ino in seen_inodes:
            continue
        seen_inodes.add(ino)

        size = stat.st_size
        nlink = stat.st_nlink
        impact.total_bytes += size

        links_in_deletion = deletion_inode_counts.get(ino, 0)

        if links_in_deletion >= nlink:
            # All links will be removed -> space is freed
            impact.freeable_bytes += size
        else:
            # Some links survive -> space is NOT freed
            impact.shared_inodes += 1

    return impact
