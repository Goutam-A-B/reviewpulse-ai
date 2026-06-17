"""Persistence for enrichment outputs (sentiment, themes, review_themes, keywords).

Each enrichment run replaces the prior derived data for the app, so re-runs are
idempotent and reflect the current corpus. Two implementations: in-memory (tests)
and Postgres (Supabase, untested without creds).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass
class EnrichReview:
    review_id: str
    source_review_id: str
    platform: str
    text_clean: str
    rating: int | None
    review_date: datetime | None


class EnrichmentRepository(Protocol):
    async def load_enrichable_reviews(self, app_id: str) -> list[EnrichReview]: ...

    async def replace_sentiment(self, items: list[dict]) -> int: ...

    async def replace_themes(self, app_id: str, themes: list[dict], review_themes: list[dict]) -> int: ...

    async def replace_keywords(self, app_id: str, keywords: list[dict], now: datetime) -> int: ...


class InMemoryEnrichmentRepository:
    def __init__(self, reviews: list[EnrichReview] | None = None) -> None:
        self._reviews = reviews or []
        self.sentiment: dict[str, dict] = {}
        self.themes: dict[str, dict] = {}
        self.review_themes: list[dict] = []
        self.keywords: list[dict] = []

    async def load_enrichable_reviews(self, app_id: str) -> list[EnrichReview]:
        return list(self._reviews)

    async def replace_sentiment(self, items: list[dict]) -> int:
        for it in items:
            self.sentiment[it["review_id"]] = it
        return len(items)

    async def replace_themes(self, app_id: str, themes: list[dict], review_themes: list[dict]) -> int:
        self.themes = {t["theme_id"]: t for t in themes}
        self.review_themes = list(review_themes)
        return len(themes)

    async def replace_keywords(self, app_id: str, keywords: list[dict], now: datetime) -> int:
        self.keywords = list(keywords)
        return len(keywords)


class PostgresEnrichmentRepository:
    def __init__(self, settings) -> None:
        self._settings = settings

    async def load_enrichable_reviews(self, app_id: str) -> list[EnrichReview]:
        from sqlalchemy import text

        from app.db.session import get_engine

        engine = get_engine(self._settings)
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        """
                        select id, source_review_id, platform, text_clean, rating, review_date
                        from reviews
                        where app_id = :app_id
                          and is_analysable and not is_duplicate and not is_spam
                        order by source_review_id
                        """
                    ),
                    {"app_id": app_id},
                )
            ).all()
        return [
            EnrichReview(str(r[0]), r[1], r[2], r[3], r[4], r[5]) for r in rows
        ]

    async def replace_sentiment(self, items: list[dict]) -> int:
        from sqlalchemy import text

        from app.db.session import get_engine

        engine = get_engine(self._settings)
        sql = text(
            """
            insert into sentiment (review_id, label, model_version)
            values (:review_id, :label, :model_version)
            on conflict (review_id) do update
              set label = excluded.label, model_version = excluded.model_version
            """
        )
        async with engine.begin() as conn:
            for it in items:
                await conn.execute(sql, it)
        return len(items)

    async def replace_themes(self, app_id: str, themes: list[dict], review_themes: list[dict]) -> int:
        from sqlalchemy import text

        from app.db.session import get_engine

        engine = get_engine(self._settings)
        async with engine.begin() as conn:
            # Deleting themes cascades to review_themes (FK on delete cascade).
            await conn.execute(text("delete from themes where app_id = :app_id"), {"app_id": app_id})
            for t in themes:
                await conn.execute(
                    text(
                        """
                        insert into themes (id, app_id, label, size, model_version)
                        values (:theme_id, :app_id, :label, :size, :model_version)
                        """
                    ),
                    t,
                )
            for rt in review_themes:
                await conn.execute(
                    text(
                        """
                        insert into review_themes (review_id, theme_id, distance)
                        values (:review_id, :theme_id, :distance)
                        on conflict (review_id, theme_id) do update set distance = excluded.distance
                        """
                    ),
                    rt,
                )
        return len(themes)

    async def replace_keywords(self, app_id: str, keywords: list[dict], now: datetime) -> int:
        from sqlalchemy import text

        from app.db.session import get_engine

        engine = get_engine(self._settings)
        async with engine.begin() as conn:
            await conn.execute(text("delete from keywords where app_id = :app_id"), {"app_id": app_id})
            for k in keywords:
                await conn.execute(
                    text(
                        """
                        insert into keywords (app_id, term, frequency, window_end)
                        values (:app_id, :term, :frequency, :now)
                        """
                    ),
                    {"app_id": app_id, "term": k["term"], "frequency": k["frequency"], "now": now},
                )
        return len(keywords)
