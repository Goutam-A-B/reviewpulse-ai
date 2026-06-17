"""Phase 7 tests — Deep Analysis budget bounds + observability never blocks."""
from __future__ import annotations

from datetime import datetime, timezone

from app.obs import trace
from app.query.quotes import Quote, QuoteResult
from app.query.stats_source import InMemoryStatsSource, ReviewRecord
from app.report.budget import PremiumBudget
from app.report.builder import build_report

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _source():
    recs = [ReviewRecord(NOW, 1, "negative", "t-login", "login") for _ in range(6)] + [
        ReviewRecord(NOW, 5, "positive", "t-pay", "payment") for _ in range(4)
    ]
    return InMemoryStatsSource({"app-1": recs})


async def _fake_quotes(*, app_id, theme_id, limit):
    return QuoteResult(
        quotes=[Quote("verbatim", 1, "2026-06-01", f"{theme_id}-1", "android", None)],
        total_in_scope=5,
        returned=1,
    )


class FakeSynth:
    async def synthesize(self, findings):
        tid = findings["themes"][0]["theme_id"]
        return {"narrative": "n", "recommendations": [{"text": "x", "theme_id": tid}], "priority_rationale": []}


async def _build(budget, deep):
    return await build_report(
        app_id="app-1", app_name="A", stats_source=_source(), quote_retriever=_fake_quotes,
        synthesizer=FakeSynth(), budget=budget, deep=deep,
    )


async def test_deep_mode_uses_bounded_extra_budget():
    rep = await _build(PremiumBudget(3), deep=True)
    assert rep["premium_calls_used"] == 2  # initial + one refine pass


async def test_normal_mode_one_call():
    rep = await _build(PremiumBudget(1), deep=False)
    assert rep["premium_calls_used"] == 1


async def test_deep_mode_still_capped_by_ceiling():
    rep = await _build(PremiumBudget(1), deep=True)
    assert rep["premium_calls_used"] == 1  # a ceiling of 1 caps even deep mode (EC-P7-05)


def test_trace_emit_noop_without_key(monkeypatch):
    monkeypatch.setattr(trace, "get_settings", lambda: type("S", (), {"langsmith_api_key": ""})())
    trace.emit("evt", {"a": 1})  # must not raise


def test_trace_emit_swallows_errors(monkeypatch):
    monkeypatch.setattr(trace, "get_settings", lambda: type("S", (), {"langsmith_api_key": "bogus"})())
    trace.emit("evt", {"a": 1})  # bad key / missing SDK -> swallowed, never blocks (EC-P7-01)
