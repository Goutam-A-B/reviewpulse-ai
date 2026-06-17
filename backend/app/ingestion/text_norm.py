"""Deterministic text normalisation (EC-X-15, EC-X-13).

NFKC-normalise, strip zero-width and bidi-override characters, remove HTML/markup
and other control characters, collapse whitespace, and apply a safety length cap.
Full real reviews are preserved; only pathological input is bounded (the embed-time
truncation in Phase 2 is a separate concern, EC-P1-14).
"""
from __future__ import annotations

import re
import unicodedata

# Zero-width characters and BOM.
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)
# Bidi embedding/override/isolate controls (e.g. RLO) used to disguise text.
_BIDI = {cp: None for cp in range(0x202A, 0x202F)}
_BIDI.update({cp: None for cp in range(0x2066, 0x206A)})

_HTML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

MAX_LEN = 20_000  # safety ceiling against abuse; normal long reviews are well under this


def normalise(text: str | None) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = t.translate(_ZERO_WIDTH).translate(_BIDI)
    t = _HTML_TAG.sub(" ", t)
    # Preserve word boundaries, then drop remaining control characters.
    t = t.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    t = "".join(ch for ch in t if not unicodedata.category(ch).startswith("C"))
    t = _WS.sub(" ", t).strip()
    return t[:MAX_LEN]
