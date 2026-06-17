"""Stats Engine — plain, reproducible arithmetic over in-scope review records.

Every figure is guarded against division by zero (returns None / 'n/a' with a
denominator, never NaN or a misleading 0%, EC-P3-04) and every trend is suppressed
when its prior-window base is too small to be meaningful (EC-X-03, EC-P3-05). All
denominators come from the same scoped record set so panels reconcile (EC-X-09).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime

from app.query.stats_source import ReviewRecord, StatsSource

MIN_TREND_BASE = 5  # prior window must have at least this many reviews for a % trend


@dataclass
class TrendValue:
    current: int
    prior: int
    delta_pct: float | None  # None when base insufficient
    base_sufficient: bool


@dataclass
class ThemeStat:
    theme_id: str
    label: str | None
    count: int
    share: float | None


@dataclass
class ThemeImpact:
    theme_id: str
    label: str | None
    count: int
    impact: float  # negative share within the theme (severity proxy)
    frequency: float  # theme size / total (volume)
    score: float  # impact x frequency, scaled 0..100


def review_count(records: list[ReviewRecord]) -> int:
    return len(records)


def avg_rating(records: list[ReviewRecord]) -> float | None:
    rated = [r.rating for r in records if r.rating is not None]
    return round(sum(rated) / len(rated), 2) if rated else None


def sentiment_split(records: list[ReviewRecord]) -> dict:
    pos = sum(r.sentiment == "positive" for r in records)
    neu = sum(r.sentiment == "neutral" for r in records)
    neg = sum(r.sentiment == "negative" for r in records)
    return {"positive": pos, "neutral": neu, "negative": neg, "total": pos + neu + neg}


def sentiment_score(records: list[ReviewRecord]) -> float | None:
    s = sentiment_split(records)
    total = s["total"]
    return round((s["positive"] - s["negative"]) / total, 3) if total else None


def theme_distribution(records: list[ReviewRecord]) -> list[ThemeStat]:
    sizes: dict[str, int] = defaultdict(int)
    labels: dict[str, str | None] = {}
    for r in records:
        if r.theme_id:
            sizes[r.theme_id] += 1
            labels[r.theme_id] = r.theme_label
    total = len(records)
    out = [
        ThemeStat(tid, labels[tid], n, round(n / total, 3) if total else None)
        for tid, n in sizes.items()
    ]
    out.sort(key=lambda x: (-x.count, x.theme_id))
    return out


def theme_sentiment(records: list[ReviewRecord]) -> list[dict]:
    buckets: dict[str, dict] = defaultdict(lambda: {"positive": 0, "neutral": 0, "negative": 0})
    labels: dict[str, str | None] = {}
    for r in records:
        if r.theme_id and r.sentiment in ("positive", "neutral", "negative"):
            buckets[r.theme_id][r.sentiment] += 1
            labels[r.theme_id] = r.theme_label
    out = []
    for tid, b in buckets.items():
        total = b["positive"] + b["neutral"] + b["negative"]
        out.append({"theme_id": tid, "label": labels.get(tid), **b, "total": total})
    out.sort(key=lambda x: (-x["total"], x["theme_id"]))
    return out


def trend(current: list[ReviewRecord], prior: list[ReviewRecord]) -> TrendValue:
    c, p = len(current), len(prior)
    if p < MIN_TREND_BASE:
        return TrendValue(c, p, None, False)
    return TrendValue(c, p, round((c - p) / p * 100, 1), True)


def impact_frequency(records: list[ReviewRecord]) -> list[ThemeImpact]:
    total = len(records)
    by_theme: dict[str, list[ReviewRecord]] = defaultdict(list)
    for r in records:
        if r.theme_id:
            by_theme[r.theme_id].append(r)
    out: list[ThemeImpact] = []
    for tid, recs in by_theme.items():
        n = len(recs)
        neg = sum(x.sentiment == "negative" for x in recs)
        impact = neg / n if n else 0.0
        frequency = n / total if total else 0.0
        out.append(
            ThemeImpact(
                tid, recs[0].theme_label, n, round(impact, 3), round(frequency, 3),
                round(impact * frequency * 100, 2),
            )
        )
    out.sort(key=lambda x: (-x.score, x.theme_id))
    return out


def prior_window(start: datetime | None, end: datetime | None) -> tuple[datetime | None, datetime | None]:
    if not start or not end:
        return None, None
    duration = end - start
    return start - duration, start


async def compute_overview(
    source: StatsSource, app_id: str, start: datetime | None = None, end: datetime | None = None
) -> dict:
    records = await source.records(app_id, start, end)
    ps, pe = prior_window(start, end)
    prior = await source.records(app_id, ps, pe) if ps else []

    return {
        "reviews_analysed": review_count(records),
        "avg_rating": avg_rating(records),
        "sentiment_score": sentiment_score(records),
        "sentiment_split": sentiment_split(records),
        "theme_count": len(theme_distribution(records)),
        "theme_distribution": [asdict(t) for t in theme_distribution(records)],
        "theme_sentiment": theme_sentiment(records),
        "reviews_trend": asdict(trend(records, prior)),
        "impact_frequency": [asdict(t) for t in impact_frequency(records)],
        "window": {
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
        },
    }
