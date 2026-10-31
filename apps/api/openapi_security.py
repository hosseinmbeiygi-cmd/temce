"""OpenAPI security metadata for the Bearer-JWT dependencies.

FastAPI only emits ``security`` for routes that use ``Security(...)``; this app
uses ``Depends(get_current_user)`` and ``Header()`` instead, so the generated
contract advertised no auth at all (AUD-API-02). This decorator inspects each
route's dependency tree and declares the scheme for the operations that really
require a token.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute

_BEARER_SCHEME = {
    "type": "http",
    "scheme": "bearer",
    "bearerFormat": "JWT",
    "description": "JWT access token: Authorization: Bearer <token>",
}

# Dependencies that require a valid token for every method.
_FULL_AUTH = {"get_current_user", "get_current_active_user", "require_role"}
# Dependency that only requires a token for mutating methods.
_WRITE_AUTH = {"require_user_for_writes"}


def _dependency_names(dependant) -> set[str]:
    names: set[str] = set()
    stack = [dependant]
    while stack:
        dependency = stack.pop()
        call = getattr(dependency, "call", None)
        name = getattr(call, "__name__", "") if call is not None else ""
        if name:
            names.add(name)
        stack.extend(getattr(dependency, "dependencies", ()) or ())
    return names


def install_openapi_security(app: FastAPI) -> None:
    original_openapi = app.openapi

    def custom_openapi():
        schema = original_openapi()
        secured = 0
        for route in app.routes:
            if not isinstance(route, APIRoute) or not route.include_in_schema:
                continue
            names = _dependency_names(route.dependant)
            full_auth = bool(names & _FULL_AUTH)
            write_only = bool(names & _WRITE_AUTH)
            if not full_auth and not write_only:
                continue
            path_item = schema.get("paths", {}).get(route.path)
            if not path_item:
                continue
            for method in route.methods or ():
                if write_only and method in {"GET", "HEAD", "OPTIONS"}:
                    continue
                operation = path_item.get(method.lower())
                if operation is None:
                    continue
                operation["security"] = [{"bearerAuth": []}]
                secured += 1
        if secured:
            components = schema.setdefault("components", {})
            components.setdefault("securitySchemes", {})["bearerAuth"] = _BEARER_SCHEME
        return schema

    app.openapi = custom_openapi
