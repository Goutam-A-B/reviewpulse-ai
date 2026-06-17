"""FastAPI entrypoint (Phase 0).

Run: uvicorn app.main:app --reload  (from the backend/ directory)
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analyze import router as analyze_router
from app.api.enrichment import router as enrichment_router
from app.api.ingestion import router as ingestion_router
from app.api.query import router as query_router
from app.api.report import router as report_router
from app.config import get_settings
from app.health import health_report

app = FastAPI(title="ReviewPulse AI", version="0.1.0-phase1")

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingestion_router)
app.include_router(enrichment_router)
app.include_router(query_router)
app.include_router(analyze_router)
app.include_router(report_router)


@app.get("/")
async def root() -> dict:
    return {
        "service": "ReviewPulse AI backend",
        "phase": "0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health() -> dict:
    return await health_report(get_settings())
