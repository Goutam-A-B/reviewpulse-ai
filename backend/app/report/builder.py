"""build_report — assemble the verified quantitative report, then spend at most one
premium call to write the narrative (Phase 5).

The quantitative half (KPIs, themes, sentiment, distribution, trend, impact,
quotes) is built first and always returned. Synthesis is attempted only if the
budget allows; any failure degrades gracefully to narrative_status='unavailable'
with the full quantitative report intact — never an error (EC-P5-01/02/04/10).
Synthesis input is strictly the approved findings (EC-P5-12) and its output is
post-validated (EC-P5-03).
"""
from __future__ import annotations

from datetime import datetime

from app.query.stats import compute_overview
from app.report.budget import PremiumBudget
from app.report.renderer import render_report
from app.report.synthesis import validate_synthesis


async def build_report(
    *,
    app_id: str,
    app_name: str | None,
    stats_source,
    quote_retriever,
    synthesizer,
    budget: PremiumBudget,
    deep: bool = False,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict:
    overview = await compute_overview(stats_source, app_id, start, end)

    user_voices: list[dict] = []
    for t in overview["theme_distribution"][:5]:
        qres = await quote_retriever(app_id=app_id, theme_id=t["theme_id"], limit=3)
        for q in qres.quotes:
            user_voices.append(
                {
                    "text": q.text,
                    "rating": q.rating,
                    "review_date": q.review_date,
                    "source_review_id": q.source_review_id,
                    "platform": q.platform,
                    "theme_id": t["theme_id"],
                    "theme_label": t["label"],
                }
            )

    approved = {
        "themes": overview["theme_distribution"],
        "theme_sentiment": overview["theme_sentiment"],
        "sentiment": overview["sentiment_split"],
        "trend": overview["reviews_trend"],
        "impact": overview["impact_frequency"],
        "quotes": user_voices,
    }

    narrative: str | None = None
    recommendations: list[dict] = []
    priority_rationale: list[dict] = []
    narrative_status = "unavailable"
    premium_used = 0

    if synthesizer is not None and budget.can_spend():
        budget.spend()  # count the slot before the call (EC-P5-11)
        premium_used += 1
        try:
            clean = validate_synthesis(await synthesizer.synthesize(approved), approved)
            narrative = clean["narrative"]
            recommendations = clean["recommendations"]
            priority_rationale = clean["priority_rationale"]
            narrative_status = "ok"
            # Deep Analysis: an opt-in refinement pass, still bounded by the budget (EC-P7-05).
            if deep and budget.can_spend():
                budget.spend()
                premium_used += 1
                try:
                    refined = validate_synthesis(
                        await synthesizer.synthesize({**approved, "previous": clean}), approved
                    )
                    narrative = refined["narrative"]
                    recommendations = refined["recommendations"]
                    priority_rationale = refined["priority_rationale"]
                except Exception:  # noqa: BLE001 - keep first-pass result on refine failure
                    pass
        except Exception:  # noqa: BLE001 - degrade on rate-limit/malformed/timeout
            narrative_status = "unavailable"

    return render_report(
        app_id=app_id,
        app_name=app_name,
        overview=overview,
        user_voices=user_voices,
        narrative=narrative,
        recommendations=recommendations,
        priority_rationale=priority_rationale,
        narrative_status=narrative_status,
        premium_used=premium_used,
    )
