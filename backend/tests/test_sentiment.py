"""Sentiment classifier tests — deterministic labelling."""
from __future__ import annotations

from app.ingestion.enrichment import sentiment


def test_positive_negative_neutral():
    assert sentiment.classify("I love this app, it works great and is amazing!") == sentiment.POSITIVE
    assert sentiment.classify("Terrible, it crashes constantly and is the worst") == sentiment.NEGATIVE
    assert sentiment.classify("This is an application for phones") == sentiment.NEUTRAL


def test_deterministic():
    texts = ["great app", "awful buggy mess", "it exists"]
    assert sentiment.classify_many(texts) == sentiment.classify_many(texts)


def test_empty_is_neutral():
    assert sentiment.classify("") == sentiment.NEUTRAL
