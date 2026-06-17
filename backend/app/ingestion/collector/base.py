"""Review Collector interface + shared retry/backoff (PRD §3, Phase 1).

The Collector is a deterministic-ish tool boundary: it resolves an app and pulls
raw reviews. Store calls are wrapped in with_retries so transient failures back
off and a persistent failure surfaces as ScraperUnavailable (EC-P1-08) rather
than crashing the request.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Protocol, TypeVar

from app.ingestion.schemas import AppRef, Platform, RawReview


class ScraperError(Exception):
    pass


class AppNotFound(ScraperError):
    """The app could not be resolved; never substitute a similar app (EC-P1-01)."""


class AmbiguousApp(ScraperError):
    """Multiple apps match a name; caller should disambiguate (EC-P1-02)."""

    def __init__(self, candidates: list[dict]) -> None:
        self.candidates = candidates
        super().__init__("Multiple apps match; specify the store id or URL.")


class ScraperUnavailable(ScraperError):
    """Store unreachable / markup changed after retries (EC-P1-08)."""


@dataclass
class ResolvedApp:
    platform: Platform
    store_app_id: str
    name: str
    store_url: str | None = None


@dataclass
class CollectorResult:
    app: ResolvedApp
    reviews: list[RawReview]
    requested: int
    truncated_by_error: bool = False  # partial scrape from a mid-run failure (EC-P1-07)


class Collector(Protocol):
    platform: Platform

    def resolve(self, ref: AppRef) -> ResolvedApp: ...

    def collect(self, ref: AppRef, limit: int) -> CollectorResult: ...


T = TypeVar("T")


def with_retries(fn: Callable[[], T], attempts: int = 3, base_delay: float = 1.0) -> T:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - any store failure is retryable
            last = exc
            if i < attempts - 1:
                time.sleep(base_delay * (2**i))
    raise ScraperUnavailable(str(last))
