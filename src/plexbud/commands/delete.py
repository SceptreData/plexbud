"""Delete CLI commands."""

from __future__ import annotations

import shutil
from typing import Annotated

import click
import typer
from rich.console import Console
from rich.status import Status

from plexbud.commands._shared import (
    get_clients_and_config,
    get_disk_path_for_media,
    get_media_items,
    get_stats_rows_for_media,
    media_label,
)
from plexbud.domain_types import MediaType

delete_app = typer.Typer(help="Delete media items completely (arr + torrents + files).")


def _parse_media(s: str) -> MediaType:
    """Parse command-facing media label to domain media type."""
    value = s.strip().lower()
    if value in {"movie", "movies"}:
        return "movie"
    if value == "tv":
        return "tv"
    raise typer.BadParameter(f"Invalid media type: {s!r} (expected tv or movie)")


def _launch_tui(media_filter: str) -> None:
    """Compatibility wrapper used by tests and CLI callbacks."""
    _launch_tui_for_media(_parse_media(media_filter))


def _launch_tui_for_media(media: MediaType) -> None:
    """Load data and launch the interactive delete TUI."""
    from plexbud.models import MediaItem
    from plexbud.tui import TUIData, run_delete_tui

    clients, config = get_clients_and_config()
    console = Console()

    with Status("Loading media library...", console=console):
        items = get_media_items(clients, media)
        rows = get_stats_rows_for_media(clients, config, media)
        rows.sort(key=lambda r: r.deletion_impact.total_bytes, reverse=True)

        items_by_key: dict[tuple[MediaType, int], MediaItem] = {
            (item.media_type, item.arr_id): item for item in items
        }

        try:
            usage = shutil.disk_usage(get_disk_path_for_media(config, media))
            disk_total, disk_free = usage.total, usage.free
        except OSError:
            disk_total, disk_free = 0, 0

    data = TUIData(
        rows=rows,
        items_by_key=items_by_key,
        clients=clients,
        config=config,
        disk_total=disk_total,
        disk_free=disk_free,
    )
    run_delete_tui(data)


def _delete_item(name: str, media_type: str, *, apply: bool, yes: bool) -> None:
    """Shared logic for deleting a TV series or movie."""
    from plexbud.output import render_deletion_plan
    from plexbud.services.deletion import build_deletion_plan, execute_deletion_plan

    media = _parse_media(media_type)
    clients, config = get_clients_and_config()
    console = Console()

    all_items = get_media_items(clients, media)
    matches = [i for i in all_items if name.lower() in i.title.lower()]

    if not matches:
        console.print(f"[red]No {media_label(media)} matching '{name}' found.[/red]")
        raise typer.Exit(1)

    if len(matches) > 1:
        console.print(f"[yellow]Multiple matches for '{name}':[/yellow]")
        for m in matches:
            console.print(f"  - {m.title}")
        console.print("[yellow]Please be more specific.[/yellow]")
        raise typer.Exit(1)

    item = matches[0]
    deletion_plan = build_deletion_plan(
        item,
        qbt=clients.qbittorrent,
        tautulli=clients.tautulli,
        config=config,
    )
    render_deletion_plan(deletion_plan, console=console)

    if not apply:
        return

    if not yes and not typer.confirm("Proceed with deletion?"):
        console.print("[dim]Cancelled.[/dim]")
        raise typer.Exit(0)

    log = execute_deletion_plan(
        deletion_plan,
        qbt=clients.qbittorrent,
        sonarr=clients.sonarr if media == "tv" else None,
        radarr=clients.radarr if media == "movie" else None,
    )
    for entry in log:
        console.print(f"  [green]OK[/green] {entry}")
    console.print(f"\n[bold green]Done.[/bold green] {item.title} has been removed.")


@delete_app.callback(invoke_without_command=True)
def delete_callback(ctx: typer.Context) -> None:
    """Delete media items completely (arr + torrents + files)."""
    if ctx.invoked_subcommand is not None:
        return
    choice = typer.prompt("Delete from", type=click.Choice(["tv", "movies"]))
    _launch_tui(media_filter=choice)


@delete_app.command("tv")
def delete_tv(
    name: Annotated[str | None, typer.Argument(help="TV show name (or substring)")] = None,
    apply: Annotated[bool, typer.Option("--apply", help="Execute deletion")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Delete a TV series from all services."""
    if name is None:
        _launch_tui(media_filter="tv")
        return
    _delete_item(name, "tv", apply=apply, yes=yes)


@delete_app.command("movie")
def delete_movie(
    name: Annotated[str | None, typer.Argument(help="Movie name (or substring)")] = None,
    apply: Annotated[bool, typer.Option("--apply", help="Execute deletion")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Delete a movie from all services."""
    if name is None:
        _launch_tui(media_filter="movie")
        return
    _delete_item(name, "movie", apply=apply, yes=yes)
