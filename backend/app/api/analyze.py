"""Agent API (Phase 4).

POST /analyze runs the Analyst Agent + Critic over the stored evidence for a topic
and timeframe, returning verified structured findings with denominators and
confidence. Reasoning runs on the Groq free tier (structured fallback) — zero
premium budget. The narrative/recommendations come later, in Phase 5.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agent.analyst import run_analysis
from app.agent.cache import DecisionPathCache
from app.agent.reasoner import GroqReasoner, StructuredReasoner
from app.config import get_settings
from app.ingestion.enrichment.vector_store import QdrantVectorStore
from app.models import build_embedder
from app.query.filters import ReviewFilter

router = APIRouter(prefix="/analyze", tags=["agent"])

# Per-process decision-path cache (Phase 5 may persist it).
_cache = DecisionPathCache()


class AnalyzeRequest(BaseModel):
    app_id: str
    topic: str
    start: datetime | None = None
    end: datetime | None = None


@router.post("")
async def analyze(req: AnalyzeRequest) -> dict:
    settings = get_settings()
    if not settings.qdrant_url:
        raise HTTPException(status_code=503, detail="Vector store not configured (set QDRANT_URL).")

    vector_store = QdrantVectorStore(settings)
    # data_version = current vector count for the app: changes when new reviews are
    # enriched, so the decision-path cache invalidates on new data (EC-P4-09).
    data_version = str(await vector_store.count(ReviewFilter(app_id=req.app_id)))
    reasoner = GroqReasoner(settings) if settings.groq_api_key else StructuredReasoner()

    result = await run_analysis(
        app_id=req.app_id,
        topic=req.topic,
        embedder=build_embedder(settings),
        vector_store=vector_store,
        reasoner=reasoner,
        cache=_cache,
        data_version=data_version,
        start=req.start,
        end=req.end,
    )
    return asdict(result)
