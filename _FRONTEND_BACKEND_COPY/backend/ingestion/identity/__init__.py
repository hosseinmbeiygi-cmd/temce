from __future__ import annotations

import hashlib
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
        """Resolve an external identity, creating it atomically when absent.

        The previous implementation returned a newly generated UUID even when
        another worker won either ``ON CONFLICT`` race.  That could return an
        ID which was never stored and could leave the external mapping attached
        to the wrong instrument.  The final lookup below always returns the ID
        that actually won the database constraints.
        """
        if not source or not external_id:
            raise ValueError("source and external_id are required")

        # Only an existing external mapping is a terminal match.  A symbol
        # match must still create the missing source/external mapping below.
        existing = await self.resolve(source, external_id)
        if existing:
            return existing

        # ``instruments.symbol`` is NOT NULL and UNIQUE in the live schema.
        # A stable source-qualified fallback keeps external-only records
        # creatable without inventing a random, non-repeatable display symbol.
        if symbol:
            instrument_symbol = symbol
        else:
            identity_hash = hashlib.sha256(f"{source}:{external_id}".encode()).hexdigest()[:32]
            instrument_symbol = f"{source[:17]}:{identity_hash}"
        new_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        instrument_row = await self._db.fetchrow(
            """
            INSERT INTO instruments (id, symbol, name, instrument_type, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $5)
            ON CONFLICT (symbol) DO UPDATE SET updated_at = EXCLUDED.updated_at
            RETURNING id
            """,
            new_id,
            instrument_symbol,
            name,
            instrument_type or "stock",
            now,
        )
        instrument_id = str(instrument_row["id"] if instrument_row else new_id)

        await self._db.execute(
            """
            INSERT INTO instrument_external_ids (instrument_id, source, external_id, created_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (source, external_id) DO NOTHING
            """,
            instrument_id,
            source,
            external_id,
            now,
        )

        # If another worker inserted the mapping first, return its instrument.
        mapped = await self._db.fetchrow(
            """
            SELECT instrument_id
            FROM instrument_external_ids
            WHERE source = $1 AND external_id = $2
            """,
            source,
            external_id,
        )
        if not mapped:
            raise RuntimeError("instrument identity was not persisted")
        return str(mapped["instrument_id"])
