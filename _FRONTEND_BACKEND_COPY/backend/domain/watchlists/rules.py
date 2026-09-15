from __future__ import annotations


def validate_watchlist_name(name: str) -> bool:
    return bool(name and name.strip())


def can_edit_watchlist(role: str) -> bool:
    return role in ("owner", "editor")


def can_delete_watchlist(is_owner: bool) -> bool:
    return is_owner


def validate_role(role: str) -> bool:
    return role in ("owner", "editor", "viewer")
