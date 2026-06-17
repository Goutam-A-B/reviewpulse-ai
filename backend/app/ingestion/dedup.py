"""Deterministic near-duplicate fingerprint (EC-P1-09).

A stable hash of the lowercased, whitespace-collapsed cleaned text. Two reviews
with different store ids but identical text (re-posts, pagination overlap) share
a fingerprint and the later one is marked a duplicate by the cleaner's batch pass.
"""
from __future__ import annotations

import hashlib


def text_fingerprint(text_clean: str) -> str:
    norm = " ".join(text_clean.lower().split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()
