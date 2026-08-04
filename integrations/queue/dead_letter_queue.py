from __future__ import annotations

from typing import Any

from core.logging import get_logger
from integrations.queue.broker import Broker, Message

logger = get_logger(__name__)


class DeadLetterQueue:
    """
    Dead-letter queue that retains the *full original message* so that
    ``replay`` can faithfully re-publish it (fixes a bug where only the
    message id was stored and replays always sent an empty body).
    """

    def __init__(self, broker: Broker, queue_name: str = "dead_letter"):
        self._broker = broker
        self._queue_name = queue_name
        self._messages: list[dict[str, Any]] = []

    async def send(self, message: Message, reason: str = "") -> None:
        dlq_msg = Message(
            body={
                "original_message_id": message.message_id,
                "original_routing_key": message.routing_key,
                "original_body": message.body,
                "reason": reason,
                "headers": message.headers,
            },
            routing_key=self._queue_name,
            headers={"x-dead-letter": "true", "x-reason": reason},
        )
        await self._broker.publish(self._queue_name, dlq_msg)
        self._messages.append(
            {
                "message_id": message.message_id,
                "reason": reason,
                "original_body": message.body,
                "original_routing_key": message.routing_key,
                "original_headers": message.headers,
            }
        )
        logger.warning("Message %s sent to DLQ: %s", message.message_id, reason)

    async def list_messages(self) -> list[dict[str, Any]]:
        return list(self._messages)

    async def replay(self, message_id: str, target_queue: str) -> bool:
        """Replay a dead-lettered message to ``target_queue``.

        The message is re-published with its original body and headers; the
        delivery destination is always the explicitly requested
        ``target_queue`` (the original routing key is kept in the DLQ entry
        for reference).
        """
        for entry in self._messages:
            if entry["message_id"] == message_id:
                original = entry.get("original_body")
                headers = dict(entry.get("original_headers") or {})
                msg = Message(body=original, routing_key=target_queue, headers=headers)
                await self._broker.publish(target_queue, msg)
                self._messages.remove(entry)
                logger.info(
                    "Replayed message %s to %s (originally %s)",
                    message_id,
                    target_queue,
                    entry.get("original_routing_key") or "?",
                )
                return True
        return False

    async def purge(self) -> int:
        count = len(self._messages)
        self._messages.clear()
        return count

    @property
    def queue_name(self) -> str:
        return self._queue_name

    @property
    def count(self) -> int:
        return len(self._messages)
