"""Ingestion runner tests — idempotency (EC-X-23) and honest states, using a fake
collector and the in-memory repository (no network, no DB)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.ingestion.collector.base import (
    AppNotFound,
    CollectorResult,
    ResolvedApp,
    ScraperUnavailable,
)
from app.ingestion.repository import InMemoryReviewRepository
from app.ingestion.runner import run_ingestion
from app.ingestion.schemas import AppRef, Platform, RawReview

NOW = datetime(2026, 6, 16, tzinfo=timezone.utc)
REF = AppRef(platform=Platform.ANDROID, store_app_id="com.example.app")
APP = ResolvedApp(Platform.ANDROID, "com.example.app", "Example", "http://x")


def _raw(rid, text="good app"):
    return RawReview(rid, Platform.ANDROID, text, None, 5, NOW)


class FakeCollector:
    platform = Platform.ANDROID

    def __init__(self, result=None, exc=None):
        self._result = result
        self._exc = exc

    def resolve(self, ref):
        return APP

    def collect(self, ref, limit):
        if self._exc:
            raise self._exc
        return self._result


async def test_ingestion_ok_and_counts():
    raws = [
        RawReview("a", Platform.ANDROID, "good app", None, 5, NOW),
        RawReview("b", Platform.ANDROID, "different text", None, 4, NOW),
        RawReview("c", Platform.ANDROID, "", None, 3, NOW),  # star-only
    ]
    repo = InMemoryReviewRepository()
    res = await run_ingestion(REF, 10, FakeCollector(CollectorResult(APP, raws, 10)), repo, now=NOW)
    assert res.status == "ok"
    assert res.collected == 3
    assert res.analysable == 2
    assert len(repo.reviews) == 3


async def test_reingest_is_idempotent():
    raws = [_raw("a"), _raw("b", "different")]
    repo = InMemoryReviewRepository()
    collector = FakeCollector(CollectorResult(APP, raws, 10))
    await run_ingestion(REF, 10, collector, repo, now=NOW)
    second = await run_ingestion(REF, 10, collector, repo, now=NOW)
    assert len(repo.reviews) == 2  # no duplicate rows on re-ingest (EC-X-23)
    assert "2 updated" in second.detail


async def test_no_reviews_state():
    res = await run_ingestion(
        REF, 10, FakeCollector(CollectorResult(APP, [], 10)), InMemoryReviewRepository(), now=NOW
    )
    assert res.status == "no_reviews"


async def test_not_found_state():
    res = await run_ingestion(
        REF, 10, FakeCollector(exc=AppNotFound("nope")), InMemoryReviewRepository(), now=NOW
    )
    assert res.status == "not_found"


async def test_unavailable_state():
    res = await run_ingestion(
        REF, 10, FakeCollector(exc=ScraperUnavailable("store down")), InMemoryReviewRepository(), now=NOW
    )
    assert res.status == "unavailable"


async def test_partial_state():
    result = CollectorResult(APP, [_raw("a")], 10, truncated_by_error=True)
    res = await run_ingestion(REF, 10, FakeCollector(result), InMemoryReviewRepository(), now=NOW)
    assert res.status == "partial"
