"""Critic tests — sample/quote gating, denominator-scaled confidence, correlation sanity."""
from __future__ import annotations

from app.agent.critic import Critic

Q = [{"text": "it is broken", "rating": 1}]


def test_rejects_low_sample():
    f = Critic().assess(claim="t", support=1, denominator=100, negative_share=1.0, sample_quotes=Q)
    assert f.confidence == "insufficient" and f.accepted is False


def test_rejects_when_no_backing_quote():
    f = Critic().assess(claim="t", support=10, denominator=100, negative_share=0.5, sample_quotes=[])
    assert f.accepted is False


def test_accepts_strong_signal_high_confidence():
    f = Critic().assess(claim="t", support=10, denominator=100, negative_share=0.5, sample_quotes=Q)
    assert f.accepted is True and f.confidence == "high"


def test_confidence_scales_with_denominator():
    small = Critic().assess(claim="t", support=8, denominator=30, negative_share=0.5, sample_quotes=Q)
    large = Critic().assess(claim="t", support=8, denominator=3000, negative_share=0.5, sample_quotes=Q)
    assert small.confidence == "high"  # 8 of 30
    assert large.confidence == "low"  # 8 of 3,000 — same count, far weaker signal


def test_correlation_requires_overlap():
    c = Critic()
    a = c.assess(claim="a", support=10, denominator=100, negative_share=0.5, sample_quotes=Q)
    b = c.assess(claim="b", support=10, denominator=100, negative_share=0.5, sample_quotes=Q)
    assert c.assess_correlation(a, b, overlap=1)["asserted"] is False
    assert c.assess_correlation(a, b, overlap=5)["asserted"] is True
