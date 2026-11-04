"""قرارداد salt برای API token: بدون env خطا، با env سالم.

هیچ salt پیش‌فرضی نباید وجود داشته باشد؛ ``GOLD_API_TOKEN_SALT`` اجباری است و
تغییرش همهٔ توکن‌های قبلی را باطل می‌کند.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import os

import pytest

import src.gold_desk.api_token as api_token


def test_import_fails_without_salt(monkeypatch) -> None:
    monkeypatch.delenv("GOLD_API_TOKEN_SALT", raising=False)

    with pytest.raises(RuntimeError, match="GOLD_API_TOKEN_SALT"):
        importlib.reload(api_token)

    # بازگرداندن ماژول به حالت سالم برای تست‌های بعدی همین session.
    monkeypatch.setenv("GOLD_API_TOKEN_SALT", "test-salt-for-pytest")
    importlib.reload(api_token)
    assert api_token.SALT == "test-salt-for-pytest"


def test_salt_comes_from_env_and_hashes_with_it(monkeypatch) -> None:
    monkeypatch.setenv("GOLD_API_TOKEN_SALT", "another-test-salt")
    importlib.reload(api_token)

    try:
        assert api_token.SALT == "another-test-salt"
        expected = hashlib.sha256(("token-value" + "another-test-salt").encode()).hexdigest()
        assert api_token._hash("token-value") == expected
    finally:
        importlib.reload(api_token)


def test_no_builtin_default_salt_remains(monkeypatch) -> None:
    monkeypatch.setenv("GOLD_API_TOKEN_SALT", "test-salt-for-pytest")
    importlib.reload(api_token)

    source = inspect.getsource(api_token)
    assert "temce-golddesk-default-salt" not in source
    assert 'os.getenv("ENV") == "production"' not in source


def test_metrics_scope_is_recognised() -> None:
    plain, info = api_token.generate_token("scraper", ["metrics"])

    assert info.scopes == ["metrics"]
    assert api_token.has_scope(info, "metrics") is True
    assert api_token.has_scope(info, "read") is False
    # توکن plain فقط برای ساخت ذخیره است و هیچ‌گاه در metadata نمی‌آید.
    assert plain not in api_token.info_to_dict(info).values()
    assert os.environ.get("GOLD_API_TOKEN_SALT")
