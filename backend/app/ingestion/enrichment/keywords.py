"""Keyword Extractor — statistical, deterministic (PRD §3, EC-P2-10).

Counts discriminative terms across the corpus, filtering English stopwords, the
app's own name, and ubiquitous terms (max_df), so trending keywords are meaningful
rather than frequent-but-empty. Deterministic ordering (count desc, then term asc).
"""
from __future__ import annotations

import re


def app_name_tokens(app_name: str | None) -> set[str]:
    if not app_name:
        return set()
    return {t for t in re.findall(r"[a-z0-9]+", app_name.lower()) if len(t) > 1}


def extract_keywords(texts: list[str], app_name: str | None = None, top_n: int = 20) -> list[dict]:
    docs = [t for t in texts if t and t.strip()]
    if not docs:
        return []

    from sklearn.feature_extraction.text import CountVectorizer

    stop = app_name_tokens(app_name)
    max_df = 1.0 if len(docs) < 5 else 0.6
    try:
        vec = CountVectorizer(
            stop_words="english",
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b",
            max_df=max_df,
        )
        matrix = vec.fit_transform(docs)
    except ValueError:
        return []  # empty vocabulary after filtering

    counts = matrix.sum(axis=0).A1
    terms = vec.get_feature_names_out()
    pairs = [(term, int(c)) for term, c in zip(terms, counts) if term not in stop]
    pairs.sort(key=lambda p: (-p[1], p[0]))
    return [{"term": t, "frequency": c} for t, c in pairs[:top_n]]
