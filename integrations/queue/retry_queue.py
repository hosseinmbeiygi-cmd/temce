from __future__ import annotations

import asyncio

from core.logging import get_logger
from integrations.queue.broker import Broker, Message

logger = get_logger(__name__)


class RetryQueue:
    """
    Retry queue with exponential backoff.

    Fixes two pre-existing defects:
      1. The computed backoff delay was never actually applied — messages
         were published to the retry queue instantly.
      2. Retry counting was keyed by the *new* message id of each retry
         attempt, so the counter reset on every cycle and the max-retry
         bound was never enforced.
    """

    def __init__(self, broker: Broker, max_retries: int = 3, base_delay: float = 5.0, queue_name: str = "retry"):
        self._broker = broker
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._queue_name = queue_name
        self._retry_counts: dict[str, int] = {}

    async def schedule(self, message: Message, delay: float | None = None) -> None:
        original_id = message.message_id
        retry_count = self._retry_counts.get(original_id, 0) + 1
        self._retry_counts[original_id] = retry_count
        if retry_count > self._max_retries:
            logger.warning("Message %s exceeded max retries (%d)", original_id, self._max_retries)
            self._retry_counts.pop(original_id, None)
            return
        wait = delay if delay is not None else self._base_delay * (2 ** (retry_count - 1))
        retry_msg = Message(
            body={
                "original": message.body,
                "retry_count": retry_count,
                "original_message_id": original_id,
            },
            routing_key=self._queue_name,
            headers={
                "x-retry-count": str(retry_count),
                "x-delay-seconds": str(wait),
                "x-original-routing-key": message.routing_key,
            },
        )
        await self._broker.publish(self._queue_name, retry_msg)
        logger.info("Message %s scheduled for retry %d in %.1fs", original_id, retry_count, wait)

    async def process_retries(self, handler: callable) -> None:
        async def retry_handler(msg: Message) -> None:
            body = msg.body
            if not isinstance(body, dict) or "original" not in body:
                logger.warning("Ignoring malformed retry message %s", msg.message_id)
                return
            original_body = body["original"]
            retry_count = int(body.get("retry_count", 1))
            original_id = str(body.get("original_message_id", msg.message_id))
            original_routing_key = msg.headers.get("x-original-routing-key", "")

            # Apply the advertised backoff delay before re-running the handler.
            try:
                delay = float(msg.headers.get("x-delay-seconds", 0))
            except (TypeError, ValueError):
                delay = 0.0
            if delay > 0:
                await asyncio.sleep(delay)

            original_msg = Message(
                body=original_body,
                message_id=original_id,
                routing_key=original_routing_key,
            )
            try:
                await handler(original_msg)
                self._retry_counts.pop(original_id, None)
            except Exception as e:
                logger.error("Retry %d failed for message: %s", retry_count, e)
                if retry_count < self._max_retries:
                    await self.schedule(original_msg)
                else:
                    self._retry_counts.pop(original_id, None)

        await self._broker.consume(self._queue_name, retry_handler)

    def reset_count(self, message_id: str) -> None:
        self._retry_counts.pop(message_id, None)

    @property
    def queue_name(self) -> str:
        return self._queue_name
