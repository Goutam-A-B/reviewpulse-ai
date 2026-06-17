"""StructuredReasoner tests — deterministic stop/continue logic."""
from __future__ import annotations

from app.agent.decisions import Action
from app.agent.reasoner import StructuredReasoner


def _ctx(support, iteration, history):
    return {"topic": "t", "query": "t", "support": support, "denominator": 100,
            "iteration": iteration, "history": history, "sample_quotes": []}


def test_stops_on_sufficient_evidence():
    assert StructuredReasoner().next_action(_ctx(9, 0, [9])).action == Action.STOP


def test_reformulates_on_weak_first_pass():
    assert StructuredReasoner().next_action(_ctx(0, 0, [0])).action == Action.REFORMULATE


def test_broadens_on_partial_signal():
    assert StructuredReasoner().next_action(_ctx(4, 0, [4])).action == Action.BROADEN


def test_stops_on_no_improvement():
    assert StructuredReasoner().next_action(_ctx(4, 1, [4, 4])).action == Action.STOP
