"""Analyst Agent loop tests — convergence, no-signal, iteration ceiling, cache replay."""
from __future__ import annotations

from app.agent.analyst import run_analysis
from app.agent.cache import DecisionPathCache
from app.agent.decisions import Action, Decision
from app.ingestion.enrichment.vector_store import InMemoryVectorStore, VectorPoint


class FakeEmbedder:
    def embed(self, texts):
        out = []
        for t in texts:
            tl = t.lower()
            if "login" in tl:
                out.append([1.0, 0.0, 0.0])
            elif "payment" in tl:
                out.append([0.0, 1.0, 0.0])
            else:
                out.append([0.0, 0.0, 1.0])
        return out


def _point(rid, text, vec):
    return VectorPoint(
        rid,
        vec,
        {
            "review_id": rid,
            "source_review_id": rid,
            "app_id": "app-1",
            "platform": "android",
            "rating": 1,
            "review_date": "2026-06-01T00:00:00+00:00",
            "text_clean": text,
            "theme_id": "t-login",
        },
    )


async def _store():
    vs = InMemoryVectorStore()
    await vs.upsert(
        [_point(f"l{i}", f"login broken case {i}", [1.0, 0.0, 0.0]) for i in range(10)]
        + [_point(f"p{i}", f"payment issue {i}", [0.0, 1.0, 0.0]) for i in range(4)]
    )
    return vs


async def test_converges_with_signal():
    vs = await _store()
    res = await run_analysis(app_id="app-1", topic="login", embedder=FakeEmbedder(), vector_store=vs)
    assert res.status == "ok"
    assert res.findings
    assert res.findings[0]["support"] >= 8
    assert res.findings[0]["confidence"] in ("high", "medium", "low")
    assert res.premium_calls == 0


async def test_no_signal_is_honest():
    vs = await _store()
    res = await run_analysis(
        app_id="app-1", topic="kyc onboarding", embedder=FakeEmbedder(), vector_store=vs
    )
    assert res.status == "no_signal"
    assert res.findings == []


async def test_iteration_ceiling_bounds_the_loop():
    class Cycler:
        name = "cycler"

        def next_action(self, ctx):
            # Always continue with a fresh query so cycle-detection doesn't fire —
            # only the hard ceiling should stop it.
            return Decision(Action.REFORMULATE, query=f"q{ctx['iteration']}", reason="loop")

    vs = await _store()
    res = await run_analysis(
        app_id="app-1", topic="login", embedder=FakeEmbedder(), vector_store=vs, reasoner=Cycler()
    )
    assert res.iterations == 6  # MAX_ITERATIONS


async def test_cache_replay_and_invalidation():
    vs = await _store()
    cache = DecisionPathCache()
    r1 = await run_analysis(
        app_id="app-1", topic="login", embedder=FakeEmbedder(), vector_store=vs, cache=cache, data_version="v1"
    )
    r2 = await run_analysis(
        app_id="app-1", topic="login", embedder=FakeEmbedder(), vector_store=vs, cache=cache, data_version="v1"
    )
    assert r1.status == "ok" and r2.status == "cached"
    assert r2.findings == r1.findings

    r3 = await run_analysis(
        app_id="app-1", topic="login", embedder=FakeEmbedder(), vector_store=vs, cache=cache, data_version="v2"
    )
    assert r3.status == "ok"  # new data_version invalidates the replay (EC-P4-09)
