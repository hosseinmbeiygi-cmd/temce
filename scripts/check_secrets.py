"""اسکنر اسرار هاردکدشده در سورس (بدون وابستگی خارجی).

چرا: کلیدهای BrsApi و AvalAI یک بار در همین ریپو هاردکد شده و در git history
ثبت شده‌اند. `.pre-commit-config.yaml` فقط diff را با gitleaks بررسی می‌کند؛ این
اسکریپت کل درخت کاری را می‌بیند و در تست واحد هم اجرا می‌شود تا رگرسیون نگیریم.

    python scripts/check_secrets.py            # بازگشت غیرصفر در صورت یافتن مورد
    python scripts/check_secrets.py --json      # خروجی ماشینی

هر «یافته» یعنی یک مقدار ثابت به یک نام حساس (API_KEY/SECRET/TOKEN/PASSWORD/...)
نسبت داده شده است. مقادیر placeholder و خواندن از محیط مجاز‌اند.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# مسیرهایی که واقعاً سورس‌اند (بقیهٔ ریپو داده/خروجی ابزار است و اسکن نمی‌شود).
SCAN_DIRS = (
    "apps",
    "brsapi",
    "core",
    "jobs",
    "migrations",
    "scripts",
    "services",
    "src",
    "tests",
    "frontend/src",
)

SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "venv",
    ".venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".next",
}

TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".cjs",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
    ".example",
    ".json",
    ".md",
    ".sh",
}

MAX_BYTES = 2_000_000

# نام متغیری که اگر مقدار ثابت بگیرد، «راز هاردکد» است.
_SECRET_NAME = r"(?:[A-Za-z_][A-Za-z0-9_]*)?(?:API_?KEY|SECRET|TOKEN|PASSWORD|PASSWD|PWD|CREDENTIALS?)"

# فرم‌های assignment:  NAME = "..."  |  NAME: "..."  |  NAME=...  |  - NAME=...
_ASSIGN_PATTERNS = (
    re.compile(rf"\b{_SECRET_NAME}\b\s*[:=]\s*([\"'])(?P<value>[^\"'\n]{{8,}})\1"),
    re.compile(rf"^\s*[- ]?\s*{_SECRET_NAME}\s*[:=]\s*(?P<value>[^\s\"'#]{{8,}})\s*$", re.MULTILINE),
)

# ارزش‌هایی که راز نیستند.
_PLACEHOLDER_HINTS = (
    "your-",
    "your_",
    "change-me",
    "changeme",
    "placeholder",
    "example",
    "dummy",
    "fake",
    "sample",
    "xxx",
    "****",
    "redacted",
    "todo",
    "none",
    "null",
    "true",
    "false",
    "not-set",
    # نمونه‌های مستندات (مثل توکن نمونهٔ تلگرام: ``123456:ABC-DEF...``)
    "...",
    "abc-def",
    "abc123",
)

# فراخوانی محیطی/مقدار غیرثابت (f-string، interpolation، secret manager، ...).
_DYNAMIC_HINTS = (
    "os.environ",
    "getenv",
    "process.env",
    "${",
    "<",
    "settings.",
    "config.",
    "self.",
    "f\"",
    "f'",
    "%s",
    "input(",
    ":?",
)


def _looks_like_placeholder(value: str) -> bool:
    low = value.lower()
    if any(hint in low for hint in _PLACEHOLDER_HINTS):
        return True
    if any(hint in value for hint in _DYNAMIC_HINTS):
        return True
    # ``{KEY}`` / ``${VAR}`` / ``$SECRET`` = جای‌نگهدار، نه مقدار ثابت.
    if any(ch in value for ch in "{}$"):
        return True
    # مقدار تک‌کلمه‌ای کوتاه بدون آنتروپی (مثل ``localhost``) راز نیست.
    return len(value) < 16 and not any(c.isdigit() for c in value)


def _iter_files(roots: tuple[str, ...] = SCAN_DIRS) -> list[Path]:
    files: list[Path] = []
    for rel in roots:
        base = REPO_ROOT / rel
        if base.is_file():
            files.append(base)
            continue
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                path = Path(dirpath) / name
                suffix = path.suffix.lower()
                if suffix not in TEXT_SUFFIXES and not name.startswith(".env"):
                    continue
                try:
                    if path.stat().st_size > MAX_BYTES:
                        continue
                except OSError:
                    continue
                files.append(path)
    # فایل‌های سطح ریشه (اسکریپت‌های پراکنده) هم بررسی می‌شوند.
    for path in sorted(REPO_ROOT.glob("*.py")) + sorted(REPO_ROOT.glob("docker-compose*.yml")):
        if path not in files:
            files.append(path)
    return files


def scan_file(path: Path) -> list[dict[str, object]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    findings: list[dict[str, object]] = []
    for pattern in _ASSIGN_PATTERNS:
        for match in pattern.finditer(text):
            value = (match.group("value") or "").strip()
            if not value or _looks_like_placeholder(value):
                continue
            try:
                rel_path = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
            except ValueError:  # مسیر خارج از ریپو (تست‌ها)
                rel_path = str(path).replace("\\", "/")
            findings.append(
                {
                    "file": rel_path,
                    "line": text.count("\n", 0, match.start()) + 1,
                    "name": next(
                        (m.group(0) for m in re.finditer(_SECRET_NAME, match.group(0))),
                        "secret",
                    ),
                    # مقدار هرگز چاپ نمی‌شود؛ فقط طول و دو کاراکتر اول برای شناسایی.
                    "value_len": len(value),
                    "value_head": value[:2],
                }
            )
    return findings


def scan(roots: tuple[str, ...] = SCAN_DIRS) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for path in _iter_files(roots):
        findings.extend(scan_file(path))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan the working tree for hardcoded secrets")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("paths", nargs="*", help="optional subtrees (default: whole source tree)")
    args = parser.parse_args(argv)

    findings = scan(tuple(args.paths) if args.paths else SCAN_DIRS)

    if args.json:
        print(json.dumps({"count": len(findings), "findings": findings}, ensure_ascii=False, indent=2))
    else:
        if findings:
            print(f"FAIL: {len(findings)} hardcoded secret candidate(s):")
            for f in findings:
                print(f"  {f['file']}:{f['line']}  {f['name']} = (2 chars: {f['value_head']}) ({f['value_len']} chars)")
            print("\nمقدار را از سورس حذف کنید و از محیط بخوانید (os.environ / process.env).")
        else:
            print("OK: no hardcoded secrets found")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
