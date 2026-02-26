"""TOML config loading and validation."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIG_PATH = Path.home() / ".config" / "plexbud" / "config.toml"


@dataclass(frozen=True)
class TautulliConfig:
    url: str
    api_key: str
    tv_section_id: int
    movie_section_id: int


@dataclass(frozen=True)
class ArrConfig:
    """Shared config for Sonarr and Radarr (both just url + api_key)."""

    url: str
    api_key: str


# Aliases for backward compat and clarity in type hints
SonarrConfig = ArrConfig
RadarrConfig = ArrConfig


@dataclass(frozen=True)
class QBittorrentConfig:
    url: str
    username: str
    password: str


@dataclass(frozen=True)
class PathsConfig:
    media_movies: str
    media_tv: str
    media_standup: str = ""
    torrents_root: str = ""
    usenet_complete: str = ""

    @property
    def media_roots(self) -> list[str]:
        return [p for p in [self.media_movies, self.media_tv, self.media_standup] if p]

    @property
    def download_roots(self) -> list[str]:
        return [p for p in [self.torrents_root, self.usenet_complete] if p]


@dataclass(frozen=True)
class PlexConfig:
    url: str = ""
    token: str = ""


@dataclass(frozen=True)
class Config:
    plex: PlexConfig = field(default_factory=PlexConfig)
    tautulli: TautulliConfig = field(default_factory=lambda: TautulliConfig("", "", 0, 0))
    sonarr: SonarrConfig = field(default_factory=lambda: SonarrConfig("", ""))
    radarr: RadarrConfig = field(default_factory=lambda: RadarrConfig("", ""))
    qbittorrent: QBittorrentConfig = field(default_factory=lambda: QBittorrentConfig("", "", ""))
    paths: PathsConfig = field(default_factory=lambda: PathsConfig("", ""))


class ConfigError(Exception):
    """Raised when config is missing or invalid."""


def _build_section[T](cls: type[T], data: dict[str, object], section_name: str) -> T:
    """Build a config dataclass from a TOML section dict, with helpful errors."""
    try:
        return cls(**data)
    except TypeError as e:
        raise ConfigError(f"[{section_name}] {e}") from None


def load_config(path: Path | None = None) -> Config:
    """Load and validate config from TOML file."""
    config_path = path or CONFIG_PATH

    if not config_path.exists():
        raise ConfigError(
            f"Config file not found: {config_path}\n"
            f"Create it with your service URLs and API keys.\n"
            f"See: plexbud --help"
        )

    text = config_path.read_text()
    raw: dict[str, Any] = tomllib.loads(text)

    plex = PlexConfig()
    tautulli = TautulliConfig("", "", 0, 0)
    sonarr = SonarrConfig("", "")
    radarr = RadarrConfig("", "")
    qbittorrent = QBittorrentConfig("", "", "")
    paths = PathsConfig("", "")

    if isinstance(raw.get("plex"), dict):
        plex = _build_section(PlexConfig, raw["plex"], "plex")
    if isinstance(raw.get("tautulli"), dict):
        tautulli = _build_section(TautulliConfig, raw["tautulli"], "tautulli")
    if isinstance(raw.get("sonarr"), dict):
        sonarr = _build_section(SonarrConfig, raw["sonarr"], "sonarr")
    if isinstance(raw.get("radarr"), dict):
        radarr = _build_section(RadarrConfig, raw["radarr"], "radarr")
    if isinstance(raw.get("qbittorrent"), dict):
        qbittorrent = _build_section(QBittorrentConfig, raw["qbittorrent"], "qbittorrent")
    if isinstance(raw.get("paths"), dict):
        paths = _build_section(PathsConfig, raw["paths"], "paths")

    config = Config(
        plex=plex,
        tautulli=tautulli,
        sonarr=sonarr,
        radarr=radarr,
        qbittorrent=qbittorrent,
        paths=paths,
    )
    _validate_config(config)
    return config


def _validate_config(config: Config) -> None:
    """Check that required config fields are non-empty."""
    missing: list[str] = []
    checks: list[tuple[str, str]] = [
        (config.tautulli.url, "tautulli.url"),
        (config.tautulli.api_key, "tautulli.api_key"),
        (config.sonarr.url, "sonarr.url"),
        (config.sonarr.api_key, "sonarr.api_key"),
        (config.radarr.url, "radarr.url"),
        (config.radarr.api_key, "radarr.api_key"),
        (config.qbittorrent.url, "qbittorrent.url"),
    ]
    for value, name in checks:
        if not value:
            missing.append(name)
    if missing:
        raise ConfigError(f"Missing required config fields: {', '.join(missing)}")
