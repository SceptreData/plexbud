"""Typer app entry point."""

from __future__ import annotations

import typer

from plexbud.commands.delete import delete_app
from plexbud.commands.stats import (
    HideAddedOption,
    HideWatchedOption,
    LimitOption,
    MinSizeOption,
    PlainOption,
    SortOption,
    UnwatchedOption,
    run_stats,
    stats_app,
)

app = typer.Typer(
    name="plexbud",
    help="CLI tool for Plex media library stats and cleanup.",
)

app.add_typer(stats_app, name="stats")
app.add_typer(delete_app, name="delete")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    sort: SortOption = "size",
    limit: LimitOption = None,
    min_size: MinSizeOption = None,
    hide_added: HideAddedOption = None,
    hide_watched: HideWatchedOption = None,
    unwatched: UnwatchedOption = None,
    plain: PlainOption = False,
) -> None:
    """CLI tool for Plex media library stats and cleanup."""
    if ctx.invoked_subcommand is not None:
        return

    from plexbud.commands._shared import get_clients_and_config
    from plexbud.services.disk import get_disk_usage

    clients, config = get_clients_and_config()

    disk_infos = get_disk_usage(config)
    if plain:
        from plexbud.output import render_disk_plain

        if disk_infos:
            print(render_disk_plain(disk_infos))
    else:
        from rich.console import Console

        from plexbud.output import render_disk_header

        render_disk_header(disk_infos, console=Console())

    run_stats(
        "tv",
        sort=sort,
        limit=limit,
        min_size=min_size,
        hide_added=hide_added,
        hide_watched=hide_watched,
        unwatched=unwatched,
        plain=plain,
        title="TV Shows",
        clients=clients,
        config=config,
    )
    run_stats(
        "movies",
        sort=sort,
        limit=limit,
        min_size=min_size,
        hide_added=hide_added,
        hide_watched=hide_watched,
        unwatched=unwatched,
        plain=plain,
        title="Movies",
        clients=clients,
        config=config,
    )


if __name__ == "__main__":
    app()
