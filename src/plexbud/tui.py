"""Interactive delete TUI using Textual."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from typing import cast

from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Label, Static

from plexbud.commands._shared import Clients
from plexbud.config import Config
from plexbud.domain_types import MediaType
from plexbud.models import DeletionPlan, MediaItem, StatsRow
from plexbud.output import format_size


@dataclass
class TUIData:
    rows: list[StatsRow]
    items_by_key: dict[tuple[MediaType, int], MediaItem]
    clients: Clients
    config: Config
    disk_total: int
    disk_free: int


class StatsBar(Static):
    """Disk usage bar at the top."""

    def update_stats(self, total: int, free: int, reclaimed: int) -> None:
        from rich.text import Text

        text = Text.assemble(
            " Disk: ",
            (format_size(total), "bold"),
            " total | ",
            (format_size(free), "green"),
            " free | Reclaimed: ",
            (format_size(reclaimed), "yellow"),
        )
        self.update(text)


class PlanScreen(Screen[bool]):
    """Shows deletion plan for a single item, allows execution."""

    BINDINGS = [
        Binding("d", "delete", "Delete"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, item: MediaItem, plan: DeletionPlan) -> None:
        super().__init__()
        self.item = item
        self.plan = plan
        self._executed = False
        self._confirm_pending = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(self._render_plan(), id="plan-text")
        yield Label("", id="status-text")
        yield Footer()

    def _render_plan(self) -> str:
        from rich.console import Console

        from plexbud.output import render_deletion_plan

        buf = StringIO()
        console = Console(file=buf, force_terminal=False, width=100)
        render_deletion_plan(self.plan, console=console)
        return buf.getvalue()

    def action_back(self) -> None:
        self.dismiss(self._executed)

    def action_delete(self) -> None:
        if self._executed:
            return
        status = self.query_one("#status-text", Label)
        status.update("Confirm deletion? Press 'd' again to confirm, Escape to cancel.")
        self.set_class(True, "-confirming")
        self._confirm_pending = True

    def key_d(self) -> None:
        if self._confirm_pending:
            self._confirm_pending = False
            self._do_delete()

    @work(thread=True)
    def _do_delete(self) -> None:
        from plexbud.services.deletion import execute_deletion_plan

        app = self.app
        assert isinstance(app, DeleteApp)

        try:
            log = execute_deletion_plan(
                self.plan,
                qbt=app.data.clients.qbittorrent,
                sonarr=app.data.clients.sonarr if self.item.media_type == "tv" else None,
                radarr=app.data.clients.radarr if self.item.media_type == "movie" else None,
                allowed_roots=(
                    app.data.config.paths.media_roots + app.data.config.paths.download_roots
                ),
            )
        except Exception as exc:
            msg = f"Error: {exc}"
            self.app.call_from_thread(lambda: self.query_one("#status-text", Label).update(msg))
            return

        self._executed = True
        freed = self.plan.estimated_freed_bytes

        for entry in log:
            self.app.call_from_thread(
                lambda e=entry: self.query_one("#status-text", Label).update(f"OK: {e}")
            )

        def finish() -> None:
            app.session_reclaimed += freed
            app.disk_free += freed
            # Remove from rows
            app.rows = [
                r
                for r in app.rows
                if not (r.media_type == self.item.media_type and r.arr_id == self.item.arr_id)
            ]
            self.dismiss(True)

        self.app.call_from_thread(finish)


class MainScreen(Screen[None]):
    """Browse media sorted by size, filter, and select for deletion."""

    BINDINGS = [
        Binding("escape", "quit", "Quit"),
        Binding("/", "focus_filter", "Search"),
    ]

    def __init__(self, data: TUIData) -> None:
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header()
        yield StatsBar(id="stats-bar")
        yield Input(placeholder="Type to search...", id="filter-input")
        yield DataTable(id="media-table")
        yield Footer()

    def on_mount(self) -> None:
        app = self.app
        assert isinstance(app, DeleteApp)
        self._refresh_stats_bar()

        table = self.query_one("#media-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Title", "Type", "Size", "30d", "All", "Freeable")
        self._populate_table()

    def _refresh_stats_bar(self) -> None:
        app = self.app
        assert isinstance(app, DeleteApp)
        bar = self.query_one("#stats-bar", StatsBar)
        bar.update_stats(app.data.disk_total, app.disk_free, app.session_reclaimed)

    def _populate_table(self, filter_text: str = "") -> None:
        from rich.text import Text

        app = self.app
        assert isinstance(app, DeleteApp)
        table = self.query_one("#media-table", DataTable)
        table.clear()

        needle = filter_text.lower()
        for row in app.rows:
            if needle and needle not in row.title.lower():
                continue
            key = f"{row.media_type}:{row.arr_id}"
            table.add_row(
                Text(row.title, style="bold"),
                Text(row.media_type.upper(), style="dim"),
                Text(format_size(row.size_bytes), style="cyan"),
                Text(str(row.watch_count_30d), style="yellow"),
                Text(str(row.watch_count_all), style="yellow"),
                Text(format_size(row.deletion_impact.freeable_bytes), style="green"),
                key=key,
            )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "filter-input":
            table = self.query_one("#media-table", DataTable)
            table.focus()

    def on_key(self, event: events.Key) -> None:
        filter_input = self.query_one("#filter-input", Input)
        if not filter_input.has_focus:
            return
        if event.key == "down":
            self.query_one("#media-table", DataTable).focus()
            event.prevent_default()
        elif event.key == "escape":
            filter_input.value = ""
            self.query_one("#media-table", DataTable).focus()
            event.prevent_default()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter-input":
            self._populate_table(event.value)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value is None:
            return
        app = self.app
        assert isinstance(app, DeleteApp)
        parts = str(event.row_key.value).split(":", 1)
        media_type_raw = parts[0]
        if media_type_raw not in {"tv", "movie"}:
            return
        media_type = cast(MediaType, media_type_raw)
        arr_id = int(parts[1])
        item = app.data.items_by_key.get((media_type, arr_id))
        if item is None:
            return
        self._show_plan(item)

    @work(thread=True)
    def _show_plan(self, item: MediaItem) -> None:
        from plexbud.services.deletion import build_deletion_plan

        app = self.app
        assert isinstance(app, DeleteApp)

        plan = build_deletion_plan(
            item,
            qbt=app.data.clients.qbittorrent,
            tautulli=app.data.clients.tautulli,
            config=app.data.config,
        )

        def push() -> None:
            self.app.push_screen(PlanScreen(item, plan), callback=self._on_plan_dismiss)

        self.app.call_from_thread(push)

    def _on_plan_dismiss(self, executed: bool | None) -> None:
        if executed:
            self._refresh_stats_bar()
            filter_input = self.query_one("#filter-input", Input)
            self._populate_table(filter_input.value)

    def action_focus_filter(self) -> None:
        self.query_one("#filter-input", Input).focus()

    def action_quit(self) -> None:
        self.app.exit()


class DeleteApp(App[None]):
    """Interactive delete TUI application."""

    TITLE = "plexbud delete"
    CSS = """
    #stats-bar {
        dock: top;
        height: 1;
        background: $surface;
        padding: 0 1;
    }
    #filter-input {
        dock: top;
        margin: 0 0;
    }
    #media-table {
        height: 1fr;
    }
    #plan-text {
        padding: 1 2;
        height: auto;
    }
    #status-text {
        dock: bottom;
        height: auto;
        padding: 0 2;
        color: $success;
    }
    .-confirming #status-text {
        color: $warning;
    }
    """

    def __init__(self, data: TUIData) -> None:
        super().__init__()
        self.data = data
        self.rows = list(data.rows)
        self.session_reclaimed = 0
        self.disk_free = data.disk_free

    def on_mount(self) -> None:
        self.push_screen(MainScreen(self.data))


def run_delete_tui(data: TUIData) -> None:
    app = DeleteApp(data)
    app.run()
