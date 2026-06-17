"""Deterministic PII redaction (EC-X-16, EC-X-17).

Pattern-based stripping of the high-frequency identifiers found in reviews:
emails, URLs, social handles, phone numbers, and long numeric IDs (order/account
numbers). Redaction runs at clean time, before anything is embedded or surfaced,
so a verbatim quote drawn from `text_clean` cannot leak PII.

Bias: when uncertain, redact (the phone/ID patterns may over-match a little —
acceptable, since under-claiming on privacy is the safe direction).

Known limitation: person names need NER, which is heavy and non-deterministic;
it is intentionally deferred. A pluggable name-redaction hook can be added later
without changing this interface.
"""
from __future__ import annotations

import re

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_URL = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_HANDLE = re.compile(r"(?<![A-Za-z0-9])@[A-Za-z0-9_]{2,}")
# 7+ digits possibly grouped by spaces/dashes/parens/plus -> phone-like.
_PHONE = re.compile(r"(?<!\d)\+?\d[\d\-\s().]{5,}\d(?!\d)")
# Bare run of 7+ digits -> order/account id.
_LONG_ID = re.compile(r"(?<!\d)\d{7,}(?!\d)")


def strip_pii(text: str) -> str:
    if not text:
        return ""
    t = _EMAIL.sub("[email]", text)
    t = _URL.sub("[url]", t)
    t = _HANDLE.sub("[handle]", t)
    t = _PHONE.sub("[phone]", t)
    t = _LONG_ID.sub("[id]", t)
    return t
