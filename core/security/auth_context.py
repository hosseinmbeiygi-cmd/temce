from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class AuthContext:
    user_id: str = ""
    username: str = ""
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    api_key: str = ""
    token: str = ""
    authenticated: bool = False
    authenticated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_ip: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def has_any_permission(self, *permissions: str) -> bool:
        return any(p in self.permissions for p in permissions)

    def has_all_permissions(self, *permissions: str) -> bool:
        return all(p in self.permissions for p in permissions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "roles": list(self.roles),
            "permissions": list(self.permissions),
            "authenticated": self.authenticated,
            "authenticated_at": self.authenticated_at.isoformat(),
            "source_ip": self.source_ip,
        }
