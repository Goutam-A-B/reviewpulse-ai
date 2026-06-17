"""Theme clusterer tests — determinism (EC-X-06) and honest no-themes guard (EC-P2-06)."""
from __future__ import annotations

from app.ingestion.enrichment import clusterer


def _blob(center, n, dim=8, jitter=0.001):
    out = []
    for i in range(n):
        v = [0.0] * dim
        for d, c in enumerate(center):
            v[d] = c
        v[0] += i * jitter  # tiny deterministic perturbation
        out.append(v)
    return out


def test_insufficient_reviews_yields_no_themes():
    vecs = [[1.0, 0.0], [0.0, 1.0]] * 3  # 6 < MIN_FOR_CLUSTERING
    res = clusterer.cluster(vecs, ["a b c"] * 6)
    assert res.themes == []
    assert all(label == -1 for label in res.labels)
    assert "insufficient" in res.note


def test_two_clusters_found_and_deterministic():
    a = _blob([1, 0, 0, 0, 0, 0, 0, 0], 10)
    b = _blob([0, 1, 0, 0, 0, 0, 0, 0], 10)
    vecs = a + b
    texts = ["login crash error"] * 10 + ["payment refund billing"] * 10

    r1 = clusterer.cluster(vecs, texts, app_name="App")
    r2 = clusterer.cluster(vecs, texts, app_name="App")

    assert r1.labels == r2.labels  # deterministic assignment
    assert [t.label for t in r1.themes] == [t.label for t in r2.themes]
    assert len(r1.themes) >= 2
    assert all(d >= 0 for d in r1.distances)
