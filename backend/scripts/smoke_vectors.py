"""Manual smoke test (no signup, no DB): fastembed + embedded Qdrant + Quote Retriever.

    cd backend && python -m scripts.smoke_vectors
"""
from __future__ import annotations

import asyncio
import tempfile
import uuid

from app.config import Settings
from app.ingestion.enrichment.vector_store import QdrantVectorStore, VectorPoint
from app.models.fastembed_embedder import FastEmbedEmbedder
from app.query import quotes as qt
from app.vector.qdrant import make_async_client


async def main() -> None:
    tmp = tempfile.mkdtemp(prefix="qdrant_smoke_")
    s = Settings(_env_file=None, qdrant_local_path=tmp)

    emb = FastEmbedEmbedder(s)
    texts = [
        "login keeps failing on startup",
        "cannot log in at all, stuck on the login screen",
        "payment was declined twice",
        "refund never arrived after a week",
    ]
    vectors = emb.embed(texts)
    print("embed_dim:", len(vectors[0]))

    from qdrant_client.models import Distance, VectorParams

    client = make_async_client(s)
    await client.create_collection(
        collection_name=s.qdrant_collection,
        vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE),
    )

    store = QdrantVectorStore(s)
    points = [
        VectorPoint(
            id=str(uuid.uuid4()),
            vector=vectors[i],
            payload={
                "app_id": "a",
                "platform": "android",
                "rating": 1,
                "review_date": "2026-06-01T00:00:00+00:00",
                "text_clean": texts[i],
                "source_review_id": str(i),
            },
        )
        for i in range(len(texts))
    ]
    print("upserted:", await store.upsert(points))

    res = await qt.retrieve(app_id="a", embedder=emb, vector_store=store, query_text="trouble signing in")
    print("query 'trouble signing in' ->", [q.text for q in res.quotes])
    print("total_in_scope:", res.total_in_scope)


if __name__ == "__main__":
    asyncio.run(main())
