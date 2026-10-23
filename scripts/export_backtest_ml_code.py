#!/usr/bin/env python
"""Dump the complete backtest source and the complete ML source of this repo to txt.

Creates, in the repository root by default:

    BACKTEST_ALL_CODE.txt   every backtesting/** file + every backtest-named file
    ML_ALL_CODE.txt         the whole ml/** package + every ML-named file

Each dump carries a manifest (repo, commit, date, file count, size, include rules),
a full table of contents, one ``FILE n/N: <path>`` block per file holding the file
verbatim (original bytes, CRLF preserved), and a footer with a SHA-256 prefix per
file so the dump can be checked against the working tree.

Selection rules (identical to what ``scripts/verify_backtest_ml_code_dump.py``
re-implements independently):

* file list comes from ``git ls-files`` — tracked files only, .gitignore respected;
* BACKTEST set: everything under ``backtesting/`` plus every tracked file whose path
  contains ``backtest`` (case-insensitive);
* ML set: everything under ``ml/`` plus every tracked file whose path has an ``ml``
  directory segment or an ``ml.py`` / ``ml_*.py`` name;
* source/text extensions only; generated artefacts and vendored copies are skipped
  (``_FRONTEND_BACKEND_COPY/``, ``audit_out/``, ``reports/``).

Usage:
    python scripts/export_backtest_ml_code.py
    python scripts/export_backtest_ml_code.py --only ml
    python scripts/export_backtest_ml_code.py --out-dir docs/code_dumps
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from datetime import date

CODE_EXT = (".py", ".ts", ".tsx", ".md", ".yaml", ".yml", ".toml", ".sql", ".cfg", ".ini", ".sh")
EXCLUDE_PREFIX = ("_FRONTEND_BACKEND_COPY/", "audit_out/", "reports/", "node_modules/")

ML_RE = re.compile(
    r"(^|/)ml/"  # .../ml/... directory segment
    r"|(^|[/_])ml\.[a-z0-9]+$"  # ml.py, ml.tsx, ml.md
    r"|(^|[/_])ml_[a-z0-9_]+\.[a-z0-9]+$"  # ml_*.py, test_ml_*.py, 0004_ml_*.py
)

SEP = "=" * 100


def repo_root() -> str:
    """Repository root, resolved from this file and verified through git."""
    here = os.path.dirname(os.path.abspath(__file__))
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=here,
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode == 0 and out.stdout.strip():
        return os.path.abspath(out.stdout.strip())
    return os.path.dirname(here)


ROOT = repo_root()


def git(args: list[str]) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True).stdout


def tracked_files() -> list[str]:
    return git(["ls-files"]).splitlines()


def excluded(path: str) -> bool:
    return path.startswith(EXCLUDE_PREFIX)


def select_backtest(files: list[str]) -> list[str]:
    return [
        p
        for p in files
        if not excluded(p)
        and p.lower().endswith(CODE_EXT)
        and (p.startswith("backtesting/") or "backtest" in p.lower())
    ]


def select_ml(files: list[str]) -> list[str]:
    return [
        p
        for p in files
        if not excluded(p) and p.lower().endswith(CODE_EXT) and (p.startswith("ml/") or ML_RE.search(p))
    ]


def read_source(rel: str) -> tuple[str, str]:
    """Return (text, encoding note). Source is never altered; CRLF is kept."""
    with open(os.path.join(ROOT, rel.replace("/", os.sep)), "rb") as fh:
        raw = fh.read()
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("latin-1"), "latin-1 (not valid utf-8)"


def ext_counts(paths: list[str]) -> str:
    counts: dict[str, int] = {}
    for path in paths:
        ext = os.path.splitext(path)[1] or "(none)"
        counts[ext] = counts.get(ext, 0) + 1
    return ", ".join(f"{ext} {n}" for ext, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def dump(target_dir: str, target: str, title: str, scope_lines: list[str], paths: list[str]) -> int:
    paths = sorted(paths)
    total_bytes = 0
    blocks: list[str] = []
    enc_notes: list[str] = []
    digests: list[str] = []

    for i, rel in enumerate(paths, start=1):
        text, note = read_source(rel)
        raw_bytes = len(text.encode("utf-8", errors="replace"))
        total_bytes += raw_bytes
        if note != "utf-8":
            enc_notes.append(f"{rel} -> {note}")
        digests.append(f"{hashlib.sha256(text.encode('utf-8', 'replace')).hexdigest()[:12]}  {rel}")
        line_count = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
        blocks.append(
            f"\n{SEP}\n"
            f"FILE {i}/{len(paths)}: {rel}\n"
            f"{SEP}\n"
            f"# bytes={raw_bytes}  lines={line_count}\n"
            f"{SEP}\n\n"
            f"{text}" + ("" if text.endswith("\n") else "\n")
        )

    header = [
        SEP,
        title,
        SEP,
        f"Repository : {os.path.basename(ROOT)}  ({ROOT.replace(os.sep, '/')})",
        f"Git commit : {git(['rev-parse', '--short', 'HEAD']).strip()}",
        f"Exported   : {date.today().isoformat()}",
        "Exporter   : scripts/export_backtest_ml_code.py",
        f"Files      : {len(paths)}",
        f"Extensions : {ext_counts(paths)}",
        f"Source size: {total_bytes:,} bytes ({total_bytes / 1024 / 1024:.2f} MiB)",
        "Contents   : complete, unmodified source of every file listed below.",
        "Format     : for each file a header 'FILE n/N: <path>' then the full file body.",
        "             Original line endings (CRLF) are preserved; bodies are UTF-8.",
        "",
        "Scope / include rules",
        "---------------------",
        *[f"    {line.strip()}" if line.startswith("  ") else f"  - {line}" for line in scope_lines],
        "",
        "Excluded on purpose (generated / vendored data, not source):",
        "  - _FRONTEND_BACKEND_COPY/**  (byte copy of the backend)",
        "  - audit_out/**               (audit logs, .out/.json dumps, scratch scripts)",
        "  - reports/**                 (screenshots, generated reports)",
        "  - every non source extension (.json, .png, .csv, .pyc, ...)",
        "",
        "Table of contents (sorted by path)",
        "---------------------------------",
        *[f"  {i:>4}. {p}" for i, p in enumerate(paths, start=1)],
        "",
    ]
    if enc_notes:
        header += ["Files not valid UTF-8 (dumped as latin-1):", *[f"  - {n}" for n in enc_notes], ""]

    footer = [
        "",
        SEP,
        "END OF EXPORT",
        f"{len(paths)} files, {total_bytes:,} bytes of source.",
        SEP,
        "",
        "SHA-256 (first 12 hex chars) of every dumped file body, for integrity checks:",
        *[f"  {d}" for d in digests],
        "",
    ]

    out_path = os.path.join(target_dir, target)
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(header))
        for block in blocks:
            fh.write(block)
        fh.write("\n".join(footer))

    print(f"{target}: {len(paths)} files, source {total_bytes:,} bytes, txt {os.path.getsize(out_path):,} bytes")
    return total_bytes


BACKTEST_SCOPE = [
    "everything under backtesting/** (engine, execution, costs, metrics, strategies, alpha,",
    "  optimization, scenarios, reporting, ABM / hybrid / microstructure simulators, ...)",
    "every tracked file whose path contains 'backtest' (case-insensitive) outside the copy dir:",
    "  core/config, models, schemas, repositories, services, jobs, orchestration, apps/api,",
    "  scripts, tests, frontend/src/app/backtest/**, docs/**",
]

ML_SCOPE = [
    "everything under ml/** (datasets, features, models shallow+deep+ensembles, training,",
    "  evaluation, inference, artifacts, registries, policies)",
    "ML integration points: apps/api/endpoints/ml.py, core/{config,constants,exceptions}/ml.py,",
    "  domain/ml/**, models/ml.py, schemas/ml/**, schemas/{api,admin}/ml*.py, jobs/definitions/ml_jobs.py,",
    "  repositories/ml_repository.py, migrations/*ml*.py",
    "ML entry points and glue: scripts/*ml*.py, services/ml_*.py, services/options_ml_service.py",
    "ML tests: tests/unit/ml/**, tests/**/test_ml_*.py, tests/fixtures/sample_ml_runs.py",
    "ML strategy/frontend glue: backtesting/strategies/ml_based/**, frontend/src/app/ml/**",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dump backtest / ML source trees into txt files.")
    parser.add_argument("--out-dir", default=ROOT, help="output directory (default: repo root)")
    parser.add_argument("--only", choices=("all", "backtest", "ml"), default="all", help="which dump to regenerate")
    args = parser.parse_args(argv)

    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    files = tracked_files()
    if args.only in ("all", "backtest"):
        dump(
            out_dir,
            "BACKTEST_ALL_CODE.txt",
            "FULL BACKTEST SOURCE EXPORT — backtesting package + every backtest-named file",
            BACKTEST_SCOPE,
            select_backtest(files),
        )
    if args.only in ("all", "ml"):
        dump(
            out_dir,
            "ML_ALL_CODE.txt",
            "FULL ML SOURCE EXPORT — ml package + every ML-named file",
            ML_SCOPE,
            select_ml(files),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
