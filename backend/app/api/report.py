"""Report API (Phase 5) — the orchestration entry point.

POST /report returns the full Product Intelligence Report. Warm apps build from
stored evidence (served from cache when unchanged); a cold app (platform + name)
self-ingests and enriches first, under a single-flight lock so concurrent requests
don't double-scrape (EC-P5-08). Exactly one Gemini free-tier call per report; on any
synthesis failure the quantitative report still returns (EC-P5-01).
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.ingestion.collector import get_collector
from app.ingestion.enrichment.repository import PostgresEnrichmentRepository
from app.ingestion.enrichment.runner import run_enrichment
from app.ingestion.enrichment.vector_store import QdrantVectorStore
from app.ingestion.repository import PostgresReviewRepository
from app.ingestion.runner import run_ingestion
from app.ingestion.schemas import AppRef, Platform
from app.models import build_embedder, build_synthesizer
from app.query import quotes as quotes_tool
from app.query.filters import ReviewFilter
from app.query.stats_source import PostgresStatsSource
from app.report.budget import PremiumBudget
from app.report.builder import build_report
from app.report.orchestrator import ReportCache, SingleFlight, decide_route

router = APIRouter(prefix="/report", tags=["report"])

_cache = ReportCache()
_single_flight = SingleFlight()


class ReportRequest(BaseModel):
    app_id: str | None = None
    platform: Platform | None = None
    name: str | None = None
    store_app_id: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    limit: int = 100  # bounded cold scrape — keeps Render free-tier RAM/time in check
    deep: bool = False  # Deep Analysis: opt into a higher (still bounded) premium budget


async def _build(settings, app_id: str, app_name: str | None, start, end, deep: bool) -> dict:
    vector_store = QdrantVectorStore(settings)
    embedder = build_embedder(settings)

    async def quote_retriever(*, app_id, theme_id, limit):
        return await quotes_tool.retrieve(
            app_id=app_id, embedder=embedder, vector_store=vector_store, theme_id=theme_id, limit=limit
        )

    synthesizer = build_synthesizer(settings)
    if not synthesizer.is_configured():
        synthesizer = None  # no Gemini key yet -> quantitative report only

    ceiling = settings.deep_premium_ceiling if deep else settings.premium_call_ceiling
    rep = await build_report(
        app_id=app_id,
        app_name=app_name,
        stats_source=PostgresStatsSource(settings),
        quote_retriever=quote_retriever,
        synthesizer=synthesizer,
        budget=PremiumBudget(ceiling),
        deep=deep,
        start=start,
        end=end,
    )
    from app.obs.trace import emit

    emit("report.built", {"app_id": app_id, "premium_calls_used": rep.get("premium_calls_used"), "deep": deep})
    return rep


@router.post("")
async def report(req: ReportRequest) -> dict:
    settings = get_settings()
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database not configured (set DATABASE_URL).")
    if not settings.qdrant_url:
        raise HTTPException(status_code=503, detail="Vector store not configured (set QDRANT_URL).")

    vector_store = QdrantVectorStore(settings)

    # --- Warm path: app already ingested ---
    if req.app_id:
        data_version = str(await vector_store.count(ReviewFilter(app_id=req.app_id)))
        cache_key = ReportCache.key(req.app_id, req.start, req.end, data_version)
        cached = _cache.get(cache_key)
        route = decide_route(
            in_cache=cached is not None,
            cache_version=data_version,
            current_version=data_version,
            has_data=int(data_version) > 0,
        )
        if route == "serve_cache":
            return cached
        if route == "cold_start":
            return {"status": "unavailable", "detail": "App has no enriched reviews yet."}
        rep = await _build(settings, req.app_id, req.name, req.start, req.end, req.deep)
        _cache.put(cache_key, rep)
        return rep

    # --- Cold path: resolve + ingest + enrich, then build (single-flight) ---
    if not (req.platform and (req.name or req.store_app_id)):
        raise HTTPException(
            status_code=422, detail="Provide app_id, or platform + name/store_app_id for a cold start."
        )

    flight_key = f"{req.platform.value}:{req.store_app_id or req.name}"
    async with _single_flight.lock(flight_key):
        ref = AppRef(platform=req.platform, name=req.name, store_app_id=req.store_app_id)
        ingest = await run_ingestion(
            ref, req.limit, get_collector(req.platform), PostgresReviewRepository(settings)
        )
        if ingest.status in ("not_found", "unavailable", "no_reviews"):
            return {"status": ingest.status, "detail": ingest.detail}

        await run_enrichment(
            ingest.app_id,
            req.name,
            build_embedder(settings),
            QdrantVectorStore(settings),
            PostgresEnrichmentRepository(settings),
        )
        rep = await _build(settings, ingest.app_id, req.name, req.start, req.end, req.deep)
        data_version = str(await vector_store.count(ReviewFilter(app_id=ingest.app_id)))
        _cache.put(ReportCache.key(ingest.app_id, req.start, req.end, data_version), rep)
        return rep
