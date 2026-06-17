"""Phase 5 tests — premium ceiling, synthesis validation, report assembly with
graceful degradation, routing truth table, single-flight dedup."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.query.quotes import Quote, QuoteResult
from app.query.stats_source import InMemoryStatsSource, ReviewRecord
from app.report.budget import PremiumBudget, PremiumCeilingReached
from app.report.builder import build_report
from app.report.orchestrator import ReportCache, SingleFlight, decide_route
from app.report.synthesis import validate_synthesis

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)

EIGHT_SECTIONS = {
    "top_themes",
    "theme_sentiment",
    "customer_quotes",
    "trends_and_correlations",
    "theme_distribution",
    "recommendations",
    "priority_areas",
    "confidence_volume",
}


def _source():
    records = [ReviewRecord(NOW, 1, "negative", "t-login", "login") for _ in range(6)] + [
        ReviewRecord(NOW, 5, "positive", "t-pay", "payment") for _ in range(4)
    ]
    return InMemoryStatsSource({"app-1": records})


async def _fake_quotes(*, app_id, theme_id, limit):
    return QuoteResult(
        quotes=[Quote("a verbatim complaint", 1, "2026-06-01", f"{theme_id}-1", "android", None)],
        total_in_scope=5,
        returned=1,
    )


class FakeSynth:
    def __init__(self, fail=False):
        self.fail = fail

    async def synthesize(self, findings):
        if self.fail:
            raise RuntimeError("rate limited")
        tid = findings["themes"][0]["theme_id"]
        return {
            "narrative": "Login is the top pain point.",
            "recommendations": [{"text": "Fix login", "theme_id": tid}],
            "priority_rationale": [{"theme_id": tid, "rationale": "highest negative volume"}],
        }


# --- builder ---

async def test_build_report_success_one_call_eight_sections():
    rep = await build_report(
        app_id="app-1", app_name="MyApp", stats_source=_source(),
        quote_retriever=_fake_quotes, synthesizer=FakeSynth(), budget=PremiumBudget(1),
    )
    assert rep["narrative_status"] == "ok"
    assert rep["premium_calls_used"] == 1
    assert set(rep["sections"].keys()) == EIGHT_SECTIONS
    assert rep["sections"]["recommendations"]
    assert rep["kpis"]["reviews_analysed"] == 10


async def test_build_report_degrades_on_synthesis_failure():
    rep = await build_report(
        app_id="app-1", app_name="MyApp", stats_source=_source(),
        quote_retriever=_fake_quotes, synthesizer=FakeSynth(fail=True), budget=PremiumBudget(1),
    )
    assert rep["narrative_status"] == "unavailable"
    assert rep["premium_calls_used"] == 1  # the slot was counted
    assert rep["narrative"] is None
    # full quantitative report still present
    assert rep["kpis"]["reviews_analysed"] == 10
    assert rep["sections"]["top_themes"]
    assert rep["sections"]["customer_quotes"]


async def test_build_report_respects_zero_ceiling():
    rep = await build_report(
        app_id="app-1", app_name="MyApp", stats_source=_source(),
        quote_retriever=_fake_quotes, synthesizer=FakeSynth(), budget=PremiumBudget(0),
    )
    assert rep["premium_calls_used"] == 0
    assert rep["narrative_status"] == "unavailable"
    assert rep["sections"]["top_themes"]  # quantitative report still produced


# --- synthesis validation ---

def test_validate_synthesis_strips_unsupported_claims():
    approved = {"themes": [{"theme_id": "t-login"}]}
    out = {
        "narrative": "x",
        "recommendations": [
            {"text": "ok", "theme_id": "t-login"},
            {"text": "bogus", "theme_id": "t-ghost"},
        ],
        "priority_rationale": [{"theme_id": "t-ghost", "rationale": "nope"}],
    }
    clean = validate_synthesis(out, approved)
    assert [r["theme_id"] for r in clean["recommendations"]] == ["t-login"]
    assert clean["priority_rationale"] == []


def test_validate_synthesis_requires_narrative():
    with pytest.raises(ValueError):
        validate_synthesis({"recommendations": []}, {"themes": []})


# --- budget ---

def test_budget_enforces_ceiling():
    b = PremiumBudget(1)
    assert b.can_spend()
    b.spend()
    assert not b.can_spend()
    with pytest.raises(PremiumCeilingReached):
        b.spend()


# --- routing ---

def test_decide_route_truth_table():
    assert decide_route(in_cache=True, cache_version="v1", current_version="v1", has_data=True) == "serve_cache"
    assert decide_route(in_cache=True, cache_version="v1", current_version="v2", has_data=True) == "build_warm"
    assert decide_route(in_cache=False, cache_version=None, current_version="v1", has_data=True) == "build_warm"
    assert decide_route(in_cache=False, cache_version=None, current_version="v1", has_data=False) == "cold_start"


def test_report_cache_only_stores_complete_reports():
    cache = ReportCache()
    key = ReportCache.key("app-1", None, None, "v1")
    cache.put(key, {"narrative_status": "unavailable"})
    assert cache.get(key) is None  # degraded not cached (EC-P5-07)
    cache.put(key, {"narrative_status": "ok", "x": 1})
    assert cache.get(key) == {"narrative_status": "ok", "x": 1}


# --- single-flight ---

async def test_single_flight_dedups_concurrent_cold_starts():
    sf = SingleFlight()
    cache: dict[str, str] = {}
    runs = {"n": 0}

    async def work():
        async with sf.lock("app-1"):
            if "app-1" in cache:
                return cache["app-1"]
            runs["n"] += 1
            await asyncio.sleep(0.01)
            cache["app-1"] = "report"
            return cache["app-1"]

    results = await asyncio.gather(work(), work(), work())
    assert runs["n"] == 1  # only one actually built (EC-P5-08)
    assert results == ["report", "report", "report"]
