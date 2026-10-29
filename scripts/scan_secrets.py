#!/usr/bin/env python3
"""S3 — اسکن الگوی secret در کل درخت کار (نه فقط diff کامیت‌ها).

چرا این اسکریپت لازم شد: `.github/workflows/secrets-scan.yml` از قبل gitleaks را
اجرا می‌کند، اما gitleaks-action به‌صورت پیش‌فرض **کامیت‌های تازهٔ یک push** را
می‌بیند؛ secretهایی که پیش از وجود آن workflow commit شده‌اند هرگز گزارش نمی‌شوند
(دقیقاً همان اتفاقی که برای رمز Redis و توکن صف job در docker-compose افتاد).
این اسکریپت تمام فایل‌های track‌شده را می‌خواند.

خروجی هرگز مقدار secret را چاپ نمی‌کند — فقط فایل:خط، نوع، و اینکه آیا
placeholder است یا واقعی‌نما (قاعدهٔ ۵).

    python scripts/scan_secrets.py --help
"""

from __future__ import annotations

import argparse
import contextlib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# stdout در محیط ویندوزی پیش‌فرض cp1252 است و گزارش فارسی/کاراکترهای غیرASCII
# آن را می‌شکند (UnicodeEncodeError). خروجی این اسکریپت گزارش است، پس UTF-8.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        with contextlib.suppress(Exception):  # noqa: BLE001 - اگر نشد، همان encoding قبلی می‌ماند
            _stream.reconfigure(encoding="utf-8", errors="replace")

# ── الگوها ───────────────────────────────────────────────────────────────
# هر tuple: (نام نوع، regex، آیا برای match شدن نیاز به entropy دارد؟)
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY-----")),
    ("aws-access-key-id", re.compile(r"\b(AKIA|ASIA|ABIA|ACLA)[0-9A-Z]{16}\b")),
    ("telegram-bot-token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("openai-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}\b")),
    ("url-with-credentials", re.compile(r"\b(?:redis|rediss|postgres|postgresql|mysql|mongodb)(?:\+\w+)?:\/\/[^\s:@/]{0,64}:([^\s@/]{6,})@", re.I)),
    (
        "secret-assignment",
        re.compile(
            r"""(?ix)
            \b(?:
              [A-Za-z0-9_]*(?:PASSWORD|PASSWD|SECRET|SALT|API_KEY|APIKEY|ACCESS_KEY|
                          AUTH_TOKEN|BOT_TOKEN|PRIVATE_KEY|CLIENT_SECRET|
                          SESSION_SECRET|SIGNING_KEY|ENCRYPTION_KEY|JOB_QUEUE_TOKEN|
                          TOKEN)
            )\b
            \s*[:=]\s*
            ["']?([A-Za-z0-9+/=_\-.]{8,})["']?
            """
        ),
    ),
    ("generic-high-entropy", re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b")),
]

# ── آنچه secret نیست ─────────────────────────────────────────────────────
# placeholderها، الگوهای تست، و ارجاع‌های env. این لیست باید با allowlist
# .gitleaks.toml هم‌خوان بماند.
PLACEVALUE = re.compile(
    r"""(?ix)
    ^\s*(?:
        your[-_][a-z0-9-]+ | change[-_]me\S* | changeme | xxx+ | <[^>]+> |
        \{\{[^}]+\}\} | \$\{[^}]+\} | %s | todo | fixme | example | sample |
        test[-_]?\w* | dummy | placeholder | secret[_-]?key[_-]?here |
        dev[-_]?shared[-_]?token | replace[-_]me
    )\s*$
    """
)
ENV_REF = re.compile(r"^\s*\$\{?[A-Za-z_][A-Za-z0-9_]*(?::[-?]=[^}]*)?\}?\s*$")
DOC_PROSE = re.compile(r"(?:example|for example|نمونه|placeholder|mask)", re.I)

