"""Deterministic date normalisation to UTC (EC-X-01, EC-X-02, EC-X-05).

Returns (utc_datetime_or_None, invalid_flag):
  - missing date      -> (None, False)  : unknown, not invalid (EC-P1-15)
  - epoch-zero/before -> (None, True)   : invalid, excluded from timeframe (EC-X-02)
  - future (> now+skew)-> (None, True)  : invalid (clock/scraper anomaly)
  - otherwise         -> (utc_dt, False)

`now` is injected (single source of truth, EC-X-05) so the function is pure and
the cleaner stays reproducible for a fixed reference instant.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

EPOCH_CUTOFF = datetime(2008, 1, 1, tzinfo=timezone.utc)  # before mobile app stores
FUTURE_SKEW = timedelta(days=1)


def normalise_date(value, now: datetime) -> tuple[datetime | None, bool]:
    if value is None:
        return None, False
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None, True
    if not isinstance(value, datetime):
        return None, True
    dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    if dt < EPOCH_CUTOFF or dt > now + FUTURE_SKEW:
        return None, True
    return dt, False
