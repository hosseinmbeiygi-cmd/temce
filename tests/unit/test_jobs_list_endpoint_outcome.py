"""``GET /jobs`` must not hide a DB failure as a successful empty list.

``list_jobs`` used to catch every exception and return ``success=True`` with
``items: []``. That makes a broken DB read indistinguishable from "no jobs
yet" â€” the same success-empty/source-failure conflation the sibling
``/jobs/scheduler`` and ``/jobs/queue/stats`` endpoints already avoid.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class _FailingSession:
    """Session whose first query raises, so the endpoint hits its except path."""

    async def execute(self, *_args, **_kwargs):
        raise RuntimeError("db down")


@pytest.mark.asyncio
async def test_list_jobs_db_failure_returns_success_false() -> None:
    from apps.api.endpoints import jobs as jobs_mod

    response = await jobs_mod.list_jobs(session=_FailingSession())

    assert response.success is False
    assert response.error is not None
    assert response.data["items"] == []


@pytest.mark.asyncio
async def test_list_jobs_happy_path_still_success() -> None:
    """A working session must still return success=True with the rows."""

    class _Scalar:
        def __init__(self, value):
            self._value = value

        def scalar(self):
            return self._value

        def fetchone(self):
            return (1, 1, 0, 0, 0)

        def fetchall(self):
            return []

    class _OkSession:
        async def execute(self, *_args, **_kwargs):
            return _Scalar(0)

    from apps.api.endpoints import jobs as jobs_mod

    response = await jobs_mod.list_jobs(session=_OkSession())

    assert response.success is True
    assert response.data["total"] == 0
