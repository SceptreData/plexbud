"""Tests for stats service."""

from __future__ import annotations

from datetime import datetime

from plexbud.models import MediaItem, WatchStats


class TestStatsRow:
    """Test stats row assembly logic."""

    def test_media_item_creation(self) -> None:
        item = MediaItem(
            title="Test Show",
            arr_id=1,
            external_id=12345,
            path="/media/tv/Test Show",
            size_bytes=1024 * 1024 * 1024,
            added=datetime(2024, 1, 1),
            media_type="tv",
        )
        assert item.title == "Test Show"
        assert item.media_type == "tv"

    def test_watch_stats_defaults(self) -> None:
        stats = WatchStats(rating_key=100)
        assert stats.last_watched is None
        assert stats.watch_count_30d == 0
        assert stats.watch_count_all == 0
