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
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from apps.api.middleware import (
    _clean_text,
    _sanitize_field,
    _sanitize_value,
    _SanitizeTypeError,
)
from core.security.sanitizers import safe_path_component

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


class TestControlAndBidi:
    def test_c0_and_c1_controls_removed(self):
        assert _clean_text("a\x01b\x7fc\x9fd\x00e") == "abcde"

    def test_bidi_override_and_isolate_removed(self):
        # Trojan-Source style overrides/isolates never survive.
        assert _clean_text("متن\u202eabc\u2066def\u2069") == "متنabcdef"

    def test_persian_shaping_characters_preserved(self):
        # ZWNJ (U+200C), RLM (U+200F) and Persian digits are legitimate.
        value = "فولاد\u200cسازی\u200f ۱۲۳۴۵ ریال"
        assert _clean_text(value) == value

    def test_arabic_text_preserved(self):
        value = "الشركة الوطنية للأسمنت"
        assert _clean_text(value) == value


class TestFinancialTextPreserved:
    def test_numbers_and_symbols_untouched(self):
        assert _clean_text("P/E: 12.5% | EPS=1,234 | RSI 45.6") == "P/E: 12.5% | EPS=1,234 | RSI 45.6"

    def test_lone_angle_bracket_is_not_markup(self):
        # A comparison sign is not a tag and must not be stripped.
        assert _clean_text("x < y > z") == "x < y > z"

    def test_numbers_bools_pass_through_sanitizer(self):
        payload = {"price": 1234.5, "volume": 10**9, "ok": True}
        assert _sanitize_value(payload) == payload


class TestEntityEncodedMarkup:
    def test_single_encoded_tags_removed(self):
        assert _clean_text("&lt;script&gt;alert(1)&lt;/script&gt;") == "alert(1)"
        assert _clean_text("&#60;img src=x onerror=alert(1)&#62;") == ""

    def test_double_encoded_tags_removed(self):
        assert _clean_text("&amp;lt;script&amp;gt;x") == "x"

    def test_plain_entity_text_unchanged(self):
        # Only entity-encoded *markup* is decoded; ordinary text is not rewritten.
        assert _clean_text("Tom &amp; Jerry") == "Tom &amp; Jerry"


class TestPathLikeFields:
    def test_traversal_neutralised_in_filename(self):
        out = _sanitize_field("filename", "../../etc/passwd", 0)
        assert "/" not in out and "\\" not in out
        assert not out.startswith("..")

    def test_windows_traversal_neutralised(self):
        out = _sanitize_field("file_path", "..\\..\\windows\\system32", 0)
        assert "\\" not in out and "/" not in out
        assert not out.startswith("..")

    def test_persian_filename_preserved(self):
        assert _sanitize_field("filename", "فولاد_۱۴۰۵.xlsx", 0) == "فولاد_۱۴۰۵.xlsx"

    def test_non_path_field_keeps_slashes(self):
        # Ordinary text with slashes is not path-mangled.
        assert _sanitize_field("note", "خرید/فروش", 0) == "خرید/فروش"

    def test_safe_path_component_edge_cases(self):
        assert safe_path_component("") == "unknown"
        assert safe_path_component("..") == "unknown"
        assert safe_path_component(". .") == "unknown"
        assert safe_path_component("CON") == "unknown"
        assert safe_path_component("nul.txt") == "unknown"
        assert safe_path_component("فولاد") == "فولاد"


class TestMiddlewareActivation:
    """The middleware is actually wired and rewrites the body handlers read."""

    def _client(self):
        from apps.api.middleware import InputSanitizationMiddleware

        app = FastAPI()
        app.add_middleware(InputSanitizationMiddleware)

        @app.post("/echo")
        async def echo(request: Request):
            return await request.json()

        return TestClient(app)

    def test_json_body_is_sanitized_before_the_handler(self):
        res = self._client().post(
            "/echo",
            json={"name": "<script>alert(1)</script>", "password": "<P>ss word"},
        )
        assert res.status_code == 200
        assert res.json() == {"name": "alert(1)", "password": "<P>ss word"}

    def test_persian_payload_roundtrips_unchanged(self):
        payload = {"note": "فولاد\u200cسازی ۱۲۳ ریال", "price": 1234.5}
        res = self._client().post("/echo", json=payload)
        assert res.json() == payload


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


class TestDictKeysCleaned:
    def test_markup_in_object_key_removed(self):
        out = _sanitize_value({"<script>x</script>": 1, "ok": 2})
        assert out == {"x": 1, "ok": 2}

    def test_plain_and_persian_keys_unchanged(self):
        payload = {"نماد": "فولاد", "price": 1.5}
        assert _sanitize_value(payload) == payload

    def test_key_that_is_only_markup_is_kept_verbatim(self):
        # Collapsing to "" would be a worse failure than a harmless key.
        assert _sanitize_value({"<img src=x onerror=alert(1)>": 1}) == {
            "<img src=x onerror=alert(1)>": 1
        }


# ── Query-string / form-body coverage ────────────────────────────


class TestQueryStringSanitization:
    """Query parameters are user-controlled on every method."""

    def _client(self):
        from apps.api.middleware import InputSanitizationMiddleware

        app = FastAPI()
        app.add_middleware(InputSanitizationMiddleware)

        @app.get("/q")
        async def q(request: Request):
            return dict(request.query_params)

        return TestClient(app)

    def test_markup_stripped_from_query_value(self):
        res = self._client().get("/q", params={"q": "<script>alert(1)</script>"})
        assert res.status_code == 200
        assert res.json() == {"q": "alert(1)"}

    def test_encoded_markup_stripped(self):
        res = self._client().get("/q", params={"q": "&lt;img src=x onerror=alert(1)&gt;"})
        assert res.json() == {"q": ""}

    def test_persian_and_financial_values_preserved(self):
        res = self._client().get("/q", params={"q": "فولاد\u200cسازی ۱۲۳ | P/E=12.5"})
        assert res.json() == {"q": "فولاد\u200cسازی ۱۲۳ | P/E=12.5"}

    def test_raw_field_untouched(self):
        res = self._client().get("/q", params={"token": "a.b<t>c"})
        assert res.json() == {"token": "a.b<t>c"}

    def test_path_like_field_neutralises_traversal(self):
        res = self._client().get("/q", params={"path": "../../etc/passwd"})
        value = res.json()["path"]
        assert "/" not in value and "\\" not in value
        assert not value.startswith("..")

    def test_repeated_params_keep_order(self):
        res = self._client().get("/q?a=<b>1</b>&a=2")
        # FastAPI's mapping keeps the last occurrence for a repeated name, and
        # the sanitized value must still be the one the handler sees.
        assert res.json() == {"a": "2"}

    def test_control_chars_removed(self):
        res = self._client().get("/q?a=x%01y")
        assert res.json() == {"a": "xy"}


class TestFormBodySanitization:
    def _client(self):
        from apps.api.middleware import InputSanitizationMiddleware

        app = FastAPI()
        app.add_middleware(InputSanitizationMiddleware)

        @app.post("/f")
        async def f(request: Request):
            return dict(await request.form())

        return TestClient(app)

    def test_urlencoded_body_sanitized(self):
        res = self._client().post(
            "/f",
            data={"name": "<script>alert(1)</script>", "password": "<P>ss word"},
        )
        assert res.status_code == 200
        assert res.json() == {"name": "alert(1)", "password": "<P>ss word"}

    def test_persian_form_value_preserved(self):
        res = self._client().post("/f", data={"note": "فولاد\u200cسازی"})
        assert res.json() == {"note": "فولاد\u200cسازی"}


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
