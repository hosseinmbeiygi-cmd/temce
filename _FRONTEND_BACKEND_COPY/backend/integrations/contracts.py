from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class NotificationSender(ABC):
    @abstractmethod
    async def send(self, message: Any) -> None: ...


class ObjectStorageClient(ABC):
    @abstractmethod
    async def upload(self, key: str, data: bytes) -> str: ...

    @abstractmethod
    async def download(self, key: str) -> bytes: ...


class QueueClient(ABC):
    @abstractmethod
    async def publish(self, message: Any) -> None: ...

    @abstractmethod
    async def consume(self, callback: Any) -> None: ...


class CacheClient(ABC):
    @abstractmethod
    async def get(self, key: str) -> Any | None: ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 300) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...
