#!/usr/bin/env python
"""Ratchet gate for mypy and import-linter.

Snapshot the current debt once, then fail only when a violation grows.
mypy keys are (file, error-code) — line numbers are dropped on purpose so
refactors do not churn the baseline. Import-linter keys are contract names.

Exit codes: 0 = no regression, 1 = regression, 2 = the tool itself failed
(a broken gate must never read as a pass).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_DEFAULT = ROOT / "ci" / "quality_baseline.json"

PROFILES: dict[str, dict] = {
    # The old CI step passed ``domain`` while it was in [tool.mypy].exclude,
    # which made mypy exit 2 ("no .py files in directory") under ``|| true``.
    # --explicit-package-bases is required because apps/ has no __init__.py.
    "mypy": {
        "cmd": [
            "mypy", "apps", "core", "services", "domain",
            "--explicit-package-bases", "--ignore-missing-imports",
            "--no-error-summary",
        ],
        "kind": "mypy",
    },
    "mypy-strict-gold": {
        "cmd": [
            "mypy", "src/gold_desk", "--strict",
            "--explicit-package-bases", "--ignore-missing-imports",
            "--no-error-summary",
        ],
        "kind": "mypy",
    },
    "imports": {
        "cmd": ["lint-imports", "--config", str(ROOT / ".importlinter")],
        "kind": "imports",
    },
}

MYPY_ERROR_RE = re.compile(
    r"^(?P<path>.+?):\d+: (?:error|warning): .*\[(?P<code>[a-z-]+)\]$"
)


def run(profile: str) -> tuple[int, str]:
    proc = subprocess.run(
        PROFILES[profile]["cmd"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def parse_mypy(output: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in output.splitlines():
        match = MYPY_ERROR_RE.match(line.strip())
        if not match:
            continue
        path = match.group("path").replace("\\", "/").lower()
        key = f"{path}|{match.group('code')}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def parse_imports(output: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    current: str | None = None
    lines = output.splitlines()
    for index, line in enumerate(lines):
        underline = index + 1 < len(lines) and set(lines[index + 1].strip()) == {"-"}
        if underline and line.strip():
            current = line.strip()
            counts.setdefault(current, 0)
            continue
        if current and line.startswith("-   "):
            counts[current] += 1
    return counts


def collect(profile: str) -> dict[str, int]:
    code, output = run(profile)
    if "No matches for ignored import" in output:
        raise SystemExit(
            "import-linter config is stale (an ignore_imports entry matches nothing):\n"
            + output
        )
    if code not in (0, 1):
        raise SystemExit(f"{profile}: tool failed (exit {code}):\n{output}")
    counts = (
        parse_mypy(output)
        if PROFILES[profile]["kind"] == "mypy"
        else parse_imports(output)
    )
    if code == 1 and not counts:
        raise SystemExit(f"{profile}: exit 1 with no parsed violations:\n{output}")
    return counts


def load(path: Path) -> dict[str, dict[str, int]]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def snapshot(args: argparse.Namespace) -> int:
    baseline = load(args.out)
    for profile in args.tool:
        baseline[profile] = collect(profile)
        print(
            f"snapshot {profile}: {len(baseline[profile])} keys, "
            f"{sum(baseline[profile].values())} violations"
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.out}")
    return 0


def check(args: argparse.Namespace) -> int:
    baseline = load(args.out)
    failures = 0
    for profile in args.tool:
        if profile not in baseline:
            raise SystemExit(f"no baseline for {profile}; run snapshot first")
        current = collect(profile)
        previous = baseline[profile]
        new = {
            key: value
            for key, value in current.items()
            if value > previous.get(key, 0)
        }
        removed = sorted(set(previous) - set(current))
        if new:
            failures += 1
            print(f"{profile}: NEW violations ({len(new)}):", file=sys.stderr)
            for key, value in sorted(new.items()):
                print(
                    f"  {key} -> {value} (baseline {previous.get(key, 0)})",
                    file=sys.stderr,
                )
        total_now, total_before = sum(current.values()), sum(previous.values())
        if total_now > total_before and not new:
            failures += 1
            print(
                f"{profile}: total grew {total_before} -> {total_now} without a new key",
                file=sys.stderr,
            )
        if removed:
            print(
                f"{profile}: {len(removed)} baseline entries no longer occur — "
                "re-run snapshot to shrink the baseline"
            )
        if not new and total_now <= total_before:
            print(f"{profile}: OK ({total_now} violations, baseline {total_before})")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("snapshot", snapshot), ("check", check)):
        cmd = sub.add_parser(name)
        cmd.add_argument(
            "--tool", action="append", choices=sorted(PROFILES), required=True
        )
        cmd.add_argument("--out", type=Path, default=BASELINE_DEFAULT)
        cmd.set_defaults(handler=handler)
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
