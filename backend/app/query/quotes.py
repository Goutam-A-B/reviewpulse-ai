"""Quote Retriever — verbatim excerpts from stored evidence (PRD §3, Phase 3).

Returns rows that exist or nothing; it cannot invent a quote (Principle 2). A text
query is embedded and matched by filtered vector search with a relevance threshold,
so off-topic neighbours are not asserted as evidence (EC-P3-02/03). Near-duplicate
quotes are collapsed (EC-P3-07), results are capped (EC-P3-10), and the in-scope
total is always returned as the denominator (EC-P3-08). Sufficiency judgment is the
Critic's job in Phase 4 — this tool only retrieves and ranks.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from app.query.filters import ReviewFilter

DEFAULT_MIN_SCORE = 0.3
CANDIDATE_MULTIPLIER = 5


@dataclass
class Quote:
    text: str
    rating: int | None
    review_date: str | None
    source_review_id: str
    platform: str | None
    score: float | None


@dataclass
class QuoteResult:
    quotes: list[Quote]
    total_in_scope: int
    returned: int
    note: str = ""


def _fingerprint(text: str) -> str:
    return hashlib.sha256(" ".join(text.lower().split()).encode("utf-8")).hexdigest()


async def retrieve(
    *,
    app_id: str,
    embedder,
    vector_store,
    query_text: str | None = None,
    theme_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    rating_min: int | None = None,
    rating_max: int | None = None,
    platform: str | None = None,
    limit: int = 10,
    min_score: float = DEFAULT_MIN_SCORE,
) -> QuoteResult:
    f = ReviewFilter(app_id, start, end, rating_min, rating_max, theme_id, platform)

    total = await vector_store.count(f)
    if total == 0:
        return QuoteResult([], 0, 0, note="no reviews match this scope")

    if query_text:
        vector = embedder.embed([query_text])[0]
        scored = await vector_store.search(vector, f, limit * CANDIDATE_MULTIPLIER, min_score)
        candidates = [(s.payload, s.score) for s in scored]
    else:
        payloads = await vector_store.scroll(f, limit * CANDIDATE_MULTIPLIER)
        candidates = [(pl, None) for pl in payloads]

    seen: set[str] = set()
    quotes: list[Quote] = []
    for payload, score in candidates:
        text = payload.get("text_clean") or ""
        if not text:
            continue
        fp = _fingerprint(text)
        if fp in seen:
            continue
        seen.add(fp)
        quotes.append(
            Quote(
                text=text,
                rating=payload.get("rating"),
                review_date=payload.get("review_date"),
                source_review_id=payload.get("source_review_id", ""),
                platform=payload.get("platform"),
                score=score,
            )
        )
        if len(quotes) >= limit:
            break

    note = "no strong evidence for this topic in scope" if (query_text and not quotes) else ""
    return QuoteResult(quotes, total, len(quotes), note)
