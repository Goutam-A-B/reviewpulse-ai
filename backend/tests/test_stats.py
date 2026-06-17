"""Stats Engine tests — guarded arithmetic, trend suppression, impact x frequency."""
from __future__ import annotations

from datetime import datetime, timezone

from app.query import stats
from app.query.stats_source import InMemoryStatsSource, ReviewRecord


def _rec(month, day, rating, sentiment, theme_id, label):
    return ReviewRecord(
        datetime(2026, month, day, tzinfo=timezone.utc), rating, sentiment, theme_id, label
    )


def test_empty_records_never_nan():
    assert stats.avg_rating([]) is None
    assert stats.sentiment_score([]) is None
    t = stats.trend([], [])
    assert t.delta_pct is None and t.base_sufficient is False


def test_sentiment_split_and_score():
    recs = [
        _rec(6, 1, 5, "positive", "t1", "a"),
        _rec(6, 1, 4, "positive", "t1", "a"),
        _rec(6, 1, 1, "negative", "t1", "a"),
        _rec(6, 1, 3, "neutral", "t1", "a"),
    ]
    split = stats.sentiment_split(recs)
    assert split == {"positive": 2, "neutral": 1, "negative": 1, "total": 4}
    assert stats.sentiment_score(recs) == round((2 - 1) / 4, 3)


def test_trend_suppressed_on_small_base():
    current = [_rec(6, 10, 5, "positive", "t1", "a")] * 8
    small_prior = [_rec(5, 20, 5, "positive", "t1", "a")] * 3  # < MIN_TREND_BASE
    ok_prior = [_rec(5, 20, 5, "positive", "t1", "a")] * 6

    suppressed = stats.trend(current, small_prior)
    assert suppressed.delta_pct is None and suppressed.base_sufficient is False

    computed = stats.trend(current, ok_prior)
    assert computed.base_sufficient is True
    assert computed.delta_pct == round((8 - 6) / 6 * 100, 1)


def test_impact_frequency_for_every_theme():
    recs = (
        [_rec(6, 1, 1, "negative", "t-login", "login")] * 5
        + [_rec(6, 1, 5, "positive", "t-pay", "payment")] * 3
    )
    out = stats.impact_frequency(recs)
    ids = {t.theme_id for t in out}
    assert ids == {"t-login", "t-pay"}  # a score for every theme
    login = next(t for t in out if t.theme_id == "t-login")
    assert login.impact == 1.0  # all negative
    assert login.frequency == round(5 / 8, 3)
    assert out[0].theme_id == "t-login"  # highest score first


def test_theme_distribution_shares_and_order():
    recs = [_rec(6, 1, 3, "neutral", "t1", "a")] * 5 + [_rec(6, 1, 3, "neutral", "t2", "b")] * 3
    dist = stats.theme_distribution(recs)
    assert [d.theme_id for d in dist] == ["t1", "t2"]
    assert dist[0].share == round(5 / 8, 3)


async def test_compute_overview_with_window():
    recs = (
        [_rec(6, 10, 1, "negative", "t-login", "login") for _ in range(5)]
        + [_rec(6, 11, 5, "positive", "t-pay", "payment") for _ in range(3)]
        + [_rec(5, 20, 3, "neutral", "t-login", "login") for _ in range(6)]  # prior window
    )
    source = InMemoryStatsSource({"app-1": recs})
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    end = datetime(2026, 6, 15, tzinfo=timezone.utc)

    overview = await stats.compute_overview(source, "app-1", start, end)
    assert overview["reviews_analysed"] == 8
    assert overview["avg_rating"] == 2.5
    assert overview["sentiment_score"] == -0.25
    assert overview["theme_count"] == 2
    assert overview["reviews_trend"]["base_sufficient"] is True
    assert overview["reviews_trend"]["delta_pct"] == round((8 - 6) / 6 * 100, 1)
    assert len(overview["impact_frequency"]) == 2
