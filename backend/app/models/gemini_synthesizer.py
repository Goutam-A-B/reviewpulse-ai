"""The single synthesis call on Gemini 2.5 Flash (free tier). Wired in Phase 5.

Exactly one call per report (PRD §6.2). Takes Critic-approved findings and returns
structured JSON (narrative + recommendations + priority rationale). It is instructed
to use ONLY the provided findings; the caller post-validates the output so an
unsupported quote/stat can't reach the user (EC-P5-03). Temperature 0; the google-genai
SDK is imported lazily so the app boots without it.
"""
from __future__ import annotations

import asyncio
import json

from app.config import Settings

_SYSTEM = (
    "You are a senior product analyst. Using ONLY the verified findings provided, "
    "write a concise narrative and concrete, prioritised recommendations for a product team. "
    "Do NOT invent quotes, numbers, themes, or theme_ids that are not present in the findings. "
    "Reply ONLY as JSON of the form: "
    '{"narrative": string, '
    '"recommendations": [{"text": string, "theme_id": string}], '
    '"priority_rationale": [{"theme_id": string, "rationale": string}]}.'
)


class GeminiSynthesizer:
    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.model = settings.gemini_model

    def is_configured(self) -> bool:
        return bool(self._settings.gemini_api_key)

    async def synthesize(self, findings: dict) -> dict:
        return await asyncio.to_thread(self._call, findings)

    def _call(self, findings: dict) -> dict:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self._settings.gemini_api_key)
        prompt = f"{_SYSTEM}\n\nVERIFIED FINDINGS (JSON):\n{json.dumps(findings, default=str)}"
        resp = client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0, response_mime_type="application/json"
            ),
        )
        return json.loads(resp.text)
