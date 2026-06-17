"""Sentiment Classifier — VADER (lexicon-based, deterministic, free, tiny).

Same review always yields the same label (PRD §3, EC-X-06). VADER is a sensible
free/light default that fits a constrained host; it can be swapped for an ONNX
transformer behind this same interface without touching callers. Per-review labels
are noisy on sarcasm/negation (EC-P2-04) — that is surfaced later as aggregate
confidence, never as per-review ground truth.
"""
from __future__ import annotations

from functools import lru_cache

POSITIVE = "positive"
NEUTRAL = "neutral"
NEGATIVE = "negative"

# Standard VADER decision thresholds on the compound score.
_POS_THRESHOLD = 0.05
_NEG_THRESHOLD = -0.05


@lru_cache(maxsize=1)
def _analyzer():
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    return SentimentIntensityAnalyzer()


def _label_for(compound: float) -> str:
    if compound >= _POS_THRESHOLD:
        return POSITIVE
    if compound <= _NEG_THRESHOLD:
        return NEGATIVE
    return NEUTRAL


def classify(text: str) -> str:
    if not text or not text.strip():
        return NEUTRAL
    return _label_for(_analyzer().polarity_scores(text)["compound"])


def classify_many(texts: list[str]) -> list[str]:
    analyzer = _analyzer()
    out: list[str] = []
    for t in texts:
        compound = analyzer.polarity_scores(t)["compound"] if t and t.strip() else 0.0
        out.append(_label_for(compound))
    return out
