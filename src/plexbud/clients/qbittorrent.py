"""qBittorrent API client."""

from __future__ import annotations

from plexbud.clients.base import APIError, BaseClient
from plexbud.models import TorrentInfo


class QBittorrentClient(BaseClient):
    service_name = "qBittorrent"

    def __init__(self, base_url: str, username: str, password: str) -> None:
        super().__init__(base_url)
        self._username = username
        self._password = password
        self._logged_in = False

    def _login(self) -> None:
        if self._logged_in:
            return
        resp = self._post(
            "/api/v2/auth/login",
            data={"username": self._username, "password": self._password},
        )
        if resp.status_code != 200 or resp.text.strip() != "Ok.":
            raise APIError(self.service_name, resp.status_code, "Login failed")
        self._logged_in = True

    def get_torrents(self) -> list[TorrentInfo]:
        """Fetch all torrents."""
        self._login()
        data = self._get("/api/v2/torrents/info")
        if not isinstance(data, list):
            return []

        torrents: list[TorrentInfo] = []
        for t in data:
            torrents.append(
                TorrentInfo(
                    hash=t.get("hash", ""),
                    name=t.get("name", ""),
                    save_path=t.get("save_path", t.get("savePath", "")),
                    size=t.get("size", 0),
                )
            )
        return torrents

    def get_torrent_files(self, torrent_hash: str) -> list[str]:
        """Get file paths for a specific torrent."""
        self._login()
        data = self._get("/api/v2/torrents/files", params={"hash": torrent_hash})
        if not isinstance(data, list):
            return []
        return [f.get("name", "") for f in data if f.get("name")]

    def delete_torrents(self, hashes: list[str], *, delete_files: bool = True) -> None:
        """Delete torrents by hash."""
        self._login()
        self._post(
            "/api/v2/torrents/delete",
            data={
                "hashes": "|".join(hashes),
                "deleteFiles": str(delete_files).lower(),
            },
        )
