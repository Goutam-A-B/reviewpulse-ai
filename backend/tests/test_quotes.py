"""Quote Retriever tests — relevance threshold, dedup, honest empty/no-evidence states."""
from __future__ import annotations

from app.ingestion.enrichment.vector_store import InMemoryVectorStore, VectorPoint
from app.query import quotes


class FakeEmbedder:
    def embed(self, texts):
        out = []
        for t in texts:
            tl = t.lower()
            if "login" in tl:
                out.append([1.0, 0.0])
            elif "payment" in tl:
                out.append([0.0, 1.0])
            else:
                out.append([0.5, 0.5])
        return out


def _point(rid, text, vec, app_id="app-1", rating=2, date="2026-06-01T00:00:00+00:00", theme="t-login"):
    return VectorPoint(
        id=rid,
        vector=vec,
        payload={
            "review_id": rid,
            "source_review_id": rid,
            "app_id": app_id,
            "platform": "android",
            "rating": rating,
            "review_date": date,
            "text_clean": text,
            "theme_id": theme,
        },
    )


async def _store():
    vs = InMemoryVectorStore()
    await vs.upsert(
        [
            _point("l1", "login keeps failing", [1.0, 0.0], theme="t-login"),
            _point("l2", "cannot log in at all", [1.0, 0.0], theme="t-login"),
            _point("p1", "payment was declined", [0.0, 1.0], rating=1, theme="t-pay"),
            _point("p2", "refund never arrived", [0.0, 1.0], rating=1, theme="t-pay"),
        ]
    )
    return vs


async def test_query_returns_only_relevant_above_threshold():
    vs = await _store()
    res = await quotes.retrieve(app_id="app-1", embedder=FakeEmbedder(), vector_store=vs, query_text="login problems")
    assert res.total_in_scope == 4  # denominator = all in scope
    texts = [q.text for q in res.quotes]
    assert "login keeps failing" in texts
    assert "payment was declined" not in texts  # off-topic excluded (EC-P3-02)


async def test_no_strong_evidence_note():
    vs = await _store()
    res = await quotes.retrieve(
        app_id="app-1", embedder=FakeEmbedder(), vector_store=vs, query_text="unrelated topic", min_score=0.9
    )
    assert res.quotes == []
    assert "no strong evidence" in res.note


async def test_empty_scope_state():
    vs = await _store()
    res = await quotes.retrieve(app_id="other-app", embedder=FakeEmbedder(), vector_store=vs, query_text="login")
    assert res.total_in_scope == 0
    assert "no reviews match this scope" in res.note


async def test_dedup_near_duplicate_quotes():
    vs = InMemoryVectorStore()
    await vs.upsert(
        [
            _point("a", "exact same complaint", [1.0, 0.0]),
            _point("b", "exact same complaint", [1.0, 0.0]),
            _point("c", "a different complaint about login", [1.0, 0.0]),
        ]
    )
    res = await quotes.retrieve(app_id="app-1", embedder=FakeEmbedder(), vector_store=vs, query_text="login")
    assert sum(q.text == "exact same complaint" for q in res.quotes) == 1


async def test_theme_browse_without_query():
    vs = await _store()
    res = await quotes.retrieve(app_id="app-1", embedder=FakeEmbedder(), vector_store=vs, theme_id="t-pay")
    assert {q.source_review_id for q in res.quotes} == {"p1", "p2"}
    assert all(q.score is None for q in res.quotes)  # browse, not scored


async def test_rating_filter_scopes_results():
    vs = await _store()
    res = await quotes.retrieve(
        app_id="app-1", embedder=FakeEmbedder(), vector_store=vs, rating_max=1
    )
    assert res.total_in_scope == 2  # only the two 1-star payment reviews
