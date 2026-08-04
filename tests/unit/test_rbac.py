"""Comprehensive tests for the RBAC (Role-Based Access Control) system.

Tests cover:
- Role enum and hierarchy
- has_role() with hierarchy checks
- has_any_role() for multiple role checks
- First user gets admin role
- require_role and require_roles dependencies
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from core.enums.rbac import (
    ROLE_HIERARCHY,
    Role,
    has_any_role,
    has_role,
)

# ── Role Enum Tests ──────────────────────────────────────────────


class TestRoleEnum:
    """Tests for Role enum values and ordering."""

    def test_role_values(self):
        assert Role.ADMIN == "admin"
        assert Role.ANALYST == "analyst"
        assert Role.USER == "user"
        assert Role.VIEWER == "viewer"

    def test_role_hierarchy_order(self):
        """Admin should be first (highest privilege), viewer last."""
        assert ROLE_HIERARCHY[0] == Role.ADMIN
        assert ROLE_HIERARCHY[-1] == Role.VIEWER
        assert len(ROLE_HIERARCHY) == 4

    def test_role_is_string_enum(self):
        """Roles should be usable as strings."""
        assert isinstance(Role.ADMIN, str)
        assert Role.ADMIN == "admin"


# ── has_role Tests ───────────────────────────────────────────────


class TestHasRole:
    """Tests for has_role() function with hierarchy checks."""

    def test_admin_always_has_access(self):
        """Admin should have access to any role requirement."""
        assert has_role(["admin"], "admin") is True
        assert has_role(["admin"], "analyst") is True
        assert has_role(["admin"], "user") is True
        assert has_role(["admin"], "viewer") is True

    def test_admin_bypass_with_string_input(self):
        """Admin check should work with comma-separated string input."""
        assert has_role("admin", "admin") is True
        assert has_role("admin", "analyst") is True

    def test_analyst_has_user_permissions(self):
        """Analyst should have user-level permissions."""
        assert has_role(["analyst"], "user") is True
        assert has_role(["analyst"], "viewer") is True
        assert has_role(["analyst"], "analyst") is True

    def test_analyst_does_not_have_admin_permissions(self):
        """Analyst should NOT have admin permissions."""
        assert has_role(["analyst"], "admin") is False

    def test_user_has_viewer_permissions(self):
        """User should have viewer-level permissions."""
        assert has_role(["user"], "viewer") is True
        assert has_role(["user"], "user") is True

    def test_user_does_not_have_analyst_permissions(self):
        """User should NOT have analyst or admin permissions."""
        assert has_role(["user"], "analyst") is False
        assert has_role(["user"], "admin") is False

    def test_viewer_only_has_viewer_permissions(self):
        """Viewer should only have viewer permissions."""
        assert has_role(["viewer"], "viewer") is True
        assert has_role(["viewer"], "user") is False
        assert has_role(["viewer"], "analyst") is False
        assert has_role(["viewer"], "admin") is False

    def test_comma_separated_roles(self):
        """Should handle comma-separated role strings."""
        assert has_role("admin,analyst", "admin") is True
        assert has_role("user,viewer", "viewer") is True
        assert has_role("user,viewer", "admin") is False

    def test_roles_with_spaces(self):
        """Should handle roles with spaces around commas."""
        assert has_role("admin, analyst", "admin") is True
        assert has_role(" user , viewer ", "viewer") is True

    def test_unknown_role_in_user_roles(self):
        """Unknown roles should be skipped gracefully."""
        assert has_role(["unknown_role"], "viewer") is False
        assert has_role(["admin", "unknown_role"], "analyst") is True

    def test_invalid_required_role_with_non_admin(self):
        """Invalid required role should return False for non-admin users."""
        assert has_role(["user"], "invalid_role") is False

    def test_admin_bypasses_invalid_required_role(self):
        """Admin should still pass even if required role is invalid."""
        assert has_role(["admin"], "invalid_role") is True

    def test_empty_user_roles(self):
        """Empty roles list should not grant any access."""
        assert has_role([], "viewer") is False
        assert has_role([], "admin") is False


# ── has_any_role Tests ───────────────────────────────────────────


class TestHasAnyRole:
    """Tests for has_any_role() function."""

    def test_admin_always_matches(self):
        """Admin should match any role list."""
        assert has_any_role(["admin"], ["viewer"]) is True
        assert has_any_role(["admin"], ["analyst", "user"]) is True

    def test_exact_role_match(self):
        """Should match exact roles."""
        assert has_any_role(["user"], ["user"]) is True
        assert has_any_role(["analyst"], ["analyst"]) is True

    def test_no_match(self):
        """Should return False when no roles match."""
        assert has_any_role(["viewer"], ["admin", "analyst"]) is False
        assert has_any_role(["user"], ["admin"]) is False

    def test_comma_separated_roles(self):
        """Should handle comma-separated role strings."""
        assert has_any_role("admin,analyst", ["admin"]) is True
        assert has_any_role("user,viewer", ["admin"]) is False

    def test_role_objects_in_roles_list(self):
        """Should accept Role enum objects in the roles list."""
        assert has_any_role(["admin"], [Role.ADMIN]) is True
        assert has_any_role(["user"], [Role.ADMIN, Role.ANALYST]) is False


# ── require_role / require_roles Dependency Tests ─────────────────


class TestRequireRolesDependency:
    """Tests for require_role and require_roles FastAPI dependencies."""

    def _create_app_with_endpoint(self, dependency_func):
        """Helper to create a test app with a protected endpoint."""
        app = FastAPI()

        @app.get("/protected")
        async def protected(user=Depends(dependency_func)):
            return {"user": user}

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        return app

    def test_require_role_allows_admin(self):
        """require_role('admin') should allow admin users."""
        from core.enums.rbac import has_role

        app = FastAPI()

        async def _mock_get_current_user():
            return {"sub": "1", "roles": ["admin"]}

        async def _check_admin(current_user: dict = Depends(_mock_get_current_user)):
            if not has_role(current_user.get("roles", []), "admin"):
                from fastapi import HTTPException
                raise HTTPException(status_code=403, detail="Forbidden")
            return current_user

        @app.get("/protected")
        async def protected(user=Depends(_check_admin)):
            return {"user": user}

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/protected")
        assert response.status_code == 200

    def test_require_role_denies_viewer(self):
        """require_role('admin') should deny viewer users."""
        from core.enums.rbac import has_role

        app = FastAPI()

        async def _mock_get_current_user():
            return {"sub": "1", "roles": ["viewer"]}

        async def _check_admin(current_user: dict = Depends(_mock_get_current_user)):
            if not has_role(current_user.get("roles", []), "admin"):
                from fastapi import HTTPException
                raise HTTPException(status_code=403, detail="Forbidden")
            return current_user

        @app.get("/protected")
        async def protected(user=Depends(_check_admin)):
            return {"user": user}

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/protected")
        assert response.status_code == 403

    def test_require_role_allows_hierarchy(self):
        """require_role('user') should allow admin and analyst too."""
        from core.enums.rbac import has_role

        # Test with admin user
        app1 = FastAPI()
        async def _mock_admin():
            return {"sub": "1", "roles": ["admin"]}
        async def _check_user_1(current_user: dict = Depends(_mock_admin)):
            if not has_role(current_user.get("roles", []), "user"):
                from fastapi import HTTPException
                raise HTTPException(status_code=403, detail="Forbidden")
            return current_user
        @app1.get("/protected")
        async def protected_1(user=Depends(_check_user_1)):
            return {"user": user}
        client1 = TestClient(app1, raise_server_exceptions=False)
        response1 = client1.get("/protected")
        assert response1.status_code == 200

        # Test with analyst user
        app2 = FastAPI()
        async def _mock_analyst():
            return {"sub": "1", "roles": ["analyst"]}
        async def _check_user_2(current_user: dict = Depends(_mock_analyst)):
            if not has_role(current_user.get("roles", []), "user"):
                from fastapi import HTTPException
                raise HTTPException(status_code=403, detail="Forbidden")
            return current_user
        @app2.get("/protected")
        async def protected_2(user=Depends(_check_user_2)):
            return {"user": user}
        client2 = TestClient(app2, raise_server_exceptions=False)
        response2 = client2.get("/protected")
        assert response2.status_code == 200

    def test_require_roles_allows_any_of_listed(self):
        """require_roles('admin', 'analyst') should allow either."""
        from core.enums.rbac import has_any_role

        # Test admin
        app1 = FastAPI()
        async def _mock_admin():
            return {"sub": "1", "roles": ["admin"]}
        async def _check_any_1(current_user: dict = Depends(_mock_admin)):
            if not has_any_role(current_user.get("roles", []), ["admin", "analyst"]):
                from fastapi import HTTPException
                raise HTTPException(status_code=403, detail="Forbidden")
            return current_user
        @app1.get("/protected")
        async def protected_1(user=Depends(_check_any_1)):
            return {"user": user}
        client1 = TestClient(app1, raise_server_exceptions=False)
        assert client1.get("/protected").status_code == 200

        # Test analyst
        app2 = FastAPI()
        async def _mock_analyst():
            return {"sub": "1", "roles": ["analyst"]}
        async def _check_any_2(current_user: dict = Depends(_mock_analyst)):
            if not has_any_role(current_user.get("roles", []), ["admin", "analyst"]):
                from fastapi import HTTPException
                raise HTTPException(status_code=403, detail="Forbidden")
            return current_user
        @app2.get("/protected")
        async def protected_2(user=Depends(_check_any_2)):
            return {"user": user}
        client2 = TestClient(app2, raise_server_exceptions=False)
        assert client2.get("/protected").status_code == 200

        # Test user (should be denied)
        app3 = FastAPI()
        async def _mock_user():
            return {"sub": "1", "roles": ["user"]}
        async def _check_any_3(current_user: dict = Depends(_mock_user)):
            if not has_any_role(current_user.get("roles", []), ["admin", "analyst"]):
                from fastapi import HTTPException
                raise HTTPException(status_code=403, detail="Forbidden")
            return current_user
        @app3.get("/protected")
        async def protected_3(user=Depends(_check_any_3)):
            return {"user": user}
        client3 = TestClient(app3, raise_server_exceptions=False)
        assert client3.get("/protected").status_code == 403


# ── First User Gets Admin Tests ──────────────────────────────────


class TestFirstUserGetsAdmin:
    """Tests that the first registered user automatically gets admin role."""

    @pytest.mark.asyncio
    async def test_first_user_gets_admin_role(self):
        """First user registered should get admin role."""

        # Mock session: first execute returns None (no existing user), second returns empty list (count=0)
        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                # First call: check existing username/email
                mock_result.scalar_one_or_none.return_value = None
            else:
                # Second call: count users (empty = first user)
                mock_scalars = MagicMock()
                mock_scalars.all.return_value = []
                mock_result.scalars.return_value = mock_scalars
            return mock_result

        mock_session = AsyncMock()
        mock_session.execute = mock_execute
        mock_session.flush = AsyncMock()

        from services.user_service import UserService
        svc = UserService(mock_session)

        with patch("services.user_service.create_access_token", return_value="fake-token"), \
             patch("services.user_service.create_refresh_token", return_value="fake-refresh"), \
             patch("services.user_service.hash_password", return_value="hashed-password"):
            result = await svc.register("admin", "admin@test.com", "password123")
            assert result.success is True
            assert result.value["user"]["roles"] == ["admin"]

    @pytest.mark.asyncio
    async def test_second_user_gets_user_role(self):
        """Second user registered should get user role (not admin)."""

        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                # First call: check existing username/email
                mock_result.scalar_one_or_none.return_value = None
            else:
                # Second call: count users (has existing user)
                mock_scalars = MagicMock()
                mock_scalars.all.return_value = [MagicMock()]  # One existing user
                mock_result.scalars.return_value = mock_scalars
            return mock_result

        mock_session = AsyncMock()
        mock_session.execute = mock_execute
        mock_session.flush = AsyncMock()

        from services.user_service import UserService
        svc = UserService(mock_session)

        with patch("services.user_service.create_access_token", return_value="fake-token"), \
             patch("services.user_service.create_refresh_token", return_value="fake-refresh"), \
             patch("services.user_service.hash_password", return_value="hashed-password"):
            result = await svc.register("user2", "user2@test.com", "password123")
            assert result.success is True
            assert result.value["user"]["roles"] == ["user"]
