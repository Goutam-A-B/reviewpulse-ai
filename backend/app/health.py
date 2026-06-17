"""Health checks for every dependency (Phase 0 exit criterion).

Each check is defensive: a missing credential is `not_configured` (expected on a
fresh checkout), a missing library or a live failure is `error`. The overall
status is `ok` unless something is in `error`, so a credential-less checkout is
healthy-but-unconfigured rather than failing.
"""
from __future__ import annotations

import asyncio

from app.config import Settings
from app.models import build_embedder, build_reasoner, build_synthesizer

OK = "ok"
NOT_CONFIGURED = "not_configured"
STUB = "stub"
ERROR = "error"


async def check_database(settings: Settings) -> dict:
    if not settings.database_url:
        return {"name": "database", "status": NOT_CONFIGURED, "detail": "DATABASE_URL not set"}
    try:
        from app.db.session import ping

        await ping(settings)
        return {"name": "database", "status": OK, "detail": "SELECT 1 ok"}
    except Exception as exc:  # noqa: BLE001 - report any failure honestly
        return {"name": "database", "status": ERROR, "detail": f"{type(exc).__name__}: {exc}"}


async def check_qdrant(settings: Settings) -> dict:
    if not (settings.qdrant_url or settings.qdrant_local_path):
        return {"name": "qdrant", "status": NOT_CONFIGURED, "detail": "QDRANT_URL / QDRANT_LOCAL_PATH not set"}
    try:
        from app.vector.qdrant import ping

        info = await ping(settings)
        detail = (
            f"collections={info['collections']}; "
            f"target '{settings.qdrant_collection}' present={info['target_present']}"
        )
        return {"name": "qdrant", "status": OK, "detail": detail}
    except Exception as exc:  # noqa: BLE001
        return {"name": "qdrant", "status": ERROR, "detail": f"{type(exc).__name__}: {exc}"}


def check_models(settings: Settings) -> list[dict]:
    out: list[dict] = []
    for adapter, phase in (
        (build_reasoner(settings), "P4"),
        (build_synthesizer(settings), "P5"),
        (build_embedder(settings), "P2"),
    ):
        out.append(
            {
                "name": adapter.name,
                "status": STUB,
                "configured": adapter.is_configured(),
                "detail": f"adapter present; wired in {phase}",
            }
        )
    return out


async def health_report(settings: Settings) -> dict:
    db, qdrant = await asyncio.gather(check_database(settings), check_qdrant(settings))
    deps = [db, qdrant, *check_models(settings)]
    overall = OK if all(d.get("status") != ERROR for d in deps) else "degraded"
    return {"status": overall, "phase": "0", "dependencies": deps}
