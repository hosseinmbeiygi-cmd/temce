from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class AuditLogger:
    def __init__(self) -> None:
        self._enabled = True

    def log(
        self,
        action: str,
        entity: str,
        entity_id: str | None = None,
        user_id: str | None = None,
        changes: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self._enabled:
            return
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "action": action,
            "entity": entity,
            "entity_id": entity_id,
            "user_id": user_id,
            "changes": changes or {},
            "metadata": metadata or {},
        }
        logger.info("AUDIT: %s", json.dumps(record, ensure_ascii=False))

    def log_create(self, entity: str, entity_id: str, user_id: str | None = None, **kwargs: Any) -> None:
        self.log("CREATE", entity, entity_id, user_id, kwargs)

    def log_update(self, entity: str, entity_id: str, user_id: str | None = None, **kwargs: Any) -> None:
        self.log("UPDATE", entity, entity_id, user_id, kwargs)

    def log_delete(self, entity: str, entity_id: str, user_id: str | None = None, **kwargs: Any) -> None:
        self.log("DELETE", entity, entity_id, user_id, kwargs)

    def log_access(self, entity: str, entity_id: str, user_id: str | None = None, **kwargs: Any) -> None:
        self.log("ACCESS", entity, entity_id, user_id, kwargs)


audit_logger = AuditLogger()
