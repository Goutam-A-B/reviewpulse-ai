"""Report Renderer — assembles the eight report sections (PRD §8.3).

Pure templating: every figure already comes from the Stats Engine / Quote Retriever
(verified, free); the narrative/recommendations come from the single synthesis call.
Section 8 (confidence & volume) attaches a denominator and a confidence to each theme
so an insight is never read without its sample size (EC-10.5).
"""
from __future__ import annotations


def _confidence_for(count: int) -> str:
    if count >= 8:
        return "high"
    if count >= 3:
        return "medium"
    return "low"


def render_report(
    *,
    app_id: str,
    app_name: str | None,
    overview: dict,
    user_voices: list[dict],
    narrative: str | None,
    recommendations: list[dict],
    priority_rationale: list[dict],
    narrative_status: str,
    premium_used: int,
) -> dict:
    total = overview["reviews_analysed"]
    distribution = overview["theme_distribution"]

    confidence_volume = [
        {
            "theme_id": t["theme_id"],
            "label": t["label"],
            "count": t["count"],
            "denominator": total,
            "confidence": _confidence_for(t["count"]),
        }
        for t in distribution
    ]

    rationale_by_theme = {r["theme_id"]: r["rationale"] for r in priority_rationale}
    priority_areas = [
        {**imp, "rationale": rationale_by_theme.get(imp["theme_id"])}
        for imp in overview["impact_frequency"]
    ]

    return {
        "app_id": app_id,
        "app": app_name,
        "window": overview["window"],
        "kpis": {
            "reviews_analysed": overview["reviews_analysed"],
            "avg_rating": overview["avg_rating"],
            "sentiment_score": overview["sentiment_score"],
            "theme_count": overview["theme_count"],
        },
        "sections": {
            "top_themes": distribution,  # 1
            "theme_sentiment": overview["theme_sentiment"],  # 2
            "customer_quotes": user_voices,  # 3
            "trends_and_correlations": {"reviews_trend": overview["reviews_trend"]},  # 4
            "theme_distribution": distribution,  # 5
            "recommendations": recommendations,  # 6
            "priority_areas": priority_areas,  # 7
            "confidence_volume": confidence_volume,  # 8
        },
        "narrative": narrative,
        "narrative_status": narrative_status,
        "premium_calls_used": premium_used,
    }
