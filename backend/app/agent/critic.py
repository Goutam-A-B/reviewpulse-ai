"""The Critic — Principle 2 turned into an adversary inside the system (PRD §5.2).

Before any claim is eligible for the report it must clear the Critic: enough sample,
at least one backing quote, and a confidence that reflects the denominator ("8 of 30"
vs "8 of 3,000", EC-10.5). Weak claims are downgraded or dropped, never silently
asserted (EC-P4-06). Correlations require real co-occurrence, not coincidence (EC-P4-04).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.agent import (
    HIGH_CONFIDENCE_RATIO,
    MED_CONFIDENCE_RATIO,
    MIN_CORRELATION_OVERLAP,
    MIN_SUPPORT,
    SUFFICIENT_SUPPORT,
)


@dataclass
class Finding:
    claim: str
    support: int
    denominator: int
    confidence: str  # high | medium | low | insufficient
    negative_share: float | None
    sample_quotes: list[dict]
    accepted: bool


class Critic:
    def assess(
        self,
        *,
        claim: str,
        support: int,
        denominator: int,
        negative_share: float | None,
        sample_quotes: list[dict],
    ) -> Finding:
        # Too little evidence, or no quote actually backing it -> not assertable.
        if support < MIN_SUPPORT or not sample_quotes:
            return Finding(claim, support, denominator, "insufficient", negative_share, sample_quotes[:3], False)

        ratio = support / denominator if denominator else 0.0
        if support >= SUFFICIENT_SUPPORT and ratio >= HIGH_CONFIDENCE_RATIO:
            confidence = "high"
        elif ratio >= MED_CONFIDENCE_RATIO:
            confidence = "medium"
        else:
            confidence = "low"
        return Finding(claim, support, denominator, confidence, negative_share, sample_quotes[:3], True)

    def assess_correlation(self, a: Finding, b: Finding, overlap: int) -> dict:
        asserted = a.accepted and b.accepted and overlap >= MIN_CORRELATION_OVERLAP
        return {
            "theme_a": a.claim,
            "theme_b": b.claim,
            "overlap": overlap,
            "asserted": asserted,
            "confidence": "medium" if asserted else "low",
        }
