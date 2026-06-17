"""Vector store (Qdrant Cloud free tier) + in-memory fake.

Write path (Phase 2): deterministic, idempotent point ids (EC-X-23); payload
carries indexed filter fields + verbatim text for one-hop quote retrieval.
Read path (Phase 3): filtered search / scroll / count where filtering happens
INSIDE Qdrant on indexed payload fields, never post-filtered in Python (PRD §11.1).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.query.filters import ReviewFilter


@dataclass
class VectorPoint:
    id: str
    vector: list[float]
    payload: dict


@dataclass
class ScoredPayload:
    payload: dict
    score: float


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _matches(payload: dict, f: ReviewFilter) -> bool:
    if payload.get("app_id") != f.app_id:
        return False
    if f.platform and payload.get("platform") != f.platform:
        return False
    if f.theme_id and payload.get("theme_id") != f.theme_id:
        return False
    r = payload.get("rating")
    if f.rating_min is not None and (r is None or r < f.rating_min):
        return False
    if f.rating_max is not None and (r is None or r > f.rating_max):
        return False
    if f.start or f.end:
        d = payload.get("review_date")
        if not d:
            return False
        dt = datetime.fromisoformat(d)
        if f.start and dt < f.start:
            return False
        if f.end and dt > f.end:
            return False
    return True


class VectorStore(Protocol):
    async def upsert(self, points: list[VectorPoint]) -> int: ...

    async def count(self, f: ReviewFilter | None = None) -> int: ...

    async def search(
        self, vector: list[float], f: ReviewFilter, limit: int, min_score: float
    ) -> list[ScoredPayload]: ...

    async def scroll(self, f: ReviewFilter, limit: int) -> list[dict]: ...


class InMemoryVectorStore:
    def __init__(self) -> None:
        self.points: dict[str, VectorPoint] = {}

    async def upsert(self, points: list[VectorPoint]) -> int:
        for p in points:
            self.points[p.id] = p
        return len(points)

    async def count(self, f: ReviewFilter | None = None) -> int:
        if f is None:
            return len(self.points)
        return sum(1 for p in self.points.values() if _matches(p.payload, f))

    async def search(self, vector, f, limit, min_score) -> list[ScoredPayload]:
        scored = [
            ScoredPayload(p.payload, _cosine(vector, p.vector))
            for p in self.points.values()
            if _matches(p.payload, f)
        ]
        scored = [s for s in scored if s.score >= min_score]
        scored.sort(key=lambda s: (-s.score, s.payload.get("source_review_id", "")))
        return scored[:limit]

    async def scroll(self, f, limit) -> list[dict]:
        rows = [p.payload for p in self.points.values() if _matches(p.payload, f)]
        rows.sort(
            key=lambda pl: (pl.get("review_date") or "", pl.get("source_review_id", "")),
            reverse=True,
        )
        return rows[:limit]


class QdrantVectorStore:
    def __init__(self, settings) -> None:
        self._settings = settings

    def _client(self):
        from app.vector.qdrant import make_async_client

        return make_async_client(self._settings)

    def _filter(self, f: ReviewFilter):
        from qdrant_client.models import (
            DatetimeRange,
            FieldCondition,
            Filter,
            MatchValue,
            Range,
        )

        must = [FieldCondition(key="app_id", match=MatchValue(value=f.app_id))]
        if f.platform:
            must.append(FieldCondition(key="platform", match=MatchValue(value=f.platform)))
        if f.theme_id:
            must.append(FieldCondition(key="theme_id", match=MatchValue(value=f.theme_id)))
        if f.rating_min is not None or f.rating_max is not None:
            must.append(FieldCondition(key="rating", range=Range(gte=f.rating_min, lte=f.rating_max)))
        if f.start or f.end:
            must.append(FieldCondition(key="review_date", range=DatetimeRange(gte=f.start, lte=f.end)))
        return Filter(must=must)

    async def upsert(self, points: list[VectorPoint]) -> int:
        if not points:
            return 0
        from qdrant_client.models import PointStruct

        await self._client().upsert(
            collection_name=self._settings.qdrant_collection,
            points=[PointStruct(id=p.id, vector=p.vector, payload=p.payload) for p in points],
        )
        return len(points)

    async def count(self, f: ReviewFilter | None = None) -> int:
        res = await self._client().count(
            collection_name=self._settings.qdrant_collection,
            count_filter=self._filter(f) if f else None,
        )
        return int(res.count)

    async def search(self, vector, f, limit, min_score) -> list[ScoredPayload]:
        res = await self._client().query_points(
            collection_name=self._settings.qdrant_collection,
            query=vector,
            query_filter=self._filter(f),
            limit=limit,
            score_threshold=min_score,
            with_payload=True,
        )
        return [ScoredPayload(p.payload, float(p.score)) for p in res.points]

    async def scroll(self, f, limit) -> list[dict]:
        points, _ = await self._client().scroll(
            collection_name=self._settings.qdrant_collection,
            scroll_filter=self._filter(f),
            limit=limit,
            with_payload=True,
        )
        return [p.payload for p in points]
