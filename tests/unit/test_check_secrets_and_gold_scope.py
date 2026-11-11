"""Unit tests — اسکنر اسرار هاردکدشده.

اسکنری که هیچ‌چیز پیدا نمی‌کند می‌تواند خراب باشد؛ پس اول با فایل مصنوعی
اثبات می‌کنیم تشخیص کار می‌کند، بعد پاک‌بودن درخت کاری را می‌سنجیم.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_scanner():
    spec = importlib.util.spec_from_file_location(
        "check_secrets", REPO_ROOT / "scripts" / "check_secrets.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_secrets"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


scanner = _load_scanner()

# نمونه‌ها تکه‌تکه ساخته می‌شوند تا خودِ همین فایل تست به یک «راز هاردکد» تبدیل نشود.
_BRSAPI_LIKE = "Bk" + "7JvdJZBHJ9DMhzeuTfWjwqYy1wMsif"
_AVALAI_LIKE = "aa-cwf9" + "gL3WJ73ISkDP0cZCOwPMsefdYJsNcssmhhOZ4StLrs9B"
_DB_LIKE = "Im_GCZ" + "jNmnzhL4FModjociYjzme"


@pytest.mark.parametrize(
    "template",
    [
        'API_KEY = "{secret}"\n',
        "SECRET_TOKEN: '{secret}'\n",
        'DB_PASSWORD = "{secret}"\n',
        "      - POSTGRES_PASSWORD={secret}\n",
    ],
)
@pytest.mark.parametrize("secret", [_BRSAPI_LIKE, _AVALAI_LIKE, _DB_LIKE])
def test_scanner_detects_real_looking_secrets(
    tmp_path: Path, template: str, secret: str
) -> None:
    target = tmp_path / "leaky.py"
    target.write_text(template.format(secret=secret), encoding="utf-8")
    findings = scanner.scan_file(target)
    assert findings, f"scanner missed a hardcoded secret in {template!r}"
    # مقدار هرگز نباید در خروجی اسکنر چاپ شود.
    assert all(secret not in str(f) for f in findings)


@pytest.mark.parametrize(
    "content",
    [
        'API_KEY = os.environ.get("BRSAPI_API_KEY", "")',
        "API_KEY = settings.brsapi_api_key",
        "POSTGRES_PASSWORD=${POSTGRES_PASSWORD:?must be set}",
        "DB_PASSWORD=password",
        "GOLD_TELEGRAM_BOT_TOKEN=123456:ABC-DEF...",
        "SMTP_PASSWORD=your-app-password",
        "AUTH_TOKEN=<inject-from-secret-manager>",
    ],
)
def test_scanner_ignores_placeholders_and_env_lookups(tmp_path: Path, content: str) -> None:
    target = tmp_path / "clean.py"
    target.write_text(content, encoding="utf-8")
    assert scanner.scan_file(target) == []


def test_working_tree_has_no_hardcoded_secrets() -> None:
    """رگرسیون‌گیر: کلید هاردکد شده نباید برگردد."""
    findings = scanner.scan()
    assert findings == [], "hardcoded secret found: " + ", ".join(
        f"{f['file']}:{f['line']}" for f in findings
    )


def test_previously_leaked_files_read_from_environment() -> None:
    """فایل‌هایی که کلیدشان لو رفته بود باید از محیط بخوانند، نه از literal."""
    for rel in (
        "z.py",
        "collector.py",
        "script.py",
        "assistant.py",
        "scripts/backfill_funds_only.py",
    ):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        assert "os.environ" in text, f"{rel} must read secrets from the environment"
        assert _BRSAPI_LIKE not in text, f"{rel} still contains the leaked BrsApi key"
        assert _AVALAI_LIKE not in text, f"{rel} still contains the leaked AvalAI key"
        assert _DB_LIKE not in text, f"{rel} still contains a DB password"
