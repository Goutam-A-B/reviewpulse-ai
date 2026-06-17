"""Model-abstraction layer (PRD §6.5) — one swappable seam for every model.

No other code hard-codes a vendor. Three capabilities:
    reason()     -> Groq free API (Llama 3.x)       [wired in Phase 4]
    synthesize() -> Gemini 2.5 Flash free tier       [wired in Phase 5]
    embed()      -> bge-small-en-v1.5 via fastembed   [wired in Phase 2]

In Phase 0 the adapters exist and report configuration status, but their core
methods raise NotImplementedYet rather than returning fabricated output — a
stub must never silently fake a result (edge case EC-P0-03).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


class NotImplementedYet(NotImplementedError):
    """Typed sentinel: this adapter method is not wired until a later phase."""


@runtime_checkable
class Reasoner(Protocol):
    name: str

    def is_configured(self) -> bool: ...

    async def decide(self, prompt: str, options: list[str]) -> str: ...


@runtime_checkable
class Synthesizer(Protocol):
    name: str

    def is_configured(self) -> bool: ...

    async def synthesize(self, findings: dict) -> dict: ...


@runtime_checkable
class Embedder(Protocol):
    name: str
    dim: int

    def is_configured(self) -> bool: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...
