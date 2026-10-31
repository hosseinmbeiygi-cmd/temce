"""Error-reporting contract for ``orchestration.runners``.

Root cause locked down (audit run3, orchestration package — previously untested):

``WorkflowRunner._execute_step_with_retry`` built its failure message from
``str(last_error)``.  Two very common exception shapes stringify to the empty
string:

* ``asyncio.TimeoutError()`` / ``TimeoutError()`` — ``str()`` is ``""``
  (verified on Python 3.11), so every timeout was reported as
  ``"Unknown error"`` and the real cause was lost.
* a bare ``raise ValueError`` with no argument — ``str()`` is ``""`` too.

Operators reading ``StepResult.error`` / ``WorkflowState.error`` could not tell a
timeout from an unknown failure.  The fix keeps a descriptive message for every
path and falls back to the exception class name when the message is empty.

The orchestration package is deliberately dependency-free (no DB / providers),
so these tests run everywhere.
"""

from __future__ import annotations

import asyncio

import pytest

from orchestration.context import WorkflowContext
from orchestration.contracts import Step, Workflow, WorkflowStatus
from orchestration.policies import RetryPolicy, TimeoutPolicy, WorkflowPolicy
from orchestration.runners import AsyncWorkflowRunner, WorkflowRunner


class _Step(Step):
    def __init__(self, name: str, fn) -> None:
        super().__init__(name)
        self._fn = fn

    async def execute(self, context):  # noqa: ANN001
        return await self._fn(context)

    async def compensate(self, context) -> None:  # noqa: ANN001
        return None


class _Workflow(Workflow):
    async def execute(self, context) -> None:  # noqa: ANN001
        return None


def _wf(*steps: Step) -> _Workflow:
    return _Workflow("wf", "wf", list(steps))


@pytest.mark.asyncio
async def test_timeout_error_message_is_not_opaque() -> None:
    """A timed-out step must report a timeout, not 'Unknown error'."""
    async def slow(_ctx):
        await asyncio.sleep(1.0)
        return 1

    policy = WorkflowPolicy(
        retry=RetryPolicy(max_retries=0),
        timeout=TimeoutPolicy(timeout_seconds=0.05, raise_on_timeout=True),
    )
    state = await WorkflowRunner(policy).run(_wf(_Step("a", slow)), WorkflowContext(workflow_id="wf"))

    assert state.status is WorkflowStatus.FAILED
    assert state.results, "no step result recorded"
    error = state.results[-1].error or ""
    assert "Timeout" in error, f"timeout reported as {error!r} — the cause is lost"
    assert "Unknown error" not in error


@pytest.mark.asyncio
async def test_empty_exception_message_falls_back_to_class_name() -> None:
    """``raise ValueError`` (no message) must still be identifiable."""
    async def boom(_ctx):
        raise ValueError  # str() == ""

    policy = WorkflowPolicy(retry=RetryPolicy(max_retries=0))
    state = await WorkflowRunner(policy).run(_wf(_Step("a", boom)), WorkflowContext(workflow_id="wf"))

    error = state.results[-1].error or ""
    assert error == "ValueError", f"expected class-name fallback, got {error!r}"
    assert not state.error or "Unknown error" not in state.error


@pytest.mark.asyncio
async def test_normal_exception_message_is_preserved() -> None:
    """A real message must pass through untouched."""
    async def boom(_ctx):
        raise RuntimeError("provider returned 503")

    policy = WorkflowPolicy(retry=RetryPolicy(max_retries=0))
    state = await WorkflowRunner(policy).run(_wf(_Step("a", boom)), WorkflowContext(workflow_id="wf"))

    assert "provider returned 503" in (state.results[-1].error or "")
    assert "provider returned 503" in (state.error or "")


@pytest.mark.asyncio
async def test_async_runner_empty_exception_message_falls_back() -> None:
    """``AsyncWorkflowRunner`` must use the same non-opaque fallback."""
    async def boom(_ctx):
        raise KeyError  # str() == "" for a bare KeyError instance? -> repr-ish; assert not opaque

    policy = WorkflowPolicy(retry=RetryPolicy(max_retries=0))
    state = await AsyncWorkflowRunner(policy).run(_wf(_Step("a", boom)), WorkflowContext(workflow_id="wf"))

    error = state.results[-1].error or ""
    assert error and error != "None", "async runner produced an empty/opaque error"
