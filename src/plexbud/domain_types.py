"""Shared domain-level type aliases."""

from __future__ import annotations

from typing import Literal

type MediaType = Literal["tv", "movie"]
type SortField = Literal["size", "lastwatched", "watched30d"]
