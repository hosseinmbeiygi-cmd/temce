from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class NotificationMessage:
    channel: str
    subject: str
    body: str
    recipients: list[str] = field(default_factory=list)
    priority: str = "normal"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookPayload:
    url: str
    event: str
    data: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class StorageObjectMeta:
    key: str
    size_bytes: int = 0
    content_type: str = ""
    uploaded_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class QueueMessage:
    id: str
    body: dict[str, Any]
    priority: int = 0
    delay_seconds: int = 0
