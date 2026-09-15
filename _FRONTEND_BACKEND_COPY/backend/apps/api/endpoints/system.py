"""System administration endpoints — kill switch + risk caps (سند v5.0 §15.3 + §19.3).

Provides the operational surfaces the on-call team uses during an
incident:
  - GET  /api/v1/system/kill-switch        — read current state
  - POST /api/v1/system/kill-switch/activate   — kill all new signals
  - POST /api/v1/system/kill-switch/revive     — re-enable (dual approval)

Endpoints sit behind role-based access control:
  - /activate requires the «مدیر» role (admin)
  - /revive requires dual approval per سند §19.3: two distinct roles
    with no single role covering both ``kill_switch:revive`` and any
    other sensitive permission (segregation of duties, §14.2).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from apps.api.dependencies import get_current_user, require_roles
from core.logging import get_logger
from core.security.ime_rbac import (
    IMERole,
    dual_approval_check,
    role_has_permission,
)
from services.kill_switch import kill_switch

logger = get_logger(__name__)
router = APIRouter(prefix="/system", tags=["system"])


def _roles_of(user: dict[str, Any]) -> list[str]:
    """Extract the role names from the JWT payload.

    سند §14.2: token carries the role set assigned to the user. The
    shape mirrors ``require_roles`` upstream so this stays consistent.
    """
    return [str(r) for r in user.get("roles", []) if r]


@router.get(
    "/kill-switch",
    summary="Read current kill-switch state (سند §15.3)",
)
async def get_kill_switch_state(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    state = kill_switch.status()
    return {
        "killed": state.killed,
        "by": state.by,
        "reason": state.reason,
        "at": state.at,
        "viewer_roles": _roles_of(user),
    }


@router.post(
    "/kill-switch/activate",
    dependencies=[Depends(require_roles(IMERole.ADMIN.value))],
    summary="Activate the kill switch (سند §15.3, §19.3)",
)
async def activate_kill_switch(
    payload: dict[str, Any] = Body(default_factory=dict),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    reason = str(payload.get("reason", "")).strip() or "unspecified"
    actor = _actor_id(user)
    state = await kill_switch.kill(actor, reason)
    logger.warning("Kill switch ACTIVATED by %s (role=%s): %s", actor, _roles_of(user), reason)
    return {"killed": state.killed, "by": state.by, "reason": state.reason, "at": state.at}


@router.post(
    "/kill-switch/revive",
    summary="Revive the kill switch — dual approval (سند §19.3 + §14.2)",
)
async def revive_kill_switch(
    payload: dict[str, Any] = Body(default_factory=dict),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Two distinct approvers required per سند §19.3 step 3.

    The body must include an ``approver_roles`` list with at least two
    role names. We then enforce the segregation-of-duties matrix so no
    single role on the approver list covers both ``kill_switch:revive``
    and any other sensitive permission.
    """
    approver_roles = payload.get("approver_roles") or []
    if not isinstance(approver_roles, list) or not approver_roles:
        raise HTTPException(
            status_code=422,
            detail="approver_roles is required and must be a non-empty list",
        )
    approver_roles = [str(r) for r in approver_roles]

    ok, reason_msg = dual_approval_check(approver_roles, "kill_switch:revive")
    if not ok:
        raise HTTPException(status_code=403, detail=reason_msg)

    actor = _actor_id(user)
    try:
        state = await kill_switch.revive(actor, approver_roles=approver_roles)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    logger.warning(
        "Kill switch REVIVED by %s (initiator_role=%s, approvers=%s)",
        actor,
        _roles_of(user),
        approver_roles,
    )
    return {
        "killed": state.killed,
        "by": state.by,
        "reason": state.reason,
        "at": state.at,
        "approver_roles": approver_roles,
    }


def _actor_id(user: dict[str, Any]) -> str:
    """Return a stable actor identifier from the JWT payload.

    Falls back to a tagged role string when the token lacks ``sub`` so
    audit trails still carry a meaningful actor label in dev / test.
    """
    sub = user.get("sub") or user.get("user_id")
    if sub:
        return f"user:{sub}"
    return f"role:{','.join(_roles_of(user)) or 'anonymous'}"


# ── Helper: Permission check (سند §14.2) ─────────────────────────────────


@router.get(
    "/permissions/check",
    summary="Check whether the caller has a specific permission",
)
async def check_permission(permission: str, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """سند §14.2 diagnostic: returns whether any of the caller's roles
    carries the requested permission. Useful for the admin panel to
    enable/disable buttons.
    """
    roles = _roles_of(user)
    granted = [r for r in roles if role_has_permission(r, permission)]
    return {
        "permission": permission,
        "granted": bool(granted),
        "granted_by_roles": granted,
    }
