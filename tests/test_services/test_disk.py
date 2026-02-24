"""Tests for disk usage service."""

from __future__ import annotations

from collections import namedtuple
from unittest.mock import patch

from plexbud.config import Config, PathsConfig
from plexbud.models import DiskInfo
from plexbud.services.disk import get_disk_usage

_Usage = namedtuple("usage", ["total", "used", "free"])


class TestDiskInfoModel:
    """Test DiskInfo dataclass."""

    def test_creation(self) -> None:
        info = DiskInfo(
            path="/volume1/media",
            total_bytes=2_000_000_000_000,
            used_bytes=1_600_000_000_000,
            free_bytes=400_000_000_000,
        )
        assert info.path == "/volume1/media"
        assert info.total_bytes == 2_000_000_000_000

    def test_percent_used(self) -> None:
        info = DiskInfo(
            path="/volume1/media",
            total_bytes=1000,
            used_bytes=750,
            free_bytes=250,
        )
        assert info.percent_used == 75.0

    def test_percent_used_zero_total(self) -> None:
        info = DiskInfo(
            path="/empty",
            total_bytes=0,
            used_bytes=0,
            free_bytes=0,
        )
        assert info.percent_used == 0.0


def _fake_disk_usage(path: str) -> _Usage:
    """Return (total, used, free) for test paths."""
    return _Usage(2_000_000_000_000, 1_600_000_000_000, 400_000_000_000)


def _fake_stat(path: str) -> object:
    """Return fake stat result. Same st_dev for same parent dir."""

    class FakeStat:
        st_dev = hash(path.rsplit("/", 1)[0]) if "/" in path else hash(path)

    return FakeStat()


class TestGetDiskUsage:
    """Test get_disk_usage service function."""

    def test_returns_disk_info_for_configured_paths(self) -> None:
        config = Config(
            paths=PathsConfig(
                media_movies="/volume1/media/movies",
                media_tv="/volume1/media/tv",
            ),
        )
        with (
            patch(
                "plexbud.services.disk.shutil.disk_usage",
                side_effect=_fake_disk_usage,
            ),
            patch("plexbud.services.disk.os.stat", side_effect=_fake_stat),
            patch("plexbud.services.disk.Path.exists", return_value=True),
        ):
            result = get_disk_usage(config)

        assert len(result) >= 1
        assert all(isinstance(r, DiskInfo) for r in result)

    def test_deduplicates_same_device(self) -> None:
        """Paths on the same device should produce one DiskInfo entry."""
        config = Config(
            paths=PathsConfig(
                media_movies="/volume1/media/movies",
                media_tv="/volume1/media/tv",
            ),
        )

        class FakeStat:
            st_dev = 12345  # same device for all paths

        with (
            patch(
                "plexbud.services.disk.shutil.disk_usage",
                side_effect=_fake_disk_usage,
            ),
            patch("plexbud.services.disk.os.stat", return_value=FakeStat()),
            patch("plexbud.services.disk.Path.exists", return_value=True),
        ):
            result = get_disk_usage(config)

        assert len(result) == 1

    def test_skips_nonexistent_paths(self) -> None:
        config = Config(
            paths=PathsConfig(
                media_movies="/nonexistent/path",
                media_tv="/also/nonexistent",
            ),
        )
        with patch("plexbud.services.disk.Path.exists", return_value=False):
            result = get_disk_usage(config)

        assert result == []

    def test_skips_empty_paths(self) -> None:
        config = Config(
            paths=PathsConfig(
                media_movies="/volume1/media/movies",
                media_tv="",
            ),
        )

        class FakeStat:
            st_dev = 12345

        with (
            patch(
                "plexbud.services.disk.shutil.disk_usage",
                side_effect=_fake_disk_usage,
            ),
            patch("plexbud.services.disk.os.stat", return_value=FakeStat()),
            patch("plexbud.services.disk.Path.exists", return_value=True),
        ):
            result = get_disk_usage(config)

        assert len(result) == 1
