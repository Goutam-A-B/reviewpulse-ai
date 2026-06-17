"""Data Cleaner tests — the determinism gate (Phase 1 exit criterion) + edge cases."""
from __future__ import annotations

from datetime import datetime, timezone

from app.ingestion.cleaner import clean_batch
from app.ingestion.schemas import Platform, RawReview

NOW = datetime(2026, 6, 16, tzinfo=timezone.utc)


def _raw(rid, text=None, title=None, rating=5, date=None, platform=Platform.ANDROID):
    return RawReview(
        source_review_id=rid,
        platform=platform,
        text=text,
        title=title,
        rating=rating,
        review_date=date,
    )


def test_determinism_identical_output():
    raws = [
        _raw("a", "Great app, love the UI", date=datetime(2026, 6, 1, tzinfo=timezone.utc)),
        _raw("b", "Crashes on login", date=datetime(2026, 6, 2, tzinfo=timezone.utc)),
        _raw("c", "", rating=4, date=NOW),  # star-only
    ]
    # Same input + same `now` must produce byte-identical CleanedReview values.
    assert clean_batch(raws, NOW) == clean_batch(raws, NOW)


def test_pii_is_redacted():
    text = (
        "Email me at john.doe@example.com or call +1-415-555-1234, "
        "see http://evil.com/x my handle @johnny order 9876543210"
    )
    [c] = clean_batch([_raw("p", text, date=NOW)], NOW)
    for leak in ("example.com", "evil.com", "415", "9876543210", "john.doe@"):
        assert leak not in c.text_clean
    for token in ("[email]", "[url]", "[handle]", "[phone]"):
        assert token in c.text_clean


def test_unicode_and_markup_normalised():
    text = "G​o​o​d  <b>app</b>‮ reversed"
    [c] = clean_batch([_raw("u", text, date=NOW)], NOW)
    assert "​" not in c.text_clean
    assert "‮" not in c.text_clean
    assert "<b>" not in c.text_clean
    assert "Good app" in c.text_clean


def test_star_only_review_is_non_analysable_and_not_spam():
    [c] = clean_batch([_raw("s", "", rating=3, date=NOW)], NOW)
    assert c.text_clean == ""
    assert c.is_analysable is False
    assert c.is_spam is False


def test_star_only_reviews_not_deduped_against_each_other():
    raws = [_raw("s1", "", rating=5, date=NOW), _raw("s2", "", rating=1, date=NOW)]
    out = clean_batch(raws, NOW)
    assert all(c.is_duplicate is False for c in out)


def test_near_duplicate_text_flagged():
    raws = [
        _raw("d1", "Same exact text", date=datetime(2026, 6, 1, tzinfo=timezone.utc)),
        _raw("d2", "Same exact text", date=datetime(2026, 6, 2, tzinfo=timezone.utc)),
    ]
    by_id = {c.source_review_id: c for c in clean_batch(raws, NOW)}
    assert by_id["d1"].is_duplicate is False  # earlier kept
    assert by_id["d2"].is_duplicate is True


def test_exact_source_id_duplicate_flagged():
    raws = [_raw("x", "hello", date=NOW), _raw("x", "hello", date=NOW)]
    assert sum(c.is_duplicate for c in clean_batch(raws, NOW)) == 1


def test_invalid_and_missing_dates():
    fc, ec, mc = clean_batch(
        [
            _raw("f", "x", date=datetime(2030, 1, 1, tzinfo=timezone.utc)),  # future
            _raw("e", "y", date=datetime(1970, 1, 1, tzinfo=timezone.utc)),  # epoch
            _raw("m", "z", date=None),  # missing
        ],
        NOW,
    )
    assert fc.review_date is None and fc.invalid_date is True
    assert ec.review_date is None and ec.invalid_date is True
    assert mc.review_date is None and mc.invalid_date is False  # missing != invalid


def test_rating_validation_never_defaults():
    bad = clean_batch([_raw("r", "txt", rating=0, date=NOW)], NOW)[0]
    none = clean_batch([_raw("r2", "txt", rating=None, date=NOW)], NOW)[0]
    good = clean_batch([_raw("r3", "txt", rating=4, date=NOW)], NOW)[0]
    assert bad.rating is None
    assert none.rating is None
    assert good.rating == 4


def test_spam_flags_repetition():
    rep_char = clean_batch([_raw("c1", "s" + "o" * 12 + " good", date=NOW)], NOW)[0]
    rep_tok = clean_batch([_raw("c2", "good good good good good", date=NOW)], NOW)[0]
    normal = clean_batch([_raw("c3", "Genuinely useful and fast", date=NOW)], NOW)[0]
    assert rep_char.is_spam is True
    assert rep_tok.is_spam is True
    assert normal.is_spam is False