# ── حذف false positiveهای کد-محور ───────────────────────────────────────
# چیزی که شبیه نام متغیر/عبارت است secret نیست: `password=hashed_password`,
# `token: NonEmptyString`, `f"{a}:{b}"`. فقط literal واقعی را می‌گیریم.
CODE_EXPRESSION = re.compile(r"""[(){}\[\],;|*/<>=!?]|\.\.\.|^\w+$""")
TYPE_WORDS = re.compile(
    r"""^(?:
        str|int|float|bool|bytes|None|True|False
      | Optional\[[^\]]*\] | list\[[^\]]*\] | dict\[[^\]]*\] | tuple\[[^\]]*\]
      | (?:self|request|settings|payload|data|row|user|obj|hashed|verify)[\w.]*
      | Field\(.+ | .*\bModel\.conf\b.*
    )$""",
    re.I | re.VERBOSE,
)
# host/cred که عمداً برای dev و CI نوشته شده‌اند
LOCAL_HOST = re.compile(r"(?:localhost|127\.0\.0\.1|0\.0\.0\.0|::1|example\.com|"
                        r"test_host|testserver|minikube|\.svc(?:\.local)?\b)", re.I)
PLACEHOLDER_URL_PARTS = re.compile(r"^(?:user|username|admin|root|postgres|quant_dev|"
                                   r"market|password|pass|secret|changeme|dev|test|"
                                   r"your[-_]?\w+|<.+>|\$.+)$", re.I)

SKIP_DIR_PARTS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build",
    ".next", "site-packages", "backups", ".pytest_cache", "coverage",
    # محتوای vendor/کپی‌شده؛ اسکن آن‌ها در گزارش ریسک اپ معنایی ندارد و
    # با --include-vendor می‌توان دیدشان. ⚠️ همهٔ entries کوچک‌اند چون parts
    # مسیر پیش از مقایسه lower() می‌شود.
    ".agents", ".claude", ".qoder", "_frontend_backend_copy", "_audit_base",
    "_base_wt", "_base_wt_clean", ".freebuff", "temce.worktrees", "temce._clean_base",
}

# زیرمجموعهٔ vendor که با --include-vendor دوباره اسکن می‌شوند
VENDOR_DIRS = {".agents", ".claude", ".qoder", "_frontend_backend_copy",
               "_audit_base", "_base_wt", "_base_wt_clean", ".freebuff",
               "temce.worktrees", "temce._clean_base"}

# قفل‌های پکیج: hash یکپارچگی (sha512) دارند و هزارها «entropy بالا» می‌سازند.
# اینها digest هستند نه credential.
LOCKFILE_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "requirements.lock", "uv.lock", "cargo.lock", "composer.lock",
    "package-lock.yaml",
}
SKIP_SUFFIX = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".tar", ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".mp4", ".webm",
    ".so", ".pyd", ".pyc", ".lock", ".min.js", ".min.css", ".map", ".ipynb",
}
MAX_BYTES = 1_500_000


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    placeholder: bool
    snippet: str
    zone: str

    def render(self) -> str:
        # هیچ کاراکتری از مقدار چاپ نمی‌شود؛ فقط طول و شکل کلی.
        tag = "PLACEHOLDER" if self.placeholder else "REAL-LOOKING"
        return f"{self.path}:{self.line}  [{self.zone}]  {self.kind:22s}  {tag}  len={len(self.snippet)}"


SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".svelte", ".vue"}
CONFIG_SUFFIXES = {".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf", ".json", ".sh", ".env", ".example"}


def candidate_files(explicit: list[str] | None) -> list[Path]:
    if explicit:
        # --files می‌تواند دایرکتوری بدهد؛ باید باز شود. نسخهٔ قبل فقط فایل‌های
        # صریح را می‌گرفت و با دایرکتوری **هیچ** چیزی اسکن نمی‌کرد (صفر کاذب).
        collected: list[Path] = []
        for raw in explicit:
            p = Path(raw)
            if p.is_dir():
                collected.extend(q for q in p.rglob("*") if q.is_file())
            elif p.is_file():
                collected.append(p)
        return collected
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], capture_output=True, check=True
        ).stdout
        names = [n for n in out.split(b"\0") if n]
        return [Path(n.decode("utf-8", "replace")) for n in names]
    except Exception:
        return [p for p in Path(".").rglob("*") if p.is_file()]


