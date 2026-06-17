"""Internal pipeline types for ingestion (kept separate from API/DB models)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class Platform(str, Enum):
    ANDROID = "android"
    IOS = "ios"


@dataclass(frozen=True)
class AppRef:
    """What the user asked us to analyse. One of store_app_id/name/store_url identifies it."""

    platform: Platform
    store_app_id: Optional[str] = None  # Play package name or App Store numeric id
    name: Optional[str] = None
    store_url: Optional[str] = None
    country: str = "us"
    lang: str = "en"


@dataclass
class RawReview:
    """A review exactly as a store scraper returned it, before any cleaning."""

    source_review_id: str
    platform: Platform
    text: Optional[str]
    title: Optional[str]
    rating: Optional[int]
    review_date: Optional[datetime]


@dataclass
class CleanedReview:
    """Deterministic output of the Data Cleaner. Same RawReview + same `now` => same value."""

    source_review_id: str
    platform: Platform
    text_raw: Optional[str]
    text_clean: str
    title_clean: Optional[str]
    rating: Optional[int]
    review_date: Optional[datetime]  # UTC tz-aware; None if missing or invalid
    is_spam: bool
    is_duplicate: bool
    is_analysable: bool
    invalid_date: bool = False
