"""Deterministic, conservative spam heuristics (EC-P1-10).

Flags obvious junk (long single-character runs, near-total token repetition) so
it can be excluded from sentiment/themes later, while logged. Deliberately
under-flags to avoid discarding genuine short reviews. Empty text (star-only) is
never spam — it is simply non-analysable (EC-P1-05).
"""
from __future__ import annotations

import re

_REPEAT_CHAR = re.compile(r"(.)\1{9,}")  # same character 10+ times in a row


def is_spam(text_clean: str) -> bool:
    t = text_clean.strip()
    if not t:
        return False
    if _REPEAT_CHAR.search(t):
        return True
    tokens = t.lower().split()
    if len(tokens) >= 4 and len(set(tokens)) / len(tokens) <= 0.25:
        return True
    return False
