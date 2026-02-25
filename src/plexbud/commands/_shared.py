"""Shared CLI utilities."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import typer

from plexbud.clients.qbittorrent import QBittorrentClient
from plexbud.clients.radarr import RadarrClient
from plexbud.clients.sonarr import SonarrClient
from plexbud.clients.tautulli import TautulliClient
from plexbud.config import Config, ConfigError, load_config
from plexbud.domain_types import MediaType
from plexbud.interfaces import QBittorrentAPI, RadarrAPI, SonarrAPI, TautulliAPI
from plexbud.models import MediaItem, StatsRow


@dataclass(frozen=True)
class Clients:
    sonarr: SonarrAPI
    radarr: RadarrAPI
    tautulli: TautulliAPI
    qbittorrent: QBittorrentAPI


def get_clients_and_config() -> tuple[Clients, Config]:
    """Load config and create appropriate clients (real or mock)."""
    if os.environ.get("PLEXBUD_MOCK") == "1":
        return _create_mock_clients()

    try:
        config = load_config()
    except ConfigError as e:
        typer.echo(f"Config error: {e}", err=True)
        sys.exit(1)

    clients = Clients(
        sonarr=SonarrClient(config.sonarr.url, config.sonarr.api_key),
        radarr=RadarrClient(config.radarr.url, config.radarr.api_key),
        tautulli=TautulliClient(config.tautulli.url, config.tautulli.api_key),
        qbittorrent=QBittorrentClient(
            config.qbittorrent.url,
            config.qbittorrent.username,
            config.qbittorrent.password,
        ),
    )
    return clients, config


def _create_mock_clients() -> tuple[Clients, Config]:
    """Create mock clients that read from fixture files."""
    from plexbud.mock import MockClients, mock_config

    config = mock_config()
    mock = MockClients()
    clients = Clients(
        sonarr=mock.sonarr,
        radarr=mock.radarr,
        tautulli=mock.tautulli,
        qbittorrent=mock.qbittorrent,
    )
    return clients, config


def get_media_items(clients: Clients, media: MediaType) -> list[MediaItem]:
    """Fetch media catalog items for one media type."""
    if media == "tv":
        return clients.sonarr.get_all_series()
    return clients.radarr.get_all_movies()


def get_library_lookup(clients: Clients, config: Config, media: MediaType) -> dict[int, int]:
    """Fetch Tautulli rating key lookup for one media type."""
    section_id = (
        config.tautulli.tv_section_id if media == "tv" else config.tautulli.movie_section_id
    )
    return clients.tautulli.get_library_media_info(section_id)


def get_stats_rows_for_media(clients: Clients, config: Config, media: MediaType) -> list[StatsRow]:
    """Build stats rows for one media type."""
    from plexbud.services.stats import build_stats_rows

    items = get_media_items(clients, media)
    id_lookup = get_library_lookup(clients, config, media)
    return build_stats_rows(items, id_lookup, clients.tautulli, config)


def get_disk_path_for_media(config: Config, media: MediaType) -> str:
    """Return the configured media path for one media type."""
    return config.paths.media_tv if media == "tv" else config.paths.media_movies


def media_label(media: MediaType) -> str:
    """Friendly singular label for output messages."""
    return "TV series" if media == "tv" else "movie"
