"""Data source for the Stats Engine — fetches the in-scope review records.

Aggregation lives in the engine (one place, testable); the source only fetches
rows joined across reviews + sentiment + themes, scoped by app_id and an optional
UTC date window. In-memory (tests) and Postgres (Supabase) implementations.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass
class ReviewRecord:
    review_date: datetime | None
    rating: int | None
    sentiment: str | None  # 'positive' | 'neutral' | 'negative' | None
    theme_id: str | None
    theme_label: str | None


class StatsSource(Protocol):
    async def records(
        self, app_id: str, start: datetime | None = None, end: datetime | None = None
    ) -> list[ReviewRecord]: ...


class InMemoryStatsSource:
    def __init__(self, records_by_app: dict[str, list[ReviewRecord]] | None = None) -> None:
        self._data = records_by_app or {}

    async def records(self, app_id, start=None, end=None) -> list[ReviewRecord]:
        out: list[ReviewRecord] = []
        for r in self._data.get(app_id, []):
            if (start or end) and r.review_date is None:
                continue  # undated reviews can't be placed in a window (EC-P1-15)
            if start and r.review_date < start:
                continue
            if end and r.review_date > end:
                continue
            out.append(r)
        return out


class PostgresStatsSource:
    def __init__(self, settings) -> None:
        self._settings = settings

    async def records(self, app_id, start=None, end=None) -> list[ReviewRecord]:
        from sqlalchemy import text

        from app.db.session import get_engine

        engine = get_engine(self._settings)
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        """
                        select r.review_date, r.rating, s.label, rt.theme_id, t.label
                        from reviews r
                        left join sentiment s on s.review_id = r.id
                        left join review_themes rt on rt.review_id = r.id
                        left join themes t on t.id = rt.theme_id
                        where r.app_id = :app_id
                          and r.is_analysable and not r.is_duplicate and not r.is_spam
                          and (cast(:start as timestamptz) is null or r.review_date >= cast(:start as timestamptz))
                          and (cast(:end as timestamptz) is null or r.review_date <= cast(:end as timestamptz))
                        """
                    ),
                    {"app_id": app_id, "start": start, "end": end},
                )
            ).all()
        return [
            ReviewRecord(
                review_date=row[0],
                rating=row[1],
                sentiment=row[2],
                theme_id=str(row[3]) if row[3] is not None else None,
                theme_label=row[4],
            )
            for row in rows
        ]
