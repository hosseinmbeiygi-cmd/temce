from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine
from typing import Any

from core.ids import new_id
from core.logging import get_logger

logger = get_logger(__name__)


class Message:
    def __init__(self, body: Any, message_id: str = "", routing_key: str = "", headers: dict[str, str] | None = None):
        self.message_id = message_id or new_id("msg")
        self.body = body
        self.routing_key = routing_key
        self.headers = headers or {}
        self.timestamp: float = 0.0
        self.delivery_tag: int = 0

    def serialize(self) -> str:
        return json.dumps(
            {"id": self.message_id, "body": self.body, "routing_key": self.routing_key, "headers": self.headers},
            ensure_ascii=False,
            default=str,
        )

    @classmethod
    def deserialize(cls, raw: str) -> Message:
        data = json.loads(raw)
        return cls(
            body=data["body"],
            message_id=data.get("id", new_id("msg")),
            routing_key=data.get("routing_key", ""),
            headers=data.get("headers", {}),
        )


class Broker:
    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}
        self._consumers: dict[str, list[Callable[[Message], Coroutine[Any, Any, None]]]] = {}
        self._running = False

    async def declare_queue(self, name: str, maxsize: int = 0) -> None:
        if name not in self._queues:
            self._queues[name] = asyncio.Queue(maxsize=maxsize)
            logger.info("Queue declared: %s", name)

    async def publish(self, routing_key: str, message: Message) -> None:
        if routing_key not in self._queues:
            await self.declare_queue(routing_key)
        message.routing_key = routing_key
        await self._queues[routing_key].put(message)

    async def consume(self, queue_name: str, callback: Callable[[Message], Coroutine[Any, Any, None]]) -> None:
        if queue_name not in self._consumers:
            self._consumers[queue_name] = []
        self._consumers[queue_name].append(callback)
        logger.info("Consumer registered for queue: %s", queue_name)

    async def start(self) -> None:
        self._running = True
        tasks = []
        for queue_name, handlers in self._consumers.items():
            task = asyncio.create_task(self._process_queue(queue_name, handlers))
            tasks.append(task)
        logger.info("Broker started with %d consumer groups", len(tasks))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_queue(self, queue_name: str, handlers: list[Callable]) -> None:
        q = self._queues.get(queue_name)
        if q is None:
            return
        while self._running:
            try:
                message = await asyncio.wait_for(q.get(), timeout=1.0)
                for handler in handlers:
                    try:
                        await handler(message)
                    except Exception as e:
                        logger.error("Handler failed for message %s: %s", message.message_id, e)
            except TimeoutError:
                continue

    async def stop(self) -> None:
        self._running = False

    async def queue_size(self, name: str) -> int:
        q = self._queues.get(name)
        return q.qsize() if q else 0
