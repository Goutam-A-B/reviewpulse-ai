"""Post-validation of the synthesis output (Principle 2 at the output boundary).

The premium model writes prose, but it must not introduce a recommendation or
rationale tied to a theme that isn't in the verified findings (EC-P5-03). Anything
ungrounded is stripped before it can reach the user. A missing narrative is treated
as a failed synthesis so the caller degrades gracefully.
"""
from __future__ import annotations


def validate_synthesis(out: dict, approved: dict) -> dict:
    if not isinstance(out, dict):
        raise ValueError("synthesis output is not an object")

    valid_theme_ids = {t["theme_id"] for t in approved.get("themes", [])}

    narrative = out.get("narrative")
    if not isinstance(narrative, str) or not narrative.strip():
        raise ValueError("synthesis missing narrative")

    recommendations = []
    for r in out.get("recommendations") or []:
        if not isinstance(r, dict):
            continue
        tid = r.get("theme_id")
        if tid is not None and tid not in valid_theme_ids:
            continue  # drop a recommendation citing an unknown theme
        recommendations.append({"text": str(r.get("text", "")), "theme_id": tid})

    priority_rationale = []
    for r in out.get("priority_rationale") or []:
        if not isinstance(r, dict):
            continue
        tid = r.get("theme_id")
        if tid not in valid_theme_ids:
            continue  # rationale must point at a real theme
        priority_rationale.append({"theme_id": tid, "rationale": str(r.get("rationale", ""))})

    return {
        "narrative": narrative,
        "recommendations": recommendations,
        "priority_rationale": priority_rationale,
    }
