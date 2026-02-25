"""Tests for interactive delete TUI."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from plexbud.models import (
    DeletionImpact,
    DeletionPlan,
    FileLocation,
    MediaItem,
    StatsRow,
)
from plexbud.tui import DeleteApp, TUIData

PATCH_BUILD = "plexbud.services.deletion.build_deletion_plan"
PATCH_EXEC = "plexbud.services.deletion.execute_deletion_plan"


def _make_item(title: str, media_type: str, arr_id: int, size: int) -> MediaItem:
    return MediaItem(
        title=title,
        arr_id=arr_id,
        external_id=arr_id * 10,
        path=f"/media/{media_type}/{title}",
        size_bytes=size,
        added=datetime(2024, 1, 1),
        media_type=media_type,
    )


def _make_row(item: MediaItem) -> StatsRow:
    return StatsRow(
        title=item.title,
        size_bytes=item.size_bytes,
        last_watched=None,
        watch_count_30d=0,
        watch_count_all=0,
        added=item.added,
        location=FileLocation(),
        deletion_impact=DeletionImpact(
            total_bytes=item.size_bytes,
            freeable_bytes=item.size_bytes,
        ),
        media_type=item.media_type,
        arr_id=item.arr_id,
        external_id=item.external_id,
    )


def _make_data() -> TUIData:
    items = [
        _make_item("Breaking Bad", "tv", 1, 50_000_000_000),
        _make_item("The Wire", "tv", 2, 30_000_000_000),
        _make_item("Interstellar", "movie", 3, 20_000_000_000),
    ]
    rows = [_make_row(i) for i in items]
    rows.sort(key=lambda r: r.deletion_impact.total_bytes, reverse=True)

    mock_clients = MagicMock()
    mock_config = MagicMock()

    return TUIData(
        rows=rows,
        items_by_key={(i.media_type, i.arr_id): i for i in items},
        clients=mock_clients,
        config=mock_config,
        disk_total=100_000_000_000,
        disk_free=40_000_000_000,
    )


@pytest.mark.asyncio
async def test_main_screen_renders_items() -> None:
    """Main screen shows all items with 6 columns."""
    data = _make_data()
    app = DeleteApp(data)
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one("#media-table")
        assert table.row_count == 3
        assert len(table.columns) == 6


@pytest.mark.asyncio
async def test_filter_narrows_list() -> None:
    """Typing in the filter box narrows the table."""
    data = _make_data()
    app = DeleteApp(data)
    async with app.run_test() as pilot:
        await pilot.pause()
        filter_input = app.screen.query_one("#filter-input")
        filter_input.focus()
        await pilot.press("b", "r", "e", "a", "k")
        await pilot.pause()
        table = app.screen.query_one("#media-table")
        assert table.row_count == 1


@pytest.mark.asyncio
async def test_select_pushes_plan_screen() -> None:
    """Selecting an item pushes the plan screen."""
    data = _make_data()

    plan = DeletionPlan(
        title="Breaking Bad",
        media_type="tv",
        arr_id=1,
        media_dir="/media/tv/Breaking Bad",
        media_file_count=5,
        media_size_bytes=50_000_000_000,
        estimated_freed_bytes=50_000_000_000,
    )

    with patch(PATCH_BUILD, return_value=plan):
        app = DeleteApp(data)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.screen.query_one("#media-table")
            table.focus()
            await pilot.press("enter")
            # Wait for @work(thread=True) to complete and push screen
            await app.workers.wait_for_complete()
            await pilot.pause()

            # Plan screen should be pushed
            plan_text = app.screen.query_one("#plan-text")
            assert "Breaking Bad" in plan_text.content


@pytest.mark.asyncio
async def test_back_without_deleting() -> None:
    """Pressing escape on plan screen returns without changes."""
    data = _make_data()

    plan = DeletionPlan(
        title="Breaking Bad",
        media_type="tv",
        arr_id=1,
        estimated_freed_bytes=50_000_000_000,
    )

    with patch(PATCH_BUILD, return_value=plan):
        app = DeleteApp(data)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.screen.query_one("#media-table")
            table.focus()
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()

            # Press escape to go back
            await pilot.press("escape")
            await pilot.pause()

            # Should be back on main screen, all rows intact
            assert app.session_reclaimed == 0
            table = app.screen.query_one("#media-table")
            assert table.row_count == 3


@pytest.mark.asyncio
async def test_execution_updates_state() -> None:
    """Executing deletion updates reclaimed counter and removes item."""
    data = _make_data()
    freed = 50_000_000_000

    plan = DeletionPlan(
        title="Breaking Bad",
        media_type="tv",
        arr_id=1,
        estimated_freed_bytes=freed,
    )

    with (
        patch(PATCH_BUILD, return_value=plan),
        patch(PATCH_EXEC, return_value=["Removed 1 torrent(s)"]),
    ):
        app = DeleteApp(data)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.screen.query_one("#media-table")
            table.focus()
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()

            # Press d twice (first triggers confirm, second executes)
            await pilot.press("d")
            await pilot.pause()
            await pilot.press("d")
            await app.workers.wait_for_complete()
            await pilot.pause()

            # Should be back on main screen with updated state
            assert app.session_reclaimed == freed
            table = app.screen.query_one("#media-table")
            assert table.row_count == 2


@pytest.mark.asyncio
async def test_enter_from_filter_focuses_table() -> None:
    """Pressing Enter in the filter input focuses the table."""
    data = _make_data()
    app = DeleteApp(data)
    async with app.run_test() as pilot:
        await pilot.pause()
        filter_input = app.screen.query_one("#filter-input")
        filter_input.focus()
        await pilot.pause()
        assert filter_input.has_focus

        await pilot.press("enter")
        await pilot.pause()

        table = app.screen.query_one("#media-table")
        assert table.has_focus


@pytest.mark.asyncio
async def test_down_arrow_from_filter_focuses_table() -> None:
    """Pressing Down arrow in the filter input focuses the table."""
    data = _make_data()
    app = DeleteApp(data)
    async with app.run_test() as pilot:
        await pilot.pause()
        filter_input = app.screen.query_one("#filter-input")
        filter_input.focus()
        await pilot.pause()
        assert filter_input.has_focus

        await pilot.press("down")
        await pilot.pause()

        table = app.screen.query_one("#media-table")
        assert table.has_focus
