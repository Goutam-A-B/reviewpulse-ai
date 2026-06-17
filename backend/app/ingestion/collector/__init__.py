"""Review Collector — store scraper adapters behind one interface."""
from __future__ import annotations

from app.ingestion.collector.app_store import AppStoreCollector
from app.ingestion.collector.base import (
    AmbiguousApp,
    AppNotFound,
    Collector,
    CollectorResult,
    ResolvedApp,
    ScraperError,
    ScraperUnavailable,
)
from app.ingestion.collector.play_store import PlayStoreCollector
from app.ingestion.schemas import Platform

__all__ = [
    "AmbiguousApp",
    "AppNotFound",
    "AppStoreCollector",
    "Collector",
    "CollectorResult",
    "PlayStoreCollector",
    "ResolvedApp",
    "ScraperError",
    "ScraperUnavailable",
    "get_collector",
]


def get_collector(platform: Platform) -> Collector:
    if platform == Platform.ANDROID:
        return PlayStoreCollector()
    if platform == Platform.IOS:
        return AppStoreCollector()
    raise ValueError(f"Unknown platform: {platform}")
