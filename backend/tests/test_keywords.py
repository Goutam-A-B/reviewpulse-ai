"""Keyword extractor tests — discriminative terms, filtering, determinism."""
from __future__ import annotations

from app.ingestion.enrichment.keywords import extract_keywords


def test_extracts_frequent_terms_and_filters_stopwords():
    texts = [
        "login fails every time login is broken",
        "the login screen crashes on login",
        "payment failed during checkout payment error",
        "cannot complete payment checkout",
        "great app love it",
    ]
    kws = extract_keywords(texts, app_name="MyApp", top_n=10)
    terms = [k["term"] for k in kws]
    assert "login" in terms
    assert "payment" in terms
    assert "the" not in terms  # stopword
    assert extract_keywords(texts, app_name="MyApp") == extract_keywords(texts, app_name="MyApp")


def test_app_name_is_filtered_out():
    texts = ["spotify is great spotify music", "love spotify and music", "music is the best app"]
    terms = [k["term"] for k in extract_keywords(texts, app_name="Spotify")]
    assert "spotify" not in terms
    assert "music" in terms
