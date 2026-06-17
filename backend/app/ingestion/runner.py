"""Ingestion runner — orchestrates collect -> clean -> persist (Phase 1).

Collector and repository are injected, so the flow is testable end-to-end with a
fake collector and the in-memory repository (no network, no DB). The store call
runs in a worker thread since the scraper libraries are synchronous.

Status values map directly to edge cases:
  ok | partial(EC-P1-07) | no_reviews(EC-P1-04) |
  not_found(EC-P1-01) | ambiguous(EC-P1-02) | unavailable(EC-P1-08)
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.ingestion.cleaner import clean_batch
from app.ingestion.collector.base import (
    AmbiguousApp,
    AppNotFound,
    Collector,
    ScraperUnavailable,
)
from app.ingestion.repository import ReviewRepository
from app.ingestion.schemas import AppRef


@dataclass
class IngestResult:
    status: str
    app_id: str | None = None
    collected: int = 0
    analysable: int = 0
    spam: int = 0
    duplicates: int = 0
    requested: int = 0
    detail: str = ""
    candidates: list = field(default_factory=list)


async def run_ingestion(
    ref: AppRef,
    limit: int,
    collector: Collector,
    repository: ReviewRepository,
    now: datetime | None = None,
) -> IngestResult:
    now = now or datetime.now(timezone.utc)

    try:
        result = await asyncio.to_thread(collector.collect, ref, limit)
    except AppNotFound as exc:
        return IngestResult("not_found", detail=str(exc))
    except AmbiguousApp as exc:
        return IngestResult("ambiguous", detail=str(exc), candidates=exc.candidates)
    except ScraperUnavailable as exc:
        return IngestResult("unavailable", detail=str(exc))

    if not result.reviews and not result.truncated_by_error:
        app_id = await repository.upsert_app(result.app, now)
        return IngestResult(
            "no_reviews", app_id=app_id, requested=limit, detail="App resolved but has no reviews"
        )

    cleaned = clean_batch(result.reviews, now)
    app_id = await repository.upsert_app(result.app, now)
    counts = await repository.upsert_reviews(app_id, cleaned)
    return IngestResult(
        status="partial" if result.truncated_by_error else "ok",
        app_id=app_id,
        collected=len(cleaned),
        analysable=sum(c.is_analysable for c in cleaned),
        spam=sum(c.is_spam for c in cleaned),
        duplicates=sum(c.is_duplicate for c in cleaned),
        requested=limit,
        detail=f"{counts.get('inserted', 0)} inserted, {counts.get('updated', 0)} updated",
    )
