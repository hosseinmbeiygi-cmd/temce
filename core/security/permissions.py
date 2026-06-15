from __future__ import annotations


class Permission:
    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Permission):
            return self.name == other.name
        if isinstance(other, str):
            return self.name == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.name)


class Role:
    def __init__(self, name: str, permissions: list[Permission] | None = None) -> None:
        self.name = name
        self._permissions = set(permissions or [])

    def add_permission(self, permission: Permission) -> None:
        self._permissions.add(permission)

    def remove_permission(self, permission: Permission) -> None:
        self._permissions.discard(permission)

    def has_permission(self, permission: str | Permission) -> bool:
        if isinstance(permission, str):
            return any(p.name == permission for p in self._permissions)
        return permission in self._permissions

    def permissions(self) -> list[str]:
        return [p.name for p in self._permissions]


# Pre-defined permissions
PERM_READ_QUOTES = Permission("read:quotes", "Read real-time and historical quotes")
PERM_READ_INSTRUMENTS = Permission("read:instruments", "Read instrument data")
PERM_READ_NEWS = Permission("read:news", "Read news")
PERM_READ_MACRO = Permission("read:macro", "Read macro data")
PERM_READ_SIGNALS = Permission("read:signals", "Read signals")
PERM_READ_RECOMMENDATIONS = Permission("read:recommendations", "Read recommendations")
PERM_READ_BACKTEST = Permission("read:backtest", "Read backtest results")
PERM_WRITE_BACKTEST = Permission("write:backtest", "Run backtests")
PERM_READ_ML = Permission("read:ml", "Read ML models and results")
PERM_WRITE_ML = Permission("write:ml", "Train and deploy ML models")
PERM_ADMIN = Permission("admin", "Full administrative access")
PERM_MANAGE_USERS = Permission("manage:users", "Manage users")
PERM_MANAGE_PROVIDERS = Permission("manage:providers", "Manage data providers")
PERM_VIEW_AUDIT = Permission("view:audit", "View audit logs")

# Pre-defined roles
ROLE_ADMIN = Role("admin", [PERM_ADMIN, PERM_MANAGE_USERS, PERM_MANAGE_PROVIDERS, PERM_VIEW_AUDIT])
ROLE_ANALYST = Role(
    "analyst",
    [
        PERM_READ_QUOTES,
        PERM_READ_INSTRUMENTS,
        PERM_READ_NEWS,
        PERM_READ_MACRO,
        PERM_READ_SIGNALS,
        PERM_READ_RECOMMENDATIONS,
        PERM_READ_BACKTEST,
        PERM_WRITE_BACKTEST,
    ],
)
ROLE_ML_ENGINEER = Role(
    "ml_engineer",
    [
        PERM_READ_ML,
        PERM_WRITE_ML,
        PERM_READ_QUOTES,
        PERM_READ_INSTRUMENTS,
    ],
)
ROLE_VIEWER = Role(
    "viewer",
    [
        PERM_READ_QUOTES,
        PERM_READ_INSTRUMENTS,
        PERM_READ_NEWS,
        PERM_READ_SIGNALS,
        PERM_READ_RECOMMENDATIONS,
    ],
)
