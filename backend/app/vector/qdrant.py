"""Qdrant client factory + ping.

One place to construct the client so cloud (free tier) and embedded local mode are
interchangeable: set QDRANT_LOCAL_PATH to run Qdrant embedded (no server, no signup);
otherwise connect to QDRANT_URL. The client is cached per target and reused for the
process lifetime — embedded mode locks its path, so a fresh client per call would
conflict, and cloud benefits from connection reuse too.
"""
from __future__ import annotations

from app.config import Settings

_clients: dict[str, object] = {}


def make_async_client(settings: Settings):
    key = settings.qdrant_local_path or settings.qdrant_url or ":none:"
    client = _clients.get(key)
    if client is None:
        from qdrant_client import AsyncQdrantClient

        if settings.qdrant_local_path:
            client = AsyncQdrantClient(path=settings.qdrant_local_path)
        else:
            client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
        _clients[key] = client
    return client


# Backwards-compatible alias.
get_client = make_async_client


async def ping(settings: Settings) -> dict:
    client = make_async_client(settings)
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]
    return {"collections": names, "target_present": settings.qdrant_collection in names}
