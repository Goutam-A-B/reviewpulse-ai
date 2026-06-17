"""Apple App Store collector (app-store-scraper). Imported lazily.

App Store reviews from this library lack a stable id, so we synthesise a
deterministic source_review_id by hashing the review's stable fields — this
keeps ingestion idempotent (EC-X-23). Resolution may require an explicit app
name (URL slug) or numeric id; name-only resolution is best-effort.
"""
from __future__ import annotations

import hashlib

from app.ingestion.collector.base import (
    AppNotFound,
    CollectorResult,
    ResolvedApp,
    with_retries,
)
from app.ingestion.schemas import AppRef, Platform, RawReview


class AppStoreCollector:
    platform = Platform.IOS

    def resolve(self, ref: AppRef) -> ResolvedApp:
        if not ref.name and not ref.store_app_id:
            raise AppNotFound("Provide an App Store app name (slug) or numeric id.")
        store_app_id = str(ref.store_app_id or ref.name)
        return ResolvedApp(self.platform, store_app_id, ref.name or store_app_id, ref.store_url)

    def collect(self, ref: AppRef, limit: int) -> CollectorResult:
        from app_store_scraper import AppStore

        resolved = self.resolve(ref)

        def _scrape() -> list[dict]:
            store = AppStore(country=ref.country, app_name=ref.name or "", app_id=ref.store_app_id)
            store.review(how_many=limit)
            return list(store.reviews)

        raw = with_retries(_scrape)
        rows: list[RawReview] = []
        for r in raw:
            seed = f"{r.get('userName', '')}|{r.get('date', '')}|{r.get('title', '')}|{(r.get('review') or '')[:64]}"
            sid = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
            rows.append(
                RawReview(
                    source_review_id=sid,
                    platform=self.platform,
                    text=r.get("review"),
                    title=r.get("title"),
                    rating=r.get("rating"),
                    review_date=r.get("date"),
                )
            )
        return CollectorResult(resolved, rows, requested=limit)
