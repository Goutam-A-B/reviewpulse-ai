"""One-shot live end-to-end demo against real services.

    cd backend && python -m scripts.demo_live [store_app_id] [app_name] [limit]

Ingest (live Play Store) -> enrich (fastembed + embedded Qdrant + Supabase) ->
report (Stats + Quote Retriever + one Gemini call). Single process so embedded
Qdrant's path lock is held throughout.
"""
from __future__ import annotations

import asyncio
import sys

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
from app.query.stats_source import PostgresStatsSource
from app.report.budget import PremiumBudget
from app.report.builder import build_report
from app.vector.qdrant import make_async_client


async def ensure_collection(settings, dim: int) -> None:
    from qdrant_client.models import Distance, PayloadSchemaType, VectorParams

    client = make_async_client(settings)
    existing = [c.name for c in (await client.get_collections()).collections]
    if settings.qdrant_collection in existing:
        return
    await client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    for field, schema in (
        ("review_date", PayloadSchemaType.DATETIME),
        ("rating", PayloadSchemaType.INTEGER),
        ("app_id", PayloadSchemaType.KEYWORD),
        ("platform", PayloadSchemaType.KEYWORD),
        ("theme_id", PayloadSchemaType.KEYWORD),
    ):
        try:
            await client.create_payload_index(settings.qdrant_collection, field_name=field, field_schema=schema)
        except Exception:  # noqa: BLE001
            pass


async def main() -> None:
    store_app_id = sys.argv[1] if len(sys.argv) > 1 else "com.spotify.music"
    app_name = sys.argv[2] if len(sys.argv) > 2 else "Spotify"
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 150

    s = get_settings()
    embedder = build_embedder(s)

    print(f"== Ingest {app_name} ({store_app_id}) limit={limit} ==")
    ref = AppRef(platform=Platform.ANDROID, store_app_id=store_app_id)
    ing = await run_ingestion(ref, limit, get_collector(Platform.ANDROID), PostgresReviewRepository(s))
    print(
        f"   status={ing.status} collected={ing.collected} analysable={ing.analysable} "
        f"dupes={ing.duplicates} spam={ing.spam}"
    )
    if ing.status not in ("ok", "partial"):
        print("   stopping:", ing.detail)
        return

    await ensure_collection(s, s.embed_dim)

    print("== Enrich ==")
    enr = await run_enrichment(
        ing.app_id, app_name, embedder, QdrantVectorStore(s), PostgresEnrichmentRepository(s)
    )
    print(
        f"   status={enr.status} reviews={enr.reviews} themes={enr.themes} "
        f"keywords={enr.keywords} vectors={enr.vectors} sentiment={enr.sentiment_counts}"
    )

    print("== Report (one Gemini call) ==")

    async def quote_retriever(*, app_id, theme_id, limit):
        return await quotes_tool.retrieve(
            app_id=app_id, embedder=embedder, vector_store=QdrantVectorStore(s), theme_id=theme_id, limit=limit
        )

    rep = await build_report(
        app_id=ing.app_id,
        app_name=app_name,
        stats_source=PostgresStatsSource(s),
        quote_retriever=quote_retriever,
        synthesizer=build_synthesizer(s),
        budget=PremiumBudget(s.premium_call_ceiling),
    )
    print("   kpis:", rep["kpis"])
    print("   top themes:", [(t["label"], t["count"]) for t in rep["sections"]["top_themes"][:5]])
    print("   premium_calls_used:", rep["premium_calls_used"], "narrative_status:", rep["narrative_status"])
    print("   narrative:", (rep["narrative"] or "")[:500])
    for v in rep["sections"]["customer_quotes"][:3]:
        print(f"   quote [{v['rating']}*]: {v['text'][:110]}")


if __name__ == "__main__":
    asyncio.run(main())
