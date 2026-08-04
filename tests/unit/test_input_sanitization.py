"""Unit tests for input sanitization (roadmap #17) and the startup lock.

Covers:
- ``_sanitize_value`` / ``_sanitize_field`` helpers used by
  ``InputSanitizationMiddleware``: markup stripped, raw (opaque) fields
  preserved, oversized strings truncated, type confusion rejected.
- ``_with_startup_lock`` / ``_release_startup_lock`` (roadmap #8): the second
  caller cannot acquire while the first holds the lock, and release frees it.
"""

from __future__ import annotations

import pytest

from apps.api.middleware import (
    _sanitize_field,
    _sanitize_value,
    _SanitizeTypeError,
)

# ── Sanitizer helpers ────────────────────────────────────────────────


class TestSanitizeValue:
    def test_strips_html_tags_from_strings(self):
        # strip_html removes tag markup but keeps the text content, so an
        # XSS payload becomes inert text.
        assert _sanitize_value("<script>alert(1)</script>") == "alert(1)"
        assert _sanitize_value("hello <b>world</b>") == "hello world"

    def test_strips_control_chars(self):
        # NUL dropped, CR dropped, LF normalized to a space.
        assert _sanitize_value("a\x00b\r\nc") == "ab c"

    def test_strips_surrounding_whitespace(self):
        assert _sanitize_value("  padded  ") == "padded"

    def test_recurses_into_nested_dicts_and_lists(self):
        payload = {
            "name": "<img src=x onerror=alert(1)>",
            "meta": {"note": "a<b>c", "tags": ["<i>x</i>", "plain"]},
        }
        out = _sanitize_value(payload)
        # An attribute-carrying tag (with an inner '>') is removed whole;
        # simple tags only lose their markup, keeping the text.
        assert out["name"] == ""
        assert out["meta"]["note"] == "ac"
        assert out["meta"]["tags"] == ["x", "plain"]

    def test_numbers_bools_null_pass_through(self):
        payload = {"n": 1, "f": 1.5, "b": True, "z": None}
        assert _sanitize_value(payload) == payload

    def test_oversized_string_truncated(self):
        long = "x" * 200_000
        out = _sanitize_value(long)
        assert len(out) <= 100_000

    def test_depth_guard_still_cleans_strings(self):
        # Past the depth limit strings are still sanitized — no raw-markup
        # bypass via deep nesting.
        out = _sanitize_value("<script>alert(1)</script>", depth=21)
        assert out == "alert(1)"


class TestSanitizeRawFields:
    def test_password_kept_intact(self):
        # `;` / whitespace inside a password must survive for exact-match.
        assert _sanitize_field("password", "P@ss; word ", 0) == "P@ss; word "
        assert _sanitize_field("current_password", "<P>ss", 0) == "<P>ss"

    def test_code_and_token_kept_intact(self):
        assert _sanitize_field("code", "123456", 0) == "123456"
        assert _sanitize_field("refresh_token", "abc.def.ghi", 0) == "abc.def.ghi"
        assert _sanitize_field("mfa_token", "tok;en", 0) == "tok;en"

    def test_raw_field_still_truncated_and_nul_stripped(self):
        assert _sanitize_field("password", "ab\x00cd", 0) == "abcd"
        out = _sanitize_field("token", "y" * 200_000, 0)
        assert len(out) <= 100_000

    def test_normal_field_sanitized(self):
        assert _sanitize_field("full_name", "<script>x</script>", 0) == "x"
        assert _sanitize_field("full_name", "Ali <b>Reza</b>", 0) == "Ali Reza"


class TestSanitizeTypeError:
    def test_non_string_field_value_rejected(self):
        # dicts are recursed; unsupported scalar types are rejected.
        assert _sanitize_value({"name": {"nested": True}}) == {"name": {"nested": True}}
        with pytest.raises(_SanitizeTypeError):
            _sanitize_field("name", b"bytes", 0)

    def test_nested_dict_and_list_values_allowed(self):
        # dict/list values are recursed, not rejected.
        out = _sanitize_value({"a": {"b": "<x>"}, "c": ["<y>"]})
        assert out == {"a": {"b": ""}, "c": [""]}


# ── Startup distributed lock (roadmap #8) ────────────────────────────


class TestStartupLock:
    @pytest.mark.asyncio
    async def test_second_worker_cannot_acquire_while_locked(self, monkeypatch):
        from apps.api import app as app_module

        # Force the in-memory JobLocking fallback (no Redis) so the lock
        # semantics are observable without a running Redis server.
        def fake_get_cache():
            return _NullCache()

        monkeypatch.setattr("jobs.locking.get_cache", fake_get_cache)

        # First worker acquires the lock.
        ok1 = await app_module._with_startup_lock("test_key", "test-task")
        assert ok1 is True

        # Second worker (different owner) must be refused.
        ok2 = await app_module._with_startup_lock("test_key", "test-task")
        assert ok2 is False

        # Release frees it for the next worker.
        await app_module._release_startup_lock("test_key")
        ok3 = await app_module._with_startup_lock("test_key", "test-task")
        assert ok3 is True
        await app_module._release_startup_lock("test_key")

    @pytest.mark.asyncio
    async def test_release_after_acquire_is_idempotent(self, monkeypatch):
        from apps.api import app as app_module

        def fake_get_cache():
            return _NullCache()

        monkeypatch.setattr("jobs.locking.get_cache", fake_get_cache)

        assert await app_module._with_startup_lock("idem", "t") is True
        await app_module._release_startup_lock("idem")
        # Releasing again must not raise.
        await app_module._release_startup_lock("idem")


class _NullCache:
    @property
    def is_connected(self):
        return False

    @property
    def client(self):
        return None
