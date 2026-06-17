"""Async Postgres engine (Supabase free tier). Lazy so the app boots without
SQLAlchemy/asyncpg installed and without credentials.
"""
from __future__ import annotations

from app.config import Settings

_engine = None


def get_engine(settings: Settings):
    global _engine
    if _engine is None:
        from sqlalchemy.ext.asyncio import create_async_engine

        _engine = create_async_engine(
            settings.async_database_url,
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=0,
            # Disable prepared-statement caching for compatibility with Supabase's
            # connection poolers (pgbouncer) — harmless on a direct/session connection.
            connect_args={"statement_cache_size": 0},
        )
    return _engine


async def ping(settings: Settings) -> None:
    """Raise if the database is unreachable."""
    from sqlalchemy import text

    engine = get_engine(settings)
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