def looks_secret(value: str) -> bool:
    """entropy نهایی: کاراکتر منحصر‌به‌فرد زیاد + بدون فاصله/الگوی انسانی."""
    if len(value) < 12:
        return False
    uniq = len(set(value))
    return uniq / len(value) >= 0.55


def zone_of(path: Path) -> str:
    parts = {p.lower() for p in path.parts}
    first = path.parts[0].lower() if path.parts else ""
    if "docs" in parts or first == "docs" or path.suffix == ".md":
        return "docs"
    if "tests" in parts or "test" in first or first.startswith("test"):
        return "tests"
    if first == ".github":
        return "ci"
    if first in {"src", "apps", "core", "domain", "services", "jobs", "models",
                 "repositories", "providers", "ingestion", "orchestration", "brsapi",
                 "backtesting", "ml", "monitoring", "integrations", "contracts", "config"}:
        return "app"
    if first == "frontend":
        return "frontend"
    return "root"


def is_quoted_literal(line: str, value: str) -> bool:
    """literal واقعاً داخل نقل‌قول باشد: `"sk-..."` یا `'abc'`."""
    return f'"{value}"' in line or f"'{value}'" in line


# fixtureهای تستی: tokenهای ساختگی. فقط این مسیرها؛ همان رشته در کد اپ باید بگیرد.
# (هم‌خوان با [allowlist].paths در .gitleaks.toml)
ALLOW_PATHS = re.compile(
    r"""(?ix)
    (?:
      (^|/)frontend/src/__tests__/
    | (^|/)frontend/src/.*\.(test|spec)\.(ts|tsx)$
    | (^|/)tests/.*test.*\.py$
    | (^|/)tests/test_.*\.(bat|sh|ps1)$
    | (^|/)\.gitleaks\.toml$          # خودِ config، الگو دارد نه secret
    | (^|/)scripts/scan_secrets\.py$ # این اسکریپت، regex دارد نه secret
    )
    """
)


