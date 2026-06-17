"""Ingestion API (Phase 1).

POST /ingest triggers collect -> clean -> persist for one app. Honest states
(no_reviews / not_found / unavailable) return 200 with a status field rather than
an error screen — the product always returns a result, only its kind differs.

Note: this triggers ingestion directly. Backgrounding it so the user never waits
is the orchestration layer's job in Phase 5; here we just expose the capability.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.ingestion.collector import get_collector
from app.ingestion.repository import PostgresReviewRepository
from app.ingestion.runner import run_ingestion
from app.ingestion.schemas import AppRef, Platform

router = APIRouter(prefix="/ingest", tags=["ingestion"])

DEFAULT_LIMIT = 300  # bounded cold scrape; backfill the tail later (EC-P1-07)
MAX_LIMIT = 1000


class IngestRequest(BaseModel):
    platform: Platform
    name: str | None = None
    store_app_id: str | None = None
    store_url: str | None = None
    country: str = "us"
    lang: str = "en"
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)


class IngestResponse(BaseModel):
    status: str
    app_id: str | None = None
    collected: int = 0
    analysable: int = 0
    spam: int = 0
    duplicates: int = 0
    requested: int = 0
    detail: str = ""
    candidates: list = []


@router.post("", response_model=IngestResponse)
async def ingest(req: IngestRequest) -> IngestResponse:
    settings = get_settings()
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database not configured (set DATABASE_URL).")
    if not (req.name or req.store_app_id or req.store_url):
        raise HTTPException(status_code=422, detail="Provide name, store_app_id, or store_url.")

    ref = AppRef(
        platform=req.platform,
        store_app_id=req.store_app_id,
        name=req.name,
        store_url=req.store_url,
        country=req.country,
        lang=req.lang,
    )
    result = await run_ingestion(
        ref, req.limit, get_collector(req.platform), PostgresReviewRepository(settings)
    )
    return IngestResponse(**result.__dict__)
