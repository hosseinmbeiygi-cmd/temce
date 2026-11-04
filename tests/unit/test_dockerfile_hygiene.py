"""Regression tests for the Dockerfile hygiene fixes (TST-021/022/023/025/026/028/029).

Invariants enforced:
  TST-021  every FROM pins a base image digest
  TST-022  no `COPY . .` wholesale copy in any Dockerfile
  TST-023  every image ends with a non-root USER (or never had root)
  TST-025  python images install from requirements.lock, not requirements.txt
  TST-028  build tools (gcc/libpq-dev) never ship in a single-stage runtime
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PYTHON_DOCKERFILES = [
    "Dockerfile",
    "Dockerfile.admin",
    "Dockerfile.api",
    "Dockerfile.currency",
    "Dockerfile.decision-engine",
    "Dockerfile.golddesk",
    "Dockerfile.scheduler",
    "Dockerfile.worker",
]
ALL_DOCKERFILES = PYTHON_DOCKERFILES + [
    "Dockerfile.frontend",
    "frontend/Dockerfile.dev",
]


def _read(name: str) -> str:
    return (REPO_ROOT / name).read_text(encoding="utf-8")


def _logical_lines(text: str) -> list[str]:
    """Return Dockerfile instructions with line continuations joined."""
    joined: list[str] = []
    buf = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if not buf:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
        buf += (" " if buf else "") + line
        if buf.rstrip().endswith("\\"):
            buf = buf.rstrip()[:-1]
            continue
        joined.append(buf.strip())
        buf = ""
    if buf.strip():
        joined.append(buf.strip())
    return joined


def test_all_base_images_pinned_by_digest() -> None:
    for name in ALL_DOCKERFILES:
        for line in _logical_lines(_read(name)):
            if line.upper().startswith("FROM "):
                assert "@sha256:" in line, f"{name}: unpinned base image -> {line}"


#: `COPY . .` and every spelling of it: flags (`--chown=`, `--link`) and
#: trailing slashes (`. ./`, `./ .`) must not slip past the guard.
_WHOLESALE_COPY = re.compile(r"^COPY\s+(?:--\S+\s+)*\./?\s+\./?\s*$", re.IGNORECASE)


def _wholesale_copies(dockerfile: str) -> list[str]:
    return [ln for ln in _logical_lines(dockerfile) if _WHOLESALE_COPY.match(ln)]


def test_no_wholesale_copy_dot() -> None:
    for name in ALL_DOCKERFILES:
        found = _wholesale_copies(_read(name))
        assert not found, f"{name}: copies the whole build context -> {found[0]}"


def test_wholesale_copy_matcher_catches_flag_and_slash_variants() -> None:
    for directive in (
        "COPY . .",
        "COPY . ./",
        "COPY ./ .",
        "COPY --chown=app:app . .",
        "COPY --link . .",
        "copy --chown=app:app --link . .",
    ):
        assert _wholesale_copies(directive), directive
    for directive in (
        "COPY apps/ ./apps/",
        "COPY --from=builder /root/.local /home/app/.local",
        "COPY *.py ./",
        "COPY .dockerignore ./",
    ):
        assert not _wholesale_copies(directive), directive


def test_python_images_install_from_lock() -> None:
    for name in PYTHON_DOCKERFILES:
        text = _read(name)
        assert "requirements.lock" in text, f"{name}: does not install from requirements.lock"
        assert "-r requirements.txt" not in text, f"{name}: still installs from requirements.txt"


def test_every_image_runs_as_non_root() -> None:
    for name in ALL_DOCKERFILES:
        stages: list[list[str]] = [[]]
        for line in _logical_lines(_read(name)):
            if line.upper().startswith("FROM "):
                stages.append([])
            else:
                stages[-1].append(line)
        # Only the final stage becomes the shipped image; builder stages may
        # legitimately run as root.
        final = stages[-1]
        users = [ln for ln in final if ln.upper().startswith("USER ")]
        last = users[-1].split()[-1] if users else "root"
        assert last not in {"root", "0"}, f"{name}: final stage runs as root"


def test_no_build_tools_in_single_stage_runtime() -> None:
    # GoldDesk used to install gcc/libpq-dev in its only stage and run from it.
    for name in PYTHON_DOCKERFILES:
        stages: list[list[str]] = [[]]
        for line in _logical_lines(_read(name)):
            if line.upper().startswith("FROM "):
                stages.append([])
            else:
                stages[-1].append(line)
        multi_stage = len(stages) > 1
        if not multi_stage:
            joined = " ".join(stages[0]).lower()
            assert "gcc" not in joined and "libpq-dev" not in joined, (
                f"{name}: build tools installed in the (only) runtime stage"
            )


def test_requirements_lock_is_fully_pinned() -> None:
    lock = (REPO_ROOT / "requirements.lock").read_text(encoding="utf-8")
    for line in lock.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-", "via")):
            continue
        assert "==" in line, f"requirements.lock has unpinned entry: {line}"


def test_frontend_images_use_npm_ci() -> None:
    for name in ("Dockerfile.frontend", "frontend/Dockerfile.dev"):
        text = _read(name)
        assert "npm ci" in text, f"{name}: must use deterministic `npm ci`"


def test_dockerignore_excludes_secrets_and_dev_artifacts() -> None:
    lines = {
        ln.strip()
        for ln in (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    }
    # Every `.env` variant must be ignored: a stray file in the context is one
    # `COPY` away from being baked into a layer.
    assert {".env", ".env.*", "*.env"} <= lines
    for artifact in ("tests/", "unit_scan_logs/", "*.db", "*.rdb"):
        assert artifact in lines, f".dockerignore must exclude {artifact}"


def test_dockerignore_covers_the_env_family() -> None:
    """`.env.production` and `.env.bak.*` must never reach a `COPY . .` layer.

    These are untracked, gitignored local files, so nothing else keeps them out of
    the build context. The original `.env` / `.env.*.local` pair missed them.
    """
    patterns = [
        ln.strip()
        for ln in _read(".dockerignore").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]

    def ignored(path: str) -> bool:
        """Docker-ish match for top-level context entries."""
        for pat in patterns:
            negated = pat.startswith("!")
            p = (pat[1:] if negated else pat).lstrip("/").rstrip("/")
            if fnmatch.fnmatch(path, p) or fnmatch.fnmatch(path, p + "/*"):
                return True
        return False

    for name in (
        ".env",
        ".env.local",
        ".env.production",
        ".env.staging",
        ".env.bak.1790980646",
    ):
        assert ignored(name), f".dockerignore does not exclude {name}"

    # Negative control: the fix must not have swept in files the images need.
    for keep in ("requirements.lock", "pyproject.toml", "alembic.ini"):
        assert not ignored(keep), f".dockerignore wrongly excludes {keep}"
