"""Query API (Phase 3) — the deterministic evidence layer over stored data.

POST /query/quotes    -> verbatim quotes via filtered vector search (Qdrant)
POST /query/stats/overview -> KPIs, sentiment split, theme distribution, trend,
                              impact x frequency (Postgres). Free, no premium budget.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.ingestion.enrichment.vector_store import QdrantVectorStore
from app.models import build_embedder
from app.query import quotes as quotes_tool
from app.query.stats import compute_overview
from app.query.stats_source import PostgresStatsSource

router = APIRouter(prefix="/query", tags=["query"])


class QuotesRequest(BaseModel):
    app_id: str
    query_text: str | None = None
    theme_id: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    rating_min: int | None = None
    rating_max: int | None = None
    platform: str | None = None
    limit: int = 10


class OverviewRequest(BaseModel):
    app_id: str
    start: datetime | None = None
    end: datetime | None = None


@router.post("/quotes")
async def get_quotes(req: QuotesRequest) -> dict:
    settings = get_settings()
    if not settings.qdrant_url:
        raise HTTPException(status_code=503, detail="Vector store not configured (set QDRANT_URL).")
    result = await quotes_tool.retrieve(
        app_id=req.app_id,
        embedder=build_embedder(settings),
        vector_store=QdrantVectorStore(settings),
        query_text=req.query_text,
        theme_id=req.theme_id,
        start=req.start,
        end=req.end,
        rating_min=req.rating_min,
        rating_max=req.rating_max,
        platform=req.platform,
        limit=req.limit,
    )
    return asdict(result)


@router.post("/stats/overview")
async def stats_overview(req: OverviewRequest) -> dict:
    settings = get_settings()
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database not configured (set DATABASE_URL).")
    return await compute_overview(PostgresStatsSource(settings), req.app_id, req.start, req.end)


@router.get("/keywords")
async def keywords(app_id: str, limit: int = 20) -> dict:
    """Trending terms for an app (Keyword Extractor output). Powers the dashboard chips."""
    settings = get_settings()
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database not configured (set DATABASE_URL).")
    from sqlalchemy import text

    from app.db.session import get_engine

    engine = get_engine(settings)
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "select term, frequency from keywords where app_id = :app_id "
                    "order by frequency desc limit :limit"
                ),
                {"app_id": app_id, "limit": limit},
            )
        ).all()
    return {"keywords": [{"term": r[0], "frequency": r[1]} for r in rows]}
