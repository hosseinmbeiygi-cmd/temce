"""Contract tests for the queue worker entrypoint and job registration.

The worker container previously started ``apps.worker.app`` as a module.
That module only defines ``WorkerApp`` and has no ``__main__`` runner, so the
process imported the class and exited with status 0. No queue message was
ever consumed, yet nothing failed loudly. These tests pin the two things that
made the failure silent: the container command and the per-process job
registration that the dispatcher depends on.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _dockerfile_cmd(path: Path) -> list[str]:
    for line in path.read_text(encoding="utf-8").splitlines():
        # Only top-level instructions count; the HEALTHCHECK body also
        # contains an indented ``CMD ...`` fragment.
        if line.startswith("CMD "):
            return json.loads(line[4:])
    raise AssertionError(f"{path.name} has no CMD instruction")


def test_worker_image_runs_package_entrypoint():
    """The image must run ``python -m apps.worker``, not the bare app module."""
    cmd = _dockerfile_cmd(REPO_ROOT / "Dockerfile.worker")
    assert cmd == ["python", "-m", "apps.worker"], cmd


def test_worker_package_entrypoint_starts_worker_app():
    """``apps/worker/__main__.py`` must actually drive ``WorkerApp``."""
    source = (REPO_ROOT / "apps" / "worker" / "__main__.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    called_attrs = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "run" in called_attrs
    assert "WorkerApp" in source


def test_worker_registers_job_definitions():
    """A worker process must populate the same registries the scheduler does.

    Without this, ``JobDispatcher.dispatch`` resolves every message to
    ``Job <name> not found`` and the queue dead-letters productive work.
    """
    from apps.worker.app import WorkerApp
    from brsapi.jobs.registry import get_brsapi_job_registry
    from jobs.registry import job_registry

    WorkerApp()._register_jobs()

    assert job_registry.get("SyncQuotesJob") is not None
    assert get_brsapi_job_registry().get("brsapi_all_symbols") is not None
    assert get_brsapi_job_registry().get("gold_snapshot") is not None
