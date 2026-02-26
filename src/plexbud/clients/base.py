"""Shared HTTP client logic."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx


class APIError(Exception):
    """Raised when an API call fails."""

    def __init__(self, service: str, status_code: int, detail: str = "") -> None:
        self.service = service
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{service} API error {status_code}: {detail}")


def parse_datetime(s: str) -> datetime:
    """Parse ISO 8601 datetime strings from Sonarr/Radarr APIs."""
    if not s:
        return datetime(1970, 1, 1, tzinfo=UTC)
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=UTC)


class BaseClient:
    """Base class for thin API wrappers."""

    service_name: str = "unknown"

    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base_url, timeout=timeout)

    def _get(
        self,
        path: str,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
    ) -> object:
        resp = self._client.get(path, params=params, headers=headers)
        if resp.status_code != 200:
            raise APIError(self.service_name, resp.status_code, resp.text[:200])
        return resp.json()

    def _post(
        self,
        path: str,
        *,
        data: dict[str, object] | None = None,
        json: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        resp = self._client.post(path, data=data, json=json, headers=headers)
        if resp.status_code >= 400:
            raise APIError(self.service_name, resp.status_code, resp.text[:200])
        return resp

    def _delete(
        self,
        path: str,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        resp = self._client.delete(path, params=params, headers=headers)
        if resp.status_code >= 400:
            raise APIError(self.service_name, resp.status_code, resp.text[:200])
        return resp

    def close(self) -> None:
        self._client.close()


class ArrClient(BaseClient):
    """Base for Sonarr/Radarr clients that share API key auth and delete patterns."""

    def __init__(self, base_url: str, api_key: str) -> None:
        super().__init__(base_url)
        self._api_key = api_key

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-Api-Key": self._api_key}

    def _arr_delete(self, path: str) -> None:
        """Delete an item from Sonarr/Radarr with standard params."""
        params: dict[str, str | int] = {
            "deleteFiles": "true",
            "addImportListExclusion": "true",
        }
        resp = self._delete(path, params=params, headers=self._headers)
        if resp.status_code not in (200, 202):
            raise APIError(self.service_name, resp.status_code, resp.text[:200])
