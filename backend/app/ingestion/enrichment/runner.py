"""Enrichment runner — embed -> sentiment -> cluster -> keywords -> persist (Phase 2).

Embedder, vector store, and repository are injected, so the deterministic core is
testable offline with a fake embedder + in-memory stores. Reviews are sorted by
source_review_id first so clustering is reproducible (EC-X-06). Only analysable,
non-duplicate, non-spam reviews are enriched (EC-P2-03).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.ingestion.enrichment import (
    EMBED_VERSION,
    SENTIMENT_VERSION,
    THEME_VERSION,
    review_point_id,
    theme_id,
)
from app.ingestion.enrichment import clusterer, keywords, sentiment
from app.ingestion.enrichment.vector_store import VectorPoint


@dataclass
class EnrichResult:
    status: str
    reviews: int = 0
    themes: int = 0
    keywords: int = 0
    vectors: int = 0
    sentiment_counts: dict = field(default_factory=dict)
    note: str = ""


async def run_enrichment(
    app_id: str,
    app_name: str | None,
    embedder,
    vector_store,
    repository,
    now: datetime | None = None,
) -> EnrichResult:
    now = now or datetime.now(timezone.utc)

    reviews = await repository.load_enrichable_reviews(app_id)
    reviews.sort(key=lambda r: r.source_review_id)  # deterministic input order
    if not reviews:
        return EnrichResult("no_reviews", note="no analysable reviews to enrich")

    texts = [r.text_clean for r in reviews]
    vectors = embedder.embed(texts)
    labels = sentiment.classify_many(texts)
    cl = clusterer.cluster(vectors, texts, app_name)
    kws = keywords.extract_keywords(texts, app_name)

    await repository.replace_sentiment(
        [
            {"review_id": r.review_id, "label": lab, "model_version": SENTIMENT_VERSION}
            for r, lab in zip(reviews, labels)
        ]
    )

    index_to_theme_id: dict[int, str] = {}
    themes_payload: list[dict] = []
    seen: set[str] = set()
    for t in cl.themes:
        tid = theme_id(app_id, t.label)
        index_to_theme_id[t.index] = tid
        if tid not in seen:
            seen.add(tid)
            themes_payload.append(
                {
                    "theme_id": tid,
                    "app_id": app_id,
                    "label": t.label,
                    "size": t.size,
                    "model_version": THEME_VERSION,
                }
            )

    review_themes_payload = [
        {"review_id": r.review_id, "theme_id": index_to_theme_id[cl.labels[i]], "distance": cl.distances[i]}
        for i, r in enumerate(reviews)
        if cl.labels[i] >= 0 and cl.labels[i] in index_to_theme_id
    ]
    await repository.replace_themes(app_id, themes_payload, review_themes_payload)

    await repository.replace_keywords(
        app_id, [{"term": k["term"], "frequency": k["frequency"]} for k in kws], now
    )

    points: list[VectorPoint] = []
    for i, r in enumerate(reviews):
        payload = {
            "review_id": r.review_id,
            "source_review_id": r.source_review_id,
            "app_id": app_id,
            "platform": r.platform,
            "rating": r.rating,
            "text_clean": r.text_clean,  # verbatim text for one-hop quote retrieval (Phase 3)
            "model_version": EMBED_VERSION,
        }
        if r.review_date is not None:
            payload["review_date"] = r.review_date.isoformat()
        if cl.labels[i] >= 0 and cl.labels[i] in index_to_theme_id:
            payload["theme_id"] = index_to_theme_id[cl.labels[i]]
        points.append(
            VectorPoint(
                id=review_point_id(app_id, r.platform, r.source_review_id),
                vector=[float(x) for x in vectors[i]],
                payload=payload,
            )
        )
    n_vectors = await vector_store.upsert(points)

    return EnrichResult(
        status="ok",
        reviews=len(reviews),
        themes=len(themes_payload),
        keywords=len(kws),
        vectors=n_vectors,
        sentiment_counts=dict(Counter(labels)),
        note=cl.note,
    )
