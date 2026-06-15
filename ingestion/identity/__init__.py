from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class IdentityResolver:
    def __init__(self, db_session: Any) -> None:
        self._db = db_session

    async def resolve(
        self,
        source: str,
        external_id: str,
        symbol: str | None = None,
    ) -> str | None:
        row = await self._db.fetchrow(
            """
            SELECT i.id FROM instruments i
            JOIN instrument_external_ids ie ON ie.instrument_id = i.id
            WHERE ie.source = $1 AND ie.external_id = $2
            LIMIT 1
            """,
            source,
            external_id,
        )
        if row:
            return str(row["id"])

        if symbol:
            row = await self._db.fetchrow(
                """
                SELECT i.id FROM instruments i
                JOIN symbol_aliases sa ON sa.instrument_id = i.id
                WHERE sa.symbol = $1
                LIMIT 1
                """,
                symbol,
            )
            if row:
                return str(row["id"])

            row = await self._db.fetchrow(
                "SELECT id FROM instruments WHERE symbol = $1 LIMIT 1",
                symbol,
            )
            if row:
                return str(row["id"])
        return None

    async def resolve_or_create(
        self,
        source: str,
        external_id: str,
        symbol: str | None = None,
        name: str | None = None,
        instrument_type: str | None = None,
    ) -> str:
        existing = await self.resolve(source, external_id, symbol)
        if existing:
            return existing

        new_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        await self._db.execute(
            """
            INSERT INTO instruments (id, symbol, name, instrument_type, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $5)
            ON CONFLICT DO NOTHING
            """,
            new_id,
            symbol,
            name,
            instrument_type or "stock",
            now,
        )

        await self._db.execute(
            """
            INSERT INTO instrument_external_ids (instrument_id, source, external_id, created_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT DO NOTHING
            """,
            new_id,
            source,
            external_id,
            now,
        )
        return new_id
