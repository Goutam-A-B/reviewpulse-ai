"""The Data Cleaner — a deterministic transformation (PRD §3, Phase 1).

clean_batch() is pure given (raws, now): identical input yields identical output,
which is the Phase 1 exit-criteria gate. It applies, in order:
  1. text normalisation (text_norm)        - EC-X-13, EC-X-15
  2. PII redaction (pii)                    - EC-X-16, EC-X-17
  3. rating validation (never defaulted)    - EC-P1-15
  4. UTC date normalisation (dates)         - EC-X-01, EC-X-02
  5. analysability (empty-after-clean)      - EC-P1-05, EC-X-18
  6. conservative spam flag (spam)          - EC-P1-10
  7. deterministic dedup pass (dedup)       - EC-P1-09, EC-X-23

Nothing here depends on wall-clock time except via the injected `now`, and no
step uses randomness or input ordering, so re-runs are byte-identical.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.ingestion import dates, pii, spam, text_norm
from app.ingestion.dedup import text_fingerprint
from app.ingestion.schemas import CleanedReview, RawReview

_MIN_UTC = datetime.min.replace(tzinfo=timezone.utc)


def _valid_rating(rating) -> int | None:
    return rating if isinstance(rating, int) and 1 <= rating <= 5 else None


def clean_review(raw: RawReview, now: datetime) -> CleanedReview:
    text_clean = " ".join(pii.strip_pii(text_norm.normalise(raw.text)).split())
    title_clean = " ".join(pii.strip_pii(text_norm.normalise(raw.title)).split()) or None
    review_date, invalid = dates.normalise_date(raw.review_date, now)
    return CleanedReview(
        source_review_id=raw.source_review_id,
        platform=raw.platform,
        text_raw=raw.text,
        text_clean=text_clean,
        title_clean=title_clean,
        rating=_valid_rating(raw.rating),
        review_date=review_date,
        is_spam=spam.is_spam(text_clean),
        is_duplicate=False,  # decided in the batch pass below
        is_analysable=bool(text_clean),
        invalid_date=invalid,
    )


def clean_batch(raws: list[RawReview], now: datetime | None = None) -> list[CleanedReview]:
    now = now or datetime.now(timezone.utc)
    cleaned = [clean_review(r, now) for r in raws]

    # Deterministic order for the dedup decision: oldest first, ties by id;
    # None-dated last. The first occurrence is kept, later copies are duplicates.
    order = sorted(
        range(len(cleaned)),
        key=lambda i: (
            cleaned[i].review_date is None,
            cleaned[i].review_date or _MIN_UTC,
            cleaned[i].source_review_id,
        ),
    )

    seen_ids: set[str] = set()
    seen_fingerprints: set[str] = set()
    for i in order:
        c = cleaned[i]
        duplicate = False
        if c.source_review_id in seen_ids:
            duplicate = True
        else:
            seen_ids.add(c.source_review_id)
        # Only dedup by text when there IS text — star-only reviews (empty text)
        # are distinct ratings, not duplicates of each other (EC-P1-05).
        if c.is_analysable:
            fp = text_fingerprint(c.text_clean)
            if fp in seen_fingerprints:
                duplicate = True
            else:
                seen_fingerprints.add(fp)
        c.is_duplicate = duplicate

    return cleaned
