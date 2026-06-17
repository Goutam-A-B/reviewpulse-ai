"""Factories for the model-abstraction layer adapters."""
from __future__ import annotations

from app.config import Settings
from app.models.fastembed_embedder import FastEmbedEmbedder
from app.models.gemini_synthesizer import GeminiSynthesizer
from app.models.groq_reasoner import GroqReasoner


def build_reasoner(settings: Settings) -> GroqReasoner:
    return GroqReasoner(settings)


def build_synthesizer(settings: Settings) -> GeminiSynthesizer:
    return GeminiSynthesizer(settings)


def build_embedder(settings: Settings) -> FastEmbedEmbedder:
    return FastEmbedEmbedder(settings)
