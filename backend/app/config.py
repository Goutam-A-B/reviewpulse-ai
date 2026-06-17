"""Typed settings — the single place secrets/config are read (EC-P0-04).

All values come from environment / backend/.env. Defaults are safe for a fresh
checkout with no credentials: the app still boots and /health reports each
dependency as `not_configured` rather than crashing.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute path to backend/.env so config loads regardless of the working directory.
_ENV_FILE = str(Path(__file__).resolve().parent.parent / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    app_env: str = "dev"

    # --- Postgres (Supabase free tier) ---
    database_url: str = ""

    # --- Qdrant (free tier cloud, or embedded local) ---
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "review_vectors"
    # If set, run Qdrant embedded at this local path (no server, no signup).
    qdrant_local_path: str = ""

    # --- Reasoning tier: Groq free API (Llama 3.x) — agent loop + Critic [P4] ---
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    # --- Synthesis: Gemini 2.5 Flash free tier — 1 call/report [P5] ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # --- Embeddings: bge-small via fastembed (ONNX, local, no key) [P2] ---
    embed_model: str = "BAAI/bge-small-en-v1.5"
    embed_dim: int = 384

    # --- Hard premium-call ceiling per report (PRD §6.5) ---
    premium_call_ceiling: int = 1
    # Deep Analysis mode: a higher, still-bounded ceiling the user opts into (EC-P7-05).
    deep_premium_ceiling: int = 3

    # --- Observability (Phase 7): optional, best-effort, never blocks ---
    langsmith_api_key: str = ""

    # --- CORS ---
    frontend_origin: str = "http://localhost:3000"

    @property
    def async_database_url(self) -> str:
        """Rewrite a plain Postgres URL to the asyncpg driver scheme."""
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
