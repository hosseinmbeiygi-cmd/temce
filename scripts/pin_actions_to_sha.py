#!/usr/bin/env python3
"""Pin GitHub Actions to commit SHAs (audit TST-011).

Rewrites ``uses: owner/repo@tag`` to ``uses: owner/repo@<full-sha> # tag``
across all workflow files, resolving tags via the GitHub API. Actions already
pinned to a full 40-char SHA are left untouched.

Usage:
    python scripts/pin_actions_to_sha.py          # rewrite in place
    python scripts/pin_actions_to_sha.py --check  # exit 1 if any unpinned

Requires: GITHUB_TOKEN (optional, raises rate limits) and network access.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

GITHUB_API = "https://api.github.com"
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
USE_PATTERN = re.compile(r"(\buses:\s*)(['\"]?)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([^\s'\"#]+)\2(.*)")

_token = os.getenv("GITHUB_TOKEN", "")


def resolve_sha(repo: str, ref: str) -> str | None:
    """Resolve a tag/branch to its full commit SHA via the GitHub API."""
    url = f"{GITHUB_API}/repos/{repo}/commits/{ref}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if _token:
        req.add_header("Authorization", f"Bearer {_token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
        return data["sha"]
    except Exception as exc:  # noqa: BLE001
        print(f"  !! could not resolve {repo}@{ref}: {exc}", file=sys.stderr)
        return None


def process_file(path: Path, check_only: bool) -> bool:
    """Return True when the file is fully pinned after processing."""
    text = path.read_text(encoding="utf-8")
    changed = False
    all_pinned = True

    def _sub(match: re.Match[str]) -> str:
        nonlocal changed, all_pinned
        uses_kw, _quote, repo, ref, tail = match.groups()
        if SHA_PATTERN.match(ref):
            return match.group(0)
        all_pinned = False
        if check_only:
            print(f"  unpinned: {repo}@{ref} ({path.name})")
            return match.group(0)
        sha = resolve_sha(repo, ref)
        if sha is None:
            return match.group(0)
        changed = True
        print(f"  pinned {repo}@{ref} -> {sha[:12]}... ({path.name})")
        return f"{uses_kw}{repo}@{sha} # {ref}{tail}"

    new_text = USE_PATTERN.sub(_sub, text)
    if not check_only and changed:
        path.write_text(new_text, encoding="utf-8")
    return all_pinned


def main() -> int:
    check_only = "--check" in sys.argv
    workflows = sorted(Path(".github/workflows").glob("*.yml"))
    if not workflows:
        print("No workflow files found")
        return 0

    print(f"{'CHECK' if check_only else 'PIN'} - {len(workflows)} workflow files\n")
    ok = True
    for wf in workflows:
        print(f"- {wf}")
        if not process_file(wf, check_only):
            ok = False

    if check_only:
        print("\nRESULT:", "ALL PINNED [OK]" if ok else "UNPINNED ACTIONS FOUND [FAIL]")
        return 0 if ok else 1
    print("\nDone. Review the diff and commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
