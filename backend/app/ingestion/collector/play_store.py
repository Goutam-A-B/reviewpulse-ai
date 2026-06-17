"""Google Play collector (google-play-scraper). Imported lazily.

Bounds the cold scrape to `limit` most-recent reviews (EC-P1-07); the long tail
is backfilled later. Developer replies (replyContent) are intentionally not
ingested — only the customer's own review (EC-P1-12).
"""
from __future__ import annotations

from app.ingestion.collector.base import (
    AppNotFound,
    CollectorResult,
    ResolvedApp,
    ScraperUnavailable,
    with_retries,
)
from app.ingestion.schemas import AppRef, Platform, RawReview


class PlayStoreCollector:
    platform = Platform.ANDROID

    def resolve(self, ref: AppRef) -> ResolvedApp:
        from google_play_scraper import app as gp_app
        from google_play_scraper import search as gp_search

        if ref.store_app_id:
            try:
                info = with_retries(
                    lambda: gp_app(ref.store_app_id, lang=ref.lang, country=ref.country)
                )
            except ScraperUnavailable as exc:
                raise AppNotFound(f"Play app '{ref.store_app_id}' not found") from exc
            return ResolvedApp(
                self.platform, ref.store_app_id, info.get("title") or ref.store_app_id, info.get("url")
            )

        if ref.name:
            results = with_retries(
                lambda: gp_search(ref.name, lang=ref.lang, country=ref.country, n_hits=5)
            )
            if not results:
                raise AppNotFound(f"No Play Store app matches '{ref.name}'")
            top = results[0]
            return ResolvedApp(self.platform, top["appId"], top.get("title") or ref.name, top.get("url"))

        raise AppNotFound("Provide a Play package id, app name, or store URL.")

    def collect(self, ref: AppRef, limit: int) -> CollectorResult:
        from google_play_scraper import Sort
        from google_play_scraper import reviews as gp_reviews

        resolved = self.resolve(ref)
        raw, _token = with_retries(
            lambda: gp_reviews(
                resolved.store_app_id,
                lang=ref.lang,
                country=ref.country,
                sort=Sort.NEWEST,
                count=limit,
            )
        )
        rows = [
            RawReview(
                source_review_id=str(r.get("reviewId")),
                platform=self.platform,
                text=r.get("content"),
                title=None,
                rating=r.get("score"),
                review_date=r.get("at"),
            )
            for r in raw
        ]
        return CollectorResult(resolved, rows, requested=limit)
