"""Create the Qdrant collection with payload indexes (Phase 0).

Filtering by date/rating must happen INSIDE Qdrant on indexed payload fields
(PRD §11.1, EC-P0-02), never post-filtered in Python. Run once after setting
QDRANT_URL / QDRANT_API_KEY in backend/.env:

    python -m scripts.bootstrap_qdrant     # from the backend/ directory
"""
from __future__ import annotations

import asyncio

from app.config import get_settings


async def main() -> None:
    from qdrant_client.models import Distance, PayloadSchemaType, VectorParams

    from app.vector.qdrant import make_async_client

    s = get_settings()
    if not (s.qdrant_url or s.qdrant_local_path):
        raise SystemExit("Set QDRANT_URL (cloud) or QDRANT_LOCAL_PATH (embedded) in backend/.env first.")

    client = make_async_client(s)
    try:
        existing = [c.name for c in (await client.get_collections()).collections]
        if s.qdrant_collection in existing:
            print(f"Collection '{s.qdrant_collection}' already exists — leaving as is.")
        else:
            await client.create_collection(
                collection_name=s.qdrant_collection,
                vectors_config=VectorParams(size=s.embed_dim, distance=Distance.COSINE),
            )
            print(f"Created collection '{s.qdrant_collection}' (dim={s.embed_dim}, cosine).")

        for field, schema in (
            ("review_date", PayloadSchemaType.DATETIME),
            ("rating", PayloadSchemaType.INTEGER),
            ("app_id", PayloadSchemaType.KEYWORD),
            ("platform", PayloadSchemaType.KEYWORD),
            ("theme_id", PayloadSchemaType.KEYWORD),
        ):
            try:
                await client.create_payload_index(
                    s.qdrant_collection, field_name=field, field_schema=schema
                )
                print(f"  indexed payload field: {field}")
            except Exception as exc:  # noqa: BLE001 - index may already exist
                print(f"  payload index {field}: {type(exc).__name__} (may already exist)")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
