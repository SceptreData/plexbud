"""Disk usage service — reads filesystem stats for configured paths."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from plexbud.config import Config
from plexbud.models import DiskInfo


def get_disk_usage(config: Config) -> list[DiskInfo]:
    """Get disk usage for all configured paths, deduplicated by device."""
    all_paths = config.paths.media_roots + config.paths.download_roots
    candidates = [p for p in all_paths if p]

    seen_devices: dict[int, str] = {}
    results: list[DiskInfo] = []

    for path_str in candidates:
        if not Path(path_str).exists():
            continue

        try:
            dev_id = os.stat(path_str).st_dev
        except OSError:
            continue

        if dev_id in seen_devices:
            continue
        seen_devices[dev_id] = path_str

        try:
            usage = shutil.disk_usage(path_str)
        except OSError:
            continue

        results.append(
            DiskInfo(
                path=path_str,
                total_bytes=usage.total,
                used_bytes=usage.used,
                free_bytes=usage.free,
            )
        )

    return results
