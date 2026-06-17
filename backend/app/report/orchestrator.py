"""Orchestration layer — control-flow, NOT an agent (PRD §7).

decide_route is a pure function of (cache state, data_version, has_data), so its
behaviour is an exhaustively-testable truth table (EC-P5-13). SingleFlight dedups
concurrent cold-start work (EC-P5-08). ReportCache keys on data_version and only
stores complete reports, so a degraded report is never served as canonical (EC-P5-07/09).
"""
from __future__ import annotations

import asyncio
import hashlib


def decide_route(*, in_cache: bool, cache_version: str | None, current_version: str, has_data: bool) -> str:
    if in_cache and cache_version == current_version:
        return "serve_cache"
    if has_data:
        return "build_warm"
    return "cold_start"


class SingleFlight:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def lock(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock


class ReportCache:
    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    @staticmethod
    def key(app_id: str, start, end, data_version: str) -> str:
        return hashlib.sha256(f"{app_id}|{start}|{end}|{data_version}".encode("utf-8")).hexdigest()

    def get(self, key: str) -> dict | None:
        return self._store.get(key)

    def put(self, key: str, report: dict) -> None:
        # Only a complete report is cacheable; a degraded one is re-attempted (EC-P5-07).
        if report.get("narrative_status") == "ok":
            self._store[key] = report
