"""Shared test fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import respx
from httpx import Request, Response

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(service: str, name: str) -> Any:
    """Load a JSON fixture file."""
    path = FIXTURES_DIR / service / f"{name}.json"
    return json.loads(path.read_text())


def _json_resp(data: Any) -> Response:
    return Response(200, json={"response": {"data": data}})


@pytest.fixture
def sonarr_mock() -> respx.MockRouter:
    data = load_fixture("sonarr", "series")
    with respx.mock(base_url="http://sonarr:8989") as mock:
        mock.get("/api/v3/series").mock(
            return_value=Response(200, json=data),
        )
        yield mock


@pytest.fixture
def radarr_mock() -> respx.MockRouter:
    data = load_fixture("radarr", "movies")
    with respx.mock(base_url="http://radarr:7878") as mock:
        mock.get("/api/v3/movie").mock(
            return_value=Response(200, json=data),
        )
        yield mock


@pytest.fixture
def tautulli_mock() -> respx.MockRouter:
    lib1 = load_fixture("tautulli", "library_1")
    lib2 = load_fixture("tautulli", "library_2")

    def route_tautulli(request: Request) -> Response:
        params = dict(request.url.params)
        cmd = params.get("cmd", "")
        if cmd == "get_library_media_info":
            data = lib1 if params.get("section_id") == "1" else lib2
            return _json_resp(data)
        if cmd == "get_item_watch_time_stats":
            return _json_resp(
                [
                    {"query_days": 30, "total_plays": 2},
                    {"query_days": 0, "total_plays": 10},
                ]
            )
        if cmd == "get_history":
            return _json_resp({"data": [{"stopped": 1740268800}]})
        if cmd == "get_activity":
            return _json_resp({"sessions": []})
        return _json_resp({})

    with respx.mock(base_url="http://tautulli:8181") as mock:
        mock.get("/api/v2").mock(side_effect=route_tautulli)
        yield mock


@pytest.fixture
def qbt_mock() -> respx.MockRouter:
    torrents = load_fixture("qbittorrent", "torrents")
    with respx.mock(base_url="http://qbt:8080", assert_all_called=False) as mock:
        mock.post("/api/v2/auth/login").mock(
            return_value=Response(200, text="Ok."),
        )
        mock.get("/api/v2/torrents/info").mock(
            return_value=Response(200, json=torrents),
        )
        mock.get("/api/v2/torrents/files").mock(
            return_value=Response(200, json=[]),
        )
        mock.post("/api/v2/torrents/delete").mock(
            return_value=Response(200),
        )
        yield mock
