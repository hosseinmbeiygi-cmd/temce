"""Role-Based Access Control (RBAC) for Iran Market Platform.

Roles (from highest to lowest privilege):
  admin   — Full access: manage users, data import, system config
  analyst — Read/write access: signals, backtests, ML training, portfolios
  user    — Read access: market data, news, watchlist
  viewer  — Read-only access: market overview, basic data (default)
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """User roles in the system."""

    ADMIN = "admin"
    ANALYST = "analyst"
    USER = "user"
    VIEWER = "viewer"


# Role hierarchy: each role inherits permissions from lower roles.
# Higher index = lower privilege.
ROLE_HIERARCHY: list[Role] = [Role.ADMIN, Role.ANALYST, Role.USER, Role.VIEWER]


def has_role(user_roles: list[str] | str, required_role: str | Role) -> bool:
    """Check if a user has at least the required role.

    Admin always has access to everything.
    """
    if isinstance(user_roles, str):
        user_roles = [r.strip() for r in user_roles.split(",") if r.strip()]

    # Admin bypass
    if Role.ADMIN in user_roles:
        return True

    # Get the index of the required role in the hierarchy
    try:
        required_idx = ROLE_HIERARCHY.index(Role(required_role))
    except ValueError:
        return False

    # User must have a role at least as privileged as the required role
    for role_str in user_roles:
        try:
            user_idx = ROLE_HIERARCHY.index(Role(role_str))
            if user_idx <= required_idx:
                return True
        except ValueError:
            continue

    return False


def has_any_role(user_roles: list[str] | str, roles: list[str | Role]) -> bool:
    """Check if user has any of the listed roles."""
    if isinstance(user_roles, str):
        user_roles = [r.strip() for r in user_roles.split(",") if r.strip()]

    if Role.ADMIN in user_roles:
        return True

    for role in roles:
        if isinstance(role, str):
            role = Role(role)
        if role in user_roles:
            return True

    return False
