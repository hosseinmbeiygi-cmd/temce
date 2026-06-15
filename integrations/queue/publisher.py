from __future__ import annotations

from typing import Any

from core.logging import get_logger
from integrations.queue.broker import Broker, Message

logger = get_logger(__name__)


class Publisher:
    def __init__(self, broker: Broker):
        self._broker = broker

    async def publish(self, routing_key: str, body: Any, headers: dict[str, str] | None = None) -> str:
        msg = Message(body=body, routing_key=routing_key, headers=headers)
        await self._broker.publish(routing_key, msg)
        logger.debug("Published message %s to %s", msg.message_id, routing_key)
        return msg.message_id

    async def publish_json(self, routing_key: str, data: dict[str, Any]) -> str:
        return await self.publish(routing_key, data, headers={"content-type": "application/json"})

    async def publish_event(self, routing_key: str, event_type: str, data: dict[str, Any]) -> str:
        payload = {"event_type": event_type, "data": data}
        return await self.publish(
            routing_key, payload, headers={"content-type": "application/json", "event_type": event_type}
        )
