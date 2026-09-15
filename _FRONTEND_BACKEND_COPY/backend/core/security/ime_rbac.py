"""IME-specific RBAC + Segregation of Duties (سند v5.0 §14.2).

The four operational roles per سند §14.2:
  - «مشاهده‌گر» (viewer)       — only see signals
  - «معامله‌گر» (trader)       — approve trade cards
  - «کارشناس کمّی» (quant)     — change model parameters
  - «مدیر» (admin)             — change risk caps, kill switch

سند §14.2: «هیچ نقشی به‌تنهایی نباید بتواند هم پارامتر مدل را تغییر دهد
و هم سقف ریسک را — تفکیک وظایف (Segregation of Duties) الزامی است».

This module defines the four roles, the permission grants, the
segregation matrix, and the dual-approval helper consumed by the API
layer (apps/api/endpoints/system.py) and the kill switch revival
workflow (services/kill_switch.py).
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum


class IMERole(str, Enum):
    """The four operational roles from سند §14.2."""

    VIEWER = "viewer"
    TRADER = "trader"
    QUANT = "quant"
    ADMIN = "admin"


# Allowed action categories per role
ROLE_PERMISSIONS: dict[IMERole, frozenset[str]] = {
    IMERole.VIEWER: frozenset(
        {
            "signal:read",
            "trade_card:read",
            "model:read",
            "risk:read",
        }
    ),
    IMERole.TRADER: frozenset(
        {
            "signal:read",
            "trade_card:read",
            "trade_card:approve",
            "trade_card:reject",
            "execution:read",
        }
    ),
    IMERole.QUANT: frozenset(
        {
            "signal:read",
            "model:read",
            "model:write",
            "model:calibrate",
            "backtest:read",
            "backtest:write",
        }
    ),
    IMERole.ADMIN: frozenset(
        {
            "signal:read",
            "risk:read",
            "risk:write",
            "kill_switch:activate",
            "kill_switch:revive",
            "policy:write",
            "config:write",
        }
    ),
}


def role_has_permission(role: IMERole | str, permission: str) -> bool:
    """True when the given role includes the named permission."""
    try:
        r = IMERole(role)
    except ValueError:
        return False
    return permission in ROLE_PERMISSIONS.get(r, frozenset())


def user_has_permission(user_roles: Iterable[str], permission: str) -> bool:
    """True when at least one of the user's roles has the permission."""
    return any(role_has_permission(r, permission) for r in user_roles)


# ── Segregation of Duties (سند §14.2) ─────────────────────────────────────

# Pairs of permission categories that no single role may hold. Used by
# the API layer to reject requests that try to combine them in one
# approval workflow.
SEGREGATED_PERMISSION_GROUPS: list[frozenset[str]] = [
    frozenset({"model:write", "risk:write"}),  # model + risk caps
    frozenset({"policy:write", "trade_card:approve"}),  # policy + execution
    frozenset({"kill_switch:revive", "model:write"}),  # undo + retrain
]


def is_segregated_violation(roles: Iterable[str], permissions: set[str]) -> bool:
    """Return True if a single approval workflow tries to combine
    permissions that سند §14.2 says must be split across roles.
    """
    roles_set = {IMERole(r) for r in roles if r in {e.value for e in IMERole}}
    for group in SEGREGATED_PERMISSION_GROUPS:
        if group.issubset(permissions):
            # Find which role(s) hold *all* the perms in this group
            for r in roles_set:
                if all(role_has_permission(r, p) for p in group):
                    return True
    return False


# ── Dual-approval helper (سند §19.3 step 3) ─────────────────────────────


def dual_approval_required(permission: str) -> bool:
    """Permissions that, per سند §19.3, require joint approval of two
    distinct roles (e.g. «تیم فنی» + «کارشناس کمّی»).
    """
    return permission in {
        "kill_switch:revive",  # un-halting trading needs two pairs of eyes
        "risk:write",  # raising/relaxing caps is policy-grade
        "policy:write",  # policy changes
    }


def dual_approval_check(approvers: list[str], permission: str) -> tuple[bool, str]:
    """سند §19.3 step 3 enforcement: at least two distinct approvers, and
    their combined roles must not violate segregation of duties.

    Returns (passed, reason). ``approvers`` is the list of role names
    collected from the approvers' tokens.
    """
    if not dual_approval_required(permission):
        return True, "no dual approval required"
    if len(set(approvers)) < 2:
        return False, f"permission {permission!r} requires ≥2 distinct approvers (سند §19.3)"
    if is_segregated_violation(approvers, {permission}):
        return False, f"approver roles {approvers} violate segregation of duties (سند §14.2)"
    return True, "dual approval satisfied"
