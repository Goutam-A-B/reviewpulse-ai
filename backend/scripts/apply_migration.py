"""Apply migrations/001_init.sql to the configured Postgres (Supabase).

    cd backend && python -m scripts.apply_migration
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from app.config import get_settings


async def main() -> None:
    from app.db.session import get_engine

    s = get_settings()
    if not s.database_url:
        raise SystemExit("DATABASE_URL not set in backend/.env")

    sql_path = Path(__file__).resolve().parent.parent / "migrations" / "001_init.sql"
    statements = [stmt.strip() for stmt in sql_path.read_text(encoding="utf-8").split(";") if stmt.strip()]

    engine = get_engine(s)
    async with engine.begin() as conn:
        for stmt in statements:
            await conn.exec_driver_sql(stmt)
    print(f"Applied {len(statements)} statements from 001_init.sql.")


if __name__ == "__main__":
    asyncio.run(main())
