from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ACTION_CREATE = "create"
ACTION_READ = "read"
ACTION_UPDATE = "update"
ACTION_DELETE = "delete"
ACTION_LOGIN = "login"
ACTION_LOGOUT = "logout"
ACTION_EXPORT = "export"
ACTION_IMPORT = "import"
ACTION_EXECUTE = "execute"
ACTION_APPROVE = "approve"
ACTION_REJECT = "reject"


@dataclass
class AuditAction:
    name: str
    category: str = ""
    description: str = ""
    severity: str = "info"
    requires_reason: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