def scan_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    if not path.is_file():
        return findings
    try:
        if path.stat().st_size > MAX_BYTES:
            return findings
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings
    if path.suffix.lower() in SKIP_SUFFIX:
        return findings
    # digest قفل‌های پکیج (sha512) نه credential است نه ریسک؛ کل فایل رد می‌شود
    if path.name.lower() in LOCKFILE_NAMES:
        return findings

    suffix = path.suffix.lower()
    zone = zone_of(path)
    normalized = str(path).replace("\\", "/")
    # fixture تستی و خودِ ابزار اسکن: real-LOOKING نیستند، اما با
    # --include-placeholders دیده می‌شوند.
    path_allowed = bool(ALLOW_PATHS.search(normalized))

    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        for kind, pattern in PATTERNS:
            for match in pattern.finditer(line):
                value = match.group(match.lastindex or 0) if match.groups() else match.group(0)
                if value is None:
                    value = match.group(0)

                if path_allowed or PLACEVALUE.match(value) or ENV_REF.match(value) or DOC_PROSE.search(stripped):
                    findings.append(Finding(normalized, lineno, kind, True, value, zone))
                    continue

                if kind == "url-with-credentials":
                    # urlهای dev/CI با host لوکال یا cred آشکارا نمونه‌ای
                    if LOCAL_HOST.search(line) or PLACEHOLDER_URL_PARTS.match(value):
                        continue
                    if looks_secret(value) or len(value) >= 6:
                        findings.append(Finding(str(path).replace("\\", "/"), lineno, kind, False, value, zone))
                    continue

                if kind == "secret-assignment":
                    if TYPE_WORDS.match(value) or not looks_secret(value):
                        continue
                    if CODE_EXPRESSION.search(value):
                        continue
                    # در کد فقط literal داخل نقل‌قول؛ در config مقدار bare هم هست
                    if suffix in SOURCE_SUFFIXES and not is_quoted_literal(line, value):
                        continue
                    findings.append(Finding(str(path).replace("\\", "/"), lineno, kind, False, value, zone))
                    continue

                if kind == "generic-high-entropy":
                    if not looks_secret(value):
                        continue
                    if zone in {"docs", "tests"}:
                        continue
                    findings.append(Finding(str(path).replace("\\", "/"), lineno, kind, False, value, zone))
                    continue

                findings.append(Finding(str(path).replace("\\", "/"), lineno, kind, False, value, zone))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-placeholders", action="store_true",
                       help="placeholderها را هم نشان بده (پیش‌فرض: فقط واقعی‌نما)")
    parser.add_argument("--include-vendor", action="store_true",
                       help="پوشه‌های vendor/کپی‌شده (.agents, _FRONTEND_BACKEND_COPY, …) را هم اسکن کن")
    parser.add_argument("--files", nargs="*", help="فقط این مسیرها (پیش‌فرض: git ls-files)")
    parser.add_argument("--exclude", action="append", default=[], metavar="REGEX",
                       help="مسیرهای منطبق بر این regex رد شوند (قابل تکرار). "
                            "برای فایل‌هایی که در محدودهٔ مالکیت این اسکریپت نیست "
                            "استفاده کنید، نه برای پنهان‌کردن secret.")
    parser.add_argument("--fail-on-real", action="store_true",
                       help="اگر حتی یک مورد واقعی‌نما پیدا شد، کد خروج ۱")
    args = parser.parse_args(argv)

    excludes = []
    for pattern in args.exclude:
        try:
            excludes.append(re.compile(pattern))
        except re.error as exc:
            print(f"--exclude نامعتبر: {pattern} ({exc})")
            return 2

    real: list[Finding] = []
    placeholders: list[Finding] = []
    skipped: list[str] = []
    for f in candidate_files(args.files):
        normalized = str(f).replace("\\", "/")
        if any(rx.search(normalized) for rx in excludes):
            skipped.append(normalized)
            continue
        parts = {part.lower() for part in f.parts}
        skip_dirs = SKIP_DIR_PARTS if not args.include_vendor else SKIP_DIR_PARTS - VENDOR_DIRS
        if parts & skip_dirs:
            continue

        for finding in scan_file(f):
            (placeholders if finding.placeholder else real).append(finding)

    if real:
        by_zone: dict[str, int] = {}
        for f in real:
            by_zone[f.zone] = by_zone.get(f.zone, 0) + 1
        print(f"=== {len(real)} مورد واقعی‌نما (مقدارها چاپ نمی‌شود) ===")
        print("تفکیک منطقه: " + ", ".join(f"{z}={n}" for z, n in sorted(by_zone.items())))
        for zone in ("app", "root", "ci", "frontend", "tests", "docs"):
            group = [f for f in real if f.zone == zone]
            if not group:
                continue
            print(f"\n--- {zone} ({len(group)}) ---")
            for f in group:
                print(f.render())
    else:
        print("=== هیچ مورد واقعی‌نما در درخت track‌شده پیدا نشد ===")

    if args.include_placeholders and placeholders:
        print(f"\n=== {len(placeholders)} placeholder (رد شدند) ===")
        for f in placeholders[:200]:
            print(f.render())
        if len(placeholders) > 200:
            print(f"... و {len(placeholders) - 200} مورد دیگر")

    if skipped:
        # انصاف: هر رد شدن باید قابل دیدن باشد، وگرنه --exclude راهی برای
        # پنهان‌کردن نشت می‌شود.
        print(f"\n=== {len(skipped)} فایل با --exclude رد شد ===")
        for path in skipped[:40]:
            print(f"  skipped: {path}")
        if len(skipped) > 40:
            print(f"  ... و {len(skipped) - 40} مورد دیگر")

    if args.fail_on_real and real:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
