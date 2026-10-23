#!/usr/bin/env python
"""Verify the txt dumps produced by ``scripts/export_backtest_ml_code.py``.

The selection rules are re-implemented here on purpose instead of imported from the
exporter: if the exporter's rules ever drift, the dumped path list stops matching
what this checker derives from ``git ls-files`` and the run fails.

Checks per dump:
  1. title banner, manifest count and table of contents are present;
  2. exactly one END OF EXPORT footer;
  3. block count equals the independently selected file set (and the header count);
  4. block numbering is 1..N with a constant N, paths sorted and gap-free;
  5. every block body is byte-identical to the file in the working tree
     (plus the separator newlines the format adds), and the declared byte count
     equals the on-disk size;
  6. the footer carries one SHA-256 prefix per file, matching the file bodies.

Exit status: 0 when every check passes, 1 otherwise.

Usage:
    python scripts/verify_backtest_ml_code_dump.py
    python scripts/verify_backtest_ml_code_dump.py --dir docs/code_dumps
    python scripts/verify_backtest_ml_code_dump.py --only ml --dir out
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys

CODE_EXT = (".py", ".ts", ".tsx", ".md", ".yaml", ".yml", ".toml", ".sql", ".cfg", ".ini", ".sh")
EXCLUDE_PREFIX = ("_FRONTEND_BACKEND_COPY/", "audit_out/", "reports/", "node_modules/")
SEP = "=" * 100

ML_RE = re.compile(r"(^|/)ml/|(^|[/_])ml\.[a-z0-9]+$|(^|[/_])ml_[a-z0-9_]+\.[a-z0-9]+$")

# '=' * 100 / FILE n/N: <path> / '=' * 100 / '# bytes=..  lines=..' / '=' * 100 / blank
HDR = re.compile(r"={100}\nFILE (\d+)/(\d+): (.+?)\n={100}\n# bytes=(\d+)  lines=(\d+)\n={100}\n\n")

failures: list[str] = []


def repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=here, capture_output=True, text=True, check=False)
    if out.returncode == 0 and out.stdout.strip():
        return os.path.abspath(out.stdout.strip())
    return os.path.dirname(here)


ROOT = repo_root()


def note(ok: bool, msg: str) -> None:
    print(("  OK   " if ok else "  FAIL ") + msg)
    if not ok:
        failures.append(msg)


def expected_paths(kind: str) -> list[str]:
    """Independently re-derive the file set the exporter is supposed to dump."""
    files = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout.splitlines()
    keep = [p for p in files if not p.startswith(EXCLUDE_PREFIX) and p.lower().endswith(CODE_EXT)]
    if kind == "backtest":
        return sorted(p for p in keep if p.startswith("backtesting/") or "backtest" in p.lower())
    return sorted(p for p in keep if p.startswith("ml/") or ML_RE.search(p))


def check_dump(dump: str, expect: list[str], out_dir: str) -> None:
    print(f"\n=== {dump} ===")
    path = os.path.join(out_dir, dump)
    if not os.path.exists(path):
        note(False, f"{dump} exists")
        return
    note(True, f"{dump} exists ({os.path.getsize(path):,} bytes)")

    with open(path, encoding="utf-8", newline="") as fh:
        content = fh.read()

    note(content.startswith(SEP + "\nFULL "), "dump starts with its title banner")
    note("Table of contents (sorted by path)" in content, "table of contents present")
    note(f"Files      : {len(expect)}" in content, f"manifest claims {len(expect)} files")
    note("END OF EXPORT" in content, "dump carries the END OF EXPORT footer")
    note(content.count("END OF EXPORT") == 1, "END OF EXPORT appears exactly once")

    matches = list(HDR.finditer(content))
    note(len(matches) == len(expect), f"block count {len(matches)} == expected {len(expect)}")

    paths = [m.group(3) for m in matches]
    note(paths == sorted(expect), "dumped paths equal the independently selected set, sorted")
    note(
        [int(m.group(1)) for m in matches] == list(range(1, len(matches) + 1)),
        "block numbering is 1..N without gaps",
    )
    note(
        all(int(m.group(2)) == len(matches) for m in matches),
        "every block header shows the same total N",
    )

    footer_at = content.index("\n" + SEP + "\nEND OF EXPORT")
    bodies_ok = 0
    sizes_ok = True
    digests_ok = True
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else footer_at
        body = content[m.end() : end]
        rel = m.group(3)
        with open(os.path.join(ROOT, rel.replace("/", os.sep)), "rb") as fh:
            raw = fh.read()
        try:
            decoded = raw.decode("utf-8")
        except UnicodeDecodeError:
            decoded = raw.decode("latin-1")
        # separators: '\n' before the next header, plus '\n' when the source did
        # not end with a newline; the last block ends at the footer separator.
        extra = "" if i + 1 == len(matches) else ("\n" if decoded.endswith("\n") else "\n\n")
        if body != decoded + extra:
            note(False, f"body mismatch for {rel} (disk {len(decoded)}B, body {len(body)}B)")
            continue
        bodies_ok += 1
        if int(m.group(4)) != len(raw):
            sizes_ok = False
            note(False, f"declared byte count differs from disk for {rel}")
        digest = hashlib.sha256(decoded.encode("utf-8", "replace")).hexdigest()[:12]
        if f"  {digest}  {rel}" not in content:
            digests_ok = False
            note(False, f"footer digest missing/incorrect for {rel}")

    note(bodies_ok == len(matches), f"{bodies_ok} bodies byte-identical to the working tree")
    note(sizes_ok, "declared byte counts match on-disk sizes")
    note(digests_ok, "footer digests match the file bodies")
    tail = content[footer_at:]
    digest_lines = [line for line in tail.splitlines() if re.match(r"^  [0-9a-f]{12}  ", line)]
    note(len(digest_lines) == len(expect), f"footer carries {len(digest_lines)} digests (1 per file)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the backtest/ML code dumps.")
    parser.add_argument("--dir", default=ROOT, help="directory holding the dumps (default: repo root)")
    parser.add_argument("--only", choices=("all", "backtest", "ml"), default="all", help="which dump to verify")
    args = parser.parse_args(argv)
    out_dir = os.path.abspath(args.dir)

    targets = (("BACKTEST_ALL_CODE.txt", "backtest"), ("ML_ALL_CODE.txt", "ml"))
    for dump, kind in targets:
        if args.only in ("all", kind):
            check_dump(dump, expected_paths(kind), out_dir)

    if failures:
        print(f"\n{len(failures)} FAILURES")
        return 1
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
