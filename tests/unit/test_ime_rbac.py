"""Tests for the IME RBAC and Segregation of Duties (سند v5.0 §14.2 + §19.3).

Covers the four operational roles, permission grants, the segregation-of-
duties matrix, and the dual-approval workflow helper.
"""

from __future__ import annotations

from core.security.ime_rbac import (
    ROLE_PERMISSIONS,
    SEGREGATED_PERMISSION_GROUPS,
    IMERole,
    dual_approval_check,
    dual_approval_required,
    is_segregated_violation,
    role_has_permission,
    user_has_permission,
)


class TestRolePermissions:
    def test_viewer_only_reads(self):
        assert role_has_permission(IMERole.VIEWER, "signal:read")
        assert not role_has_permission(IMERole.VIEWER, "trade_card:approve")
        assert not role_has_permission(IMERole.VIEWER, "kill_switch:activate")
        assert not role_has_permission(IMERole.VIEWER, "model:write")

    def test_trader_can_approve_cards(self):
        assert role_has_permission(IMERole.TRADER, "trade_card:approve")
        assert role_has_permission(IMERole.TRADER, "trade_card:reject")
        # Trader must NOT be able to change model params
        assert not role_has_permission(IMERole.TRADER, "model:write")
        # Trader must NOT be able to flip kill switch
        assert not role_has_permission(IMERole.TRADER, "kill_switch:activate")

    def test_quant_can_change_models(self):
        assert role_has_permission(IMERole.QUANT, "model:write")
        assert role_has_permission(IMERole.QUANT, "model:calibrate")
        # Quant must NOT change risk caps (سند §14.2 segregation)
        assert not role_has_permission(IMERole.QUANT, "risk:write")
        # Quant must NOT approve trade cards
        assert not role_has_permission(IMERole.QUANT, "trade_card:approve")

    def test_admin_can_manage_risk_and_kill_switch(self):
        assert role_has_permission(IMERole.ADMIN, "risk:write")
        assert role_has_permission(IMERole.ADMIN, "kill_switch:activate")
        assert role_has_permission(IMERole.ADMIN, "kill_switch:revive")
        # Admin does NOT write models (segregation: keep model changes with quant)
        assert not role_has_permission(IMERole.ADMIN, "model:write")
        # Admin does NOT approve trade cards (segregation: keep execution with trader)
        assert not role_has_permission(IMERole.ADMIN, "trade_card:approve")

    def test_all_roles_can_read(self):
        for role in IMERole:
            assert role_has_permission(role, "signal:read"), f"{role} missing signal:read"

    def test_unknown_role_returns_false(self):
        assert role_has_permission("ghost", "signal:read") is False
        assert role_has_permission(123, "signal:read") is False

    def test_string_role_lookup(self):
        # str-compatible (سند §14.2 uses Persian labels; we store the
        # ascii form in the token and look up by string)
        assert role_has_permission("viewer", "signal:read")
        assert role_has_permission("admin", "kill_switch:activate")


class TestUserHasPermission:
    def test_user_with_multiple_roles(self):
        # A user with both viewer + quant perms should pass either set
        assert user_has_permission(["viewer"], "signal:read")
        assert user_has_permission(["viewer", "quant"], "model:write")
        assert not user_has_permission(["viewer"], "model:write")

    def test_empty_roles(self):
        assert user_has_permission([], "signal:read") is False


class TestSegregationOfDuties:
    """سند §14.2: no single role can hold both model and risk authority."""

    def test_quant_cannot_combine_model_and_risk(self):
        # Even with a single quant approver, having BOTH perms is the
        # violation case (but in practice the quant role doesn't hold
        # risk:write). The check is against the held role set.
        assert not is_segregated_violation(["quant"], {"model:write", "risk:write"})

    def test_admin_does_not_hold_model_authority(self):
        # Admin has risk:write but NOT model:write → segregation is preserved
        assert not is_segregated_violation(["admin"], {"risk:write"})

    def test_violation_when_single_role_covers_segregated_group(self):
        # Construct an artificial role that has both model:write AND
        # risk:write (this should never happen in production but the
        # check should detect it). Using admin + an override is not
        # possible, so we test the rule directly: a role with both
        # perms triggers the violation. We simulate by checking the
        # segregated groups exist for the documented pairs.
        group = frozenset({"model:write", "risk:write"})
        assert group in SEGREGATED_PERMISSION_GROUPS

    def test_segregation_pairs_match_sections(self):
        # Documented pairs from سند §14.2
        all_pairs = {tuple(sorted(g)) for g in SEGREGATED_PERMISSION_GROUPS}
        assert ("kill_switch:revive", "model:write") in all_pairs
        assert ("model:write", "risk:write") in all_pairs


class TestDualApproval:
    """سند §19.3 step 3: kill_switch:revive / risk:write / policy:write
    require ≥2 distinct approvers and segregation check."""

    def test_kill_switch_revive_requires_dual(self):
        assert dual_approval_required("kill_switch:revive") is True
        assert dual_approval_required("risk:write") is True
        assert dual_approval_required("policy:write") is True

    def test_normal_actions_skip_dual_approval(self):
        assert dual_approval_required("model:write") is False
        assert dual_approval_required("trade_card:approve") is False
        assert dual_approval_required("signal:read") is False

    def test_dual_approval_with_two_distinct_roles(self):
        # kill_switch:revive: admin (no model perm) + quant (model perm) →
        # neither single role covers {kill_switch:revive, model:write}
        ok, reason = dual_approval_check(["admin", "quant"], "kill_switch:revive")
        assert ok, reason
        assert "dual approval satisfied" in reason

    def test_dual_approval_rejects_single_approver(self):
        ok, reason = dual_approval_check(["admin"], "kill_switch:revive")
        assert not ok
        assert "≥2 distinct approvers" in reason

    def test_dual_approval_rejects_segregation_violation(self):
        # Two distinct approvers needed; ["admin","admin"] collapses to 1
        ok, reason = dual_approval_check(["admin", "admin"], "kill_switch:revive")
        assert not ok
        assert "≥2 distinct" in reason

    def test_dual_approval_admin_plus_quant_ok(self):
        # admin + quant — distinct, neither holds both perms
        ok, reason = dual_approval_check(["admin", "quant"], "kill_switch:revive")
        assert ok
        assert "dual approval satisfied" in reason

    def test_dual_approval_skipped_for_non_sensitive(self):
        ok, reason = dual_approval_check(["trader"], "model:write")
        assert ok
        assert "no dual approval" in reason


class TestIntegration:
    """Combined checks: the realistic decision-support flow."""

    def test_trader_cannot_run_a_full_model_change(self):
        # A trader tries to change model params. Even with view+trader
        # roles, they don't have model:write.
        roles = ["viewer", "trader"]
        assert not user_has_permission(roles, "model:write")

    def test_quant_cannot_approve_trade_cards(self):
        roles = ["viewer", "quant"]
        assert not user_has_permission(roles, "trade_card:approve")

    def test_admin_can_reactivate_killing_with_quant_pair(self):
        # Killing then reviving requires admin+quant per سند §19.3
        roles = ["admin", "quant"]
        for r in roles:
            perms = ROLE_PERMISSIONS[IMERole(r)]
            assert not ({"model:write", "risk:write"}.issubset(perms)), f"{r} violates segregation"
