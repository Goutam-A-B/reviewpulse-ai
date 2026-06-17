"""Enrichment API (Phase 2).

POST /enrich runs embed -> sentiment -> cluster -> keywords -> persist for an
already-ingested app (use the app_id returned by /ingest). Free/local and
deterministic; consumes no premium budget.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.ingestion.enrichment.repository import PostgresEnrichmentRepository
from app.ingestion.enrichment.runner import run_enrichment
from app.ingestion.enrichment.vector_store import QdrantVectorStore
from app.models import build_embedder

router = APIRouter(prefix="/enrich", tags=["enrichment"])


class EnrichRequest(BaseModel):
    app_id: str
    app_name: str | None = None


class EnrichResponse(BaseModel):
    status: str
    reviews: int = 0
    themes: int = 0
    keywords: int = 0
    vectors: int = 0
    sentiment_counts: dict = {}
    note: str = ""


@router.post("", response_model=EnrichResponse)
async def enrich(req: EnrichRequest) -> EnrichResponse:
    settings = get_settings()
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Database not configured (set DATABASE_URL).")
    if not settings.qdrant_url:
        raise HTTPException(status_code=503, detail="Vector store not configured (set QDRANT_URL).")

    result = await run_enrichment(
        req.app_id,
        req.app_name,
        build_embedder(settings),
        QdrantVectorStore(settings),
        PostgresEnrichmentRepository(settings),
    )
    return EnrichResponse(**result.__dict__)
