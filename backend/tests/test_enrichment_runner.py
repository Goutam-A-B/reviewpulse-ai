"""Enrichment runner tests — full flow + deterministic re-run (Phase 2 exit gate)."""
from __future__ import annotations

from app.ingestion.enrichment.repository import EnrichReview, InMemoryEnrichmentRepository
from app.ingestion.enrichment.runner import run_enrichment
from app.ingestion.enrichment.vector_store import InMemoryVectorStore


class FakeEmbedder:
    name = "fake"
    dim = 4

    def is_configured(self) -> bool:
        return True

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            tl = t.lower()
            out.append(
                [
                    float(tl.count("login") + tl.count("crash")),
                    float(tl.count("payment") + tl.count("refund")),
                    float(len(t) % 7),
                    1.0,
                ]
            )
        return out


def _reviews(n_each: int = 8) -> list[EnrichReview]:
    revs: list[EnrichReview] = []
    for i in range(n_each):
        revs.append(EnrichReview(f"r-login-{i}", f"login-{i}", "android", "login crashes on startup error", 1, None))
    for i in range(n_each):
        revs.append(EnrichReview(f"r-pay-{i}", f"pay-{i}", "android", "payment refund failed billing", 2, None))
    return revs


async def test_enrichment_ok_persists_everything():
    repo = InMemoryEnrichmentRepository(_reviews())
    vs = InMemoryVectorStore()
    res = await run_enrichment("app-1", "MyApp", FakeEmbedder(), vs, repo)
    assert res.status == "ok"
    assert res.reviews == 16
    assert len(repo.sentiment) == 16  # a label for every review
    assert await vs.count() == 16  # a vector for every review
    assert res.keywords > 0
    assert res.themes >= 2
    assert sum(res.sentiment_counts.values()) == 16


async def test_enrichment_is_deterministic_on_rerun():
    revs = _reviews()
    repo1, vs1 = InMemoryEnrichmentRepository(list(revs)), InMemoryVectorStore()
    repo2, vs2 = InMemoryEnrichmentRepository(list(revs)), InMemoryVectorStore()

    r1 = await run_enrichment("app-1", "MyApp", FakeEmbedder(), vs1, repo1)
    r2 = await run_enrichment("app-1", "MyApp", FakeEmbedder(), vs2, repo2)

    assert r1 == r2
    assert repo1.themes.keys() == repo2.themes.keys()  # stable theme ids
    assert repo1.sentiment == repo2.sentiment
    assert set(vs1.points.keys()) == set(vs2.points.keys())  # stable vector ids


async def test_no_reviews_state():
    res = await run_enrichment(
        "app-x", None, FakeEmbedder(), InMemoryVectorStore(), InMemoryEnrichmentRepository([])
    )
    assert res.status == "no_reviews"
