"""Tests for disk usage service."""

from __future__ import annotations

from plexbud.models import DiskInfo


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
