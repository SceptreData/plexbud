"""Output formatting - Rich tables and plain TSV."""

from __future__ import annotations

from datetime import datetime

from rich.console import Console
from rich.table import Table

from plexbud.models import DeletionPlan, DiskInfo, StatsRow


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    if i >= 2:
        return f"{size:.1f} {units[i]}"
    return f"{size:.0f} {units[i]}"


def format_date(dt: datetime | None) -> str:
    """Format a datetime for display."""
    if dt is None:
        return "Never"
    return dt.strftime("%Y-%m-%d")


def format_age(dt: datetime) -> str:
    """Format a datetime as relative age (e.g. '42d ago')."""
    now = datetime.now().astimezone()
    try:
        dt_aware = dt.astimezone()
    except (ValueError, OSError):
        dt_aware = dt
    delta = now - dt_aware
    days = delta.days
    if days < 0:
        return "future"
    if days == 0:
        return "today"
    if days < 365:
        return f"{days}d ago"
    years = days // 365
    return f"{years}y ago"


def render_stats_table(
    rows: list[StatsRow], *, console: Console | None = None, title: str | None = None
) -> None:
    """Render stats as a Rich table."""
    c = console or Console()
    table = Table(title=title or "Media Library Stats", show_lines=False)

    table.add_column("Title", style="bold", no_wrap=True, max_width=40)
    table.add_column("Size", justify="right", style="cyan")
    table.add_column("Last Watched", justify="right")
    table.add_column("30d", justify="right", header_style="yellow", style="yellow")
    table.add_column("All", justify="right", header_style="yellow", style="yellow")
    table.add_column("Added", justify="right", style="dim")
    table.add_column("Location", style="dim")
    table.add_column("Del. Impact", justify="right", style="green")

    for row in rows:
        impact = format_size(row.deletion_impact.freeable_bytes)
        if row.deletion_impact.has_shared_links:
            impact += " *"

        table.add_row(
            row.title,
            format_size(row.size_bytes),
            format_date(row.last_watched),
            str(row.watch_count_30d),
            str(row.watch_count_all),
            format_age(row.added),
            row.location.summary,
            impact,
        )

    c.print(table)
    if any(r.deletion_impact.has_shared_links for r in rows):
        c.print("[dim]* = hardlinks detected; actual freed space may differ[/dim]")


def render_stats_plain(rows: list[StatsRow]) -> str:
    """Render stats as TSV for piping."""
    header = ["Title", "Size", "Last Watched", "30d", "All", "Added", "Location", "Del. Impact"]
    lines = ["\t".join(header)]
    for row in rows:
        fields = [
            row.title,
            str(row.size_bytes),
            format_date(row.last_watched),
            str(row.watch_count_30d),
            str(row.watch_count_all),
            row.added.strftime("%Y-%m-%d"),
            row.location.summary,
            str(row.deletion_impact.freeable_bytes),
        ]
        lines.append("\t".join(fields))
    return "\n".join(lines)


def _print_paths(c: Console, label: str, paths: list[str], fallback: str) -> None:
    """Print a labeled list of paths, or a fallback if empty."""
    if not paths:
        c.print(f"  {label:<17}{fallback}")
        return
    for path in paths:
        c.print(f"  {label:<17}{path}")


def render_deletion_plan(plan: DeletionPlan, *, console: Console | None = None) -> None:
    """Render a deletion plan."""
    c = console or Console()

    label = "TV" if plan.media_type == "tv" else "Movie"
    c.print(f"\n[bold]DELETE: {plan.title} ({label})[/bold]")
    c.print("[dim]" + "=" * 60 + "[/dim]")
    c.print()

    if plan.media_dir:
        size_info = f"({format_size(plan.media_size_bytes)}, {plan.media_file_count} files)"
        c.print(f"  {'Media files:':<17}{plan.media_dir}  {size_info}")
    else:
        c.print(f"  {'Media files:':<17}(not found on disk)")

    _print_paths(c, "Torrent files:", plan.torrent_paths, "(none found)")
    _print_paths(c, "Usenet files:", plan.usenet_paths, "(none found)")

    c.print(f"  {'qBittorrent:':<17}{plan.torrent_count} torrent(s) will be removed")

    arr_name = "Sonarr:" if plan.media_type == "tv" else "Radarr:"
    c.print(f"  {arr_name:<17}Entry will be deleted + added to exclusion list")
    c.print()
    freed = format_size(plan.estimated_freed_bytes)
    c.print(f"  Estimated space freed: [bold green]{freed}[/bold green]")

    if plan.warnings:
        c.print()
        c.print("  [yellow]Warnings:[/yellow]")
        for w in plan.warnings:
            c.print(f"    [yellow]- {w}[/yellow]")

    c.print()


def _disk_color(percent: float) -> str:
    """Return Rich color based on usage thresholds."""
    if percent >= 80:
        return "red"
    if percent >= 60:
        return "yellow"
    return "green"


def _disk_bar(percent: float, width: int = 10) -> str:
    """Build a bar string like [########..]."""
    filled = round(width * percent / 100)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"


def render_disk_header(infos: list[DiskInfo], *, console: Console | None = None) -> None:
    """Render disk usage as a colored bar-chart header."""
    if not infos:
        return

    c = console or Console()
    c.print("[bold]Disk Usage[/bold]")

    for info in infos:
        pct = round(info.percent_used)
        color = _disk_color(info.percent_used)
        bar = _disk_bar(info.percent_used)
        free = format_size(info.free_bytes)
        total = format_size(info.total_bytes)
        c.print(
            f"  {info.path:<30} [{color}]{bar} {pct}%[/{color}] ({free} free of {total})",
            highlight=False,
        )

    c.print()


def render_disk_plain(infos: list[DiskInfo]) -> str:
    """Render disk usage as TSV."""
    header = ["Path", "Total", "Used", "Free", "Percent"]
    lines = ["\t".join(header)]
    for info in infos:
        fields = [
            info.path,
            str(info.total_bytes),
            str(info.used_bytes),
            str(info.free_bytes),
            f"{info.percent_used:.1f}",
        ]
        lines.append("\t".join(fields))
    return "\n".join(lines)
