"""Shared filter for scoping stored evidence (date / rating / theme / platform).

The same filter scopes both the Quote Retriever (applied inside Qdrant on indexed
payload fields, PRD §11.1) and the Stats Engine (applied in SQL). app_id is always
required so one app's data never leaks into another's report (EC-X-21).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ReviewFilter:
    app_id: str
    start: datetime | None = None
    end: datetime | None = None
    rating_min: int | None = None
    rating_max: int | None = None
    theme_id: str | None = None
    platform: str | None = None
