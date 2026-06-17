"""Decision-schema validation (EC-P4-03) — free-form output never drives control flow."""
from __future__ import annotations

from app.agent.decisions import Action, parse_decision


def test_valid_decision():
    d = parse_decision({"action": "broaden", "query": "login", "reason": "x"})
    assert d.action == Action.BROADEN and d.query == "login"


def test_invalid_action_returns_none():
    assert parse_decision({"action": "delete_database"}) is None


def test_non_dict_returns_none():
    assert parse_decision("stop") is None
    assert parse_decision(None) is None


def test_missing_action_returns_none():
    assert parse_decision({"query": "x"}) is None


def test_rating_max_out_of_bounds_dropped():
    assert parse_decision({"action": "narrow", "rating_max": 9}).rating_max is None
    assert parse_decision({"action": "narrow", "rating_max": 2}).rating_max == 2
