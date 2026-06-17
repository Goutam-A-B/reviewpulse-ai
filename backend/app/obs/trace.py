"""Best-effort observability hook (EC-P7-01).

emit() forwards an event to LangSmith only if a key is configured and the SDK is
present. It catches everything: a tracing/transport failure must never block or
fail a report. With no key it is a no-op.
"""
from __future__ import annotations

from app.config import get_settings


def emit(event: str, payload: dict) -> None:
    try:
        settings = get_settings()
        if not settings.langsmith_api_key:
            return
        from langsmith import Client  # type: ignore

        Client(api_key=settings.langsmith_api_key).create_run(
            name=event, run_type="chain", inputs=payload, outputs={}
        )
    except Exception:  # noqa: BLE001 - observability is never allowed to break the request
        return
