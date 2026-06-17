"""The constrained action set the agent chooses from (PRD §6.3).

Decisions are structured choices, not free text — this is what keeps the agent's
behaviour predictable and auditable, and it means injected review text can never
become an instruction that changes control flow (EC-P4-03, EC-P4-12).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Action(str, Enum):
    BROADEN = "broaden"
    NARROW = "narrow"
    REFORMULATE = "reformulate"
    INVESTIGATE_CORRELATED = "investigate_correlated"
    STOP = "stop"


VALID_ACTIONS = {a.value for a in Action}


@dataclass
class Decision:
    action: Action
    query: str | None = None
    rating_max: int | None = None
    reason: str = ""


def parse_decision(raw) -> Decision | None:
    """Validate an LLM-produced decision against the schema. Returns None if invalid
    so the caller can fall back rather than trust free-form output (EC-P4-03)."""
    if not isinstance(raw, dict):
        return None
    action = raw.get("action")
    if action not in VALID_ACTIONS:
        return None
    query = raw.get("query")
    rating_max = raw.get("rating_max")
    reason = raw.get("reason", "")
    return Decision(
        action=Action(action),
        query=query if isinstance(query, str) else None,
        rating_max=rating_max if isinstance(rating_max, int) and 1 <= rating_max <= 5 else None,
        reason=reason if isinstance(reason, str) else "",
    )
