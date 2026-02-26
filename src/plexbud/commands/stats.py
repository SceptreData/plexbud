"""Stats CLI commands."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast

import typer
from rich.console import Console

from plexbud.commands._shared import Clients, get_clients_and_config, get_stats_rows_for_media
from plexbud.config import Config
from plexbud.domain_types import MediaType, SortField
from plexbud.models import StatsRow

stats_app = typer.Typer(help="Show media library stats and space usage.")


SortOption = Annotated[
    str,
    typer.Option("--sort", "-s", help="Sort by: size, lastwatched, watched30d"),
]
LimitOption = Annotated[
    int | None,
    typer.Option("--limit", "-n", help="Limit number of results"),
]
MinSizeOption = Annotated[
    str | None,
    typer.Option("--min-size", help="Minimum size filter (e.g. 20GiB)"),
]
HideAddedOption = Annotated[
    str | None,
    typer.Option("--hide-added", help="Hide items added within N days (e.g. 30d)"),
]
HideWatchedOption = Annotated[
    str | None,
    typer.Option("--hide-watched", help="Hide items watched within N days (e.g. 30d)"),
]
UnwatchedOption = Annotated[
    str | None,
    typer.Option("--unwatched", help="Only show items not watched in N+ days (e.g. 90d)"),
]
PlainOption = Annotated[
    bool,
    typer.Option("--plain", help="TSV output for piping"),
]


def run_stats(
    media: MediaType,
    *,
    sort: str = "size",
    limit: int | None = None,
    min_size: str | None = None,
    hide_added: str | None = None,
    hide_watched: str | None = None,
    unwatched: str | None = None,
    plain: bool = False,
    title: str | None = None,
    clients: Clients | None = None,
    config: Config | None = None,
) -> None:
    """Fetch, filter, and render stats for a media type."""
    active_clients = clients
    active_config = config
    if active_clients is None or active_config is None:
        active_clients, active_config = get_clients_and_config()

    rows = get_stats_rows_for_media(active_clients, active_config, media)
    rows = _apply_filters(
        rows,
        sort=sort,
        limit=limit,
        min_size=min_size,
        hide_added=hide_added,
        hide_watched=hide_watched,
        unwatched=unwatched,
    )
    _render(rows, plain=plain, title=title)


@stats_app.command("tv")
def stats_tv(
    sort: SortOption = "size",
    limit: LimitOption = None,
    min_size: MinSizeOption = None,
    hide_added: HideAddedOption = None,
    hide_watched: HideWatchedOption = None,
    unwatched: UnwatchedOption = None,
    plain: PlainOption = False,
) -> None:
    """Show TV series stats sorted by size, watch activity, etc."""
    run_stats(
        "tv",
        sort=sort,
        limit=limit,
        min_size=min_size,
        hide_added=hide_added,
        hide_watched=hide_watched,
        unwatched=unwatched,
        plain=plain,
    )


@stats_app.command("movies")
def stats_movies(
    sort: SortOption = "size",
    limit: LimitOption = None,
    min_size: MinSizeOption = None,
    hide_added: HideAddedOption = None,
    hide_watched: HideWatchedOption = None,
    unwatched: UnwatchedOption = None,
    plain: PlainOption = False,
) -> None:
    """Show movie stats sorted by size, watch activity, etc."""
    run_stats(
        "movie",
        sort=sort,
        limit=limit,
        min_size=min_size,
        hide_added=hide_added,
        hide_watched=hide_watched,
        unwatched=unwatched,
        plain=plain,
    )


def _apply_filters(
    rows: list[StatsRow],
    *,
    sort: str,
    limit: int | None,
    min_size: str | None,
    hide_added: str | None,
    hide_watched: str | None,
    unwatched: str | None,
) -> list[StatsRow]:
    """Apply CLI filters to stats rows."""
    now = datetime.now().astimezone()

    if min_size:
        min_bytes = _parse_size(min_size)
        rows = [r for r in rows if r.size_bytes >= min_bytes]

    if hide_added:
        cutoff = now - timedelta(days=_parse_duration(hide_added))
        rows = [r for r in rows if r.added.astimezone() < cutoff]

    watched_filter = hide_watched or unwatched
    if watched_filter:
        cutoff = now - timedelta(days=_parse_duration(watched_filter))
        rows = [r for r in rows if r.last_watched is None or r.last_watched.astimezone() < cutoff]

    parsed_sort = _parse_sort(sort)
    if parsed_sort == "size":
        rows.sort(key=lambda r: r.size_bytes, reverse=True)
    elif parsed_sort == "lastwatched":
        rows.sort(key=lambda r: r.last_watched or datetime.min.replace(tzinfo=UTC), reverse=False)
    else:
        rows.sort(key=lambda r: r.watch_count_30d, reverse=True)

    if limit:
        rows = rows[:limit]

    return rows


def _render(rows: list[StatsRow], *, plain: bool, title: str | None = None) -> None:
    """Render stats rows."""
    if plain:
        from plexbud.output import render_stats_plain

        print(render_stats_plain(rows))
    else:
        from plexbud.output import render_stats_table

        render_stats_table(rows, console=Console(), title=title)


def _parse_sort(sort: str) -> SortField:
    valid_sorts: set[SortField] = {"size", "lastwatched", "watched30d"}
    normalized = sort.strip().lower()
    if normalized in valid_sorts:
        return cast(SortField, normalized)
    raise typer.BadParameter(f"Invalid sort: {sort!r} (expected: size, lastwatched, watched30d)")


def _parse_duration(s: str) -> int:
    """Parse duration string like '30d' to number of days."""
    match = re.match(r"^(\d+)d$", s.strip())
    if not match:
        raise typer.BadParameter(f"Invalid duration: {s!r} (expected format: 30d)")
    return int(match.group(1))


def _parse_size(s: str) -> int:
    """Parse size string like '20GiB' to bytes."""
    match = re.match(r"^(\d+(?:\.\d+)?)\s*(B|KiB|MiB|GiB|TiB)$", s.strip(), re.IGNORECASE)
    if not match:
        raise typer.BadParameter(f"Invalid size: {s!r} (expected format: 20GiB)")
    value = float(match.group(1))
    unit = match.group(2).lower()
    multipliers = {"b": 1, "kib": 1024, "mib": 1024**2, "gib": 1024**3, "tib": 1024**4}
    return int(value * multipliers[unit])
