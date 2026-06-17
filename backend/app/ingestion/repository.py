"""Persistence for ingested reviews.

Idempotent upsert keyed on (app_id, platform, source_review_id) so re-ingestion
never creates duplicate rows (EC-X-23). Two implementations:
  - InMemoryReviewRepository: for tests / local dry-runs.
  - PostgresReviewRepository: Supabase/Postgres (untested without DB creds).
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.ingestion.collector.base import ResolvedApp
from app.ingestion.schemas import CleanedReview


class ReviewRepository(Protocol):
    async def upsert_app(self, app: ResolvedApp, now: datetime) -> str: ...

    async def upsert_reviews(self, app_id: str, reviews: list[CleanedReview]) -> dict: ...


class InMemoryReviewRepository:
    def __init__(self) -> None:
        self.apps: dict[str, dict] = {}
        self.reviews: dict[tuple[str, str, str], CleanedReview] = {}

    async def upsert_app(self, app: ResolvedApp, now: datetime) -> str:
        app_id = f"{app.platform.value}:{app.store_app_id}"
        existing = self.apps.get(app_id)
        self.apps[app_id] = {
            "name": app.name,
            "store_url": app.store_url,
            "platform": app.platform.value,
            "first_ingested_at": existing["first_ingested_at"] if existing else now,
            "last_refreshed_at": now,
        }
        return app_id

    async def upsert_reviews(self, app_id: str, reviews: list[CleanedReview]) -> dict:
        inserted = updated = 0
        for c in reviews:
            key = (app_id, c.platform.value, c.source_review_id)
            if key in self.reviews:
                updated += 1
            else:
                inserted += 1
            self.reviews[key] = c
        return {"inserted": inserted, "updated": updated, "total": len(self.reviews)}


class PostgresReviewRepository:
    def __init__(self, settings) -> None:
        self._settings = settings

    async def upsert_app(self, app: ResolvedApp, now: datetime) -> str:
        from sqlalchemy import text

        from app.db.session import get_engine

        engine = get_engine(self._settings)
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        insert into apps (name, store_app_id, store_url, platform,
                                          first_ingested_at, last_refreshed_at)
                        values (:name, :store_app_id, :store_url, :platform, :now, :now)
                        on conflict (platform, store_app_id) do update
                          set name = excluded.name,
                              store_url = excluded.store_url,
                              last_refreshed_at = :now
                        returning id
                        """
                    ),
                    {
                        "name": app.name,
                        "store_app_id": app.store_app_id,
                        "store_url": app.store_url,
                        "platform": app.platform.value,
                        "now": now,
                    },
                )
            ).first()
        return str(row[0])

    async def upsert_reviews(self, app_id: str, reviews: list[CleanedReview]) -> dict:
        from sqlalchemy import text

        from app.db.session import get_engine

        engine = get_engine(self._settings)
        sql = text(
            """
            insert into reviews (app_id, platform, source_review_id, title, text_raw, text_clean,
                                 rating, review_date, is_spam, is_duplicate, is_analysable)
            values (:app_id, :platform, :source_review_id, :title, :text_raw, :text_clean,
                    :rating, :review_date, :is_spam, :is_duplicate, :is_analysable)
            on conflict (app_id, platform, source_review_id) do update
              set title = excluded.title, text_raw = excluded.text_raw,
                  text_clean = excluded.text_clean, rating = excluded.rating,
                  review_date = excluded.review_date, is_spam = excluded.is_spam,
                  is_duplicate = excluded.is_duplicate, is_analysable = excluded.is_analysable
            returning (xmax = 0) as inserted
            """
        )
        inserted = updated = 0
        async with engine.begin() as conn:
            for c in reviews:
                res = (
                    await conn.execute(
                        sql,
                        {
                            "app_id": app_id,
                            "platform": c.platform.value,
                            "source_review_id": c.source_review_id,
                            "title": c.title_clean,
                            "text_raw": c.text_raw,
                            "text_clean": c.text_clean,
                            "rating": c.rating,
                            "review_date": c.review_date,
                            "is_spam": c.is_spam,
                            "is_duplicate": c.is_duplicate,
                            "is_analysable": c.is_analysable,
                        },
                    )
                ).first()
                if res and res[0]:
                    inserted += 1
                else:
                    updated += 1
        return {"inserted": inserted, "updated": updated, "total": inserted + updated}
