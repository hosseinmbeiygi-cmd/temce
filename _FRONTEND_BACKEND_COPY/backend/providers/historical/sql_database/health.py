from __future__ import annotations

from typing import Any

from core.constants import ProviderHealth
from core.logging import get_logger
from providers.historical.sql_database.connection import DatabaseConnection

logger = get_logger(__name__)


class SQLDatabaseHealth:
    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection

    async def check(self) -> dict[str, Any]:
        try:
            async with self.connection.session() as session:
                if session is None:
                    return {"status": ProviderHealth.DOWN, "message": "SQLAlchemy not installed"}
                await session.execute("SELECT 1")
                return {"status": ProviderHealth.HEALTHY, "message": "Database reachable"}
        except Exception as e:
            logger.error("Database health check failed: %s", e)
            return {"status": ProviderHealth.DOWN, "message": str(e)}
