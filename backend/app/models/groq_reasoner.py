"""Agent + Critic reasoning on the Groq free tier (Llama 3.x). Wired in Phase 4.

Free, deployable, and a real LLM — so the plan-act-observe-judge-decide loop
stays genuinely agentic. The Groq client is imported lazily so the app boots
without the dependency installed during early phases.
"""
from __future__ import annotations

from app.config import Settings
from app.models.base import NotImplementedYet


class GroqReasoner:
    name = "groq"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.model = settings.groq_model

    def is_configured(self) -> bool:
        return bool(self._settings.groq_api_key)

    async def decide(self, prompt: str, options: list[str]) -> str:
        # Phase 4: call Groq at temperature 0, constrained to `options`
        # (the fixed action set), with structured-scoring fallback (EC-P4-11).
        raise NotImplementedYet("GroqReasoner.decide is wired in Phase 4")
