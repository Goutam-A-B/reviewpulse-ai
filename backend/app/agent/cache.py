"""Decision-path cache (PRD §6.3) — an identical request replays the identical
investigation. The key includes data_version, so newly ingested reviews invalidate
the replay rather than serving a stale path (EC-P4-09).
"""
from __future__ import annotations

import hashlib


class DecisionPathCache:
    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    @staticmethod
    def key(app_id: str, topic: str, start, end, data_version: str) -> str:
        raw = f"{app_id}|{topic}|{start}|{end}|{data_version}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> dict | None:
        return self._store.get(key)

    def put(self, key: str, value: dict) -> None:
        self._store[key] = value
