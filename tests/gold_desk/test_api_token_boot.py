"""مرز واقعیِ import برای salt اجباری API token (سطح subprocess).

``src.gold_desk.api_token`` هیچ salt پیش‌فرضی ندارد و بدون env در همان import
``RuntimeError`` می‌دهد. این تست در یک process تازه (بدون کمک conftest) ثابت
می‌کند:

* بدون ``GOLD_API_TOKEN_SALT``، import خودِ ``api_token`` با پیام روشن شکست
  می‌خورد؛
* ``apps.api.app`` (entrypoint واقعی API) هم در سطح ماژول همان guard را
  import می‌کند، پس **process** بدون salt بالا نمی‌آید (fail-fast)؛
* با env، هم ``api_token`` و هم ``apps.api.app`` import می‌شوند؛
* ``src.gold_desk.api`` خودش ``api_token`` را در سطح ماژول import نمی‌کند
  (مسیرهای token داخل تابع import می‌کنند)؛ guard در entrypoint گذاشته شده،
  نه در ماژول router.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _run(code: str, *, salt: str | None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if salt is None:
        env.pop("GOLD_API_TOKEN_SALT", None)
    else:
        env["GOLD_API_TOKEN_SALT"] = salt
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_api_token_import_fails_fast_without_salt() -> None:
    result = _run("import src.gold_desk.api_token", salt=None)

    assert result.returncode != 0
    assert "GOLD_API_TOKEN_SALT is not set" in result.stderr


def test_api_token_import_succeeds_with_salt() -> None:
    result = _run(
        "import src.gold_desk.api_token as m; print('SALT_SET=' + str(bool(m.SALT)))",
        salt="subprocess-test-salt",
    )

    assert result.returncode == 0, result.stderr
    assert "SALT_SET=True" in result.stdout


def test_api_module_import_is_lazy_without_salt() -> None:
    result = _run(
        "import sys\n"
        "import src.gold_desk.api\n"
        "print('api_token_loaded=' + str('src.gold_desk.api_token' in sys.modules))",
        salt=None,
    )

    assert result.returncode == 0, result.stderr
    assert "api_token_loaded=False" in result.stdout


def test_api_and_api_token_import_with_salt() -> None:
    result = _run(
        "import src.gold_desk.api\nimport src.gold_desk.api_token\nimport apps.api.app\nprint('OK')",
        salt="subprocess-test-salt",
    )

    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_api_entrypoint_fails_fast_without_salt() -> None:
    result = _run("import apps.api.app", salt=None)

    assert result.returncode != 0
    assert "GOLD_API_TOKEN_SALT is not set" in result.stderr
