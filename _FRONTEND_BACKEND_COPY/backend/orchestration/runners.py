from __future__ import annotations

import asyncio
import time

from core.logging import get_logger
from orchestration.context import WorkflowContext
from orchestration.contracts import (
    Step,
    StepResult,
    StepStatus,
    Workflow,
    WorkflowState,
    WorkflowStatus,
)
from orchestration.policies import (
    WorkflowPolicy,
    default_workflow_policy,
)

logger = get_logger("orchestration.runners")


class WorkflowRunner:
    def __init__(
        self,
        policy: WorkflowPolicy | None = None,
    ) -> None:
        self.policy = policy or default_workflow_policy

    async def run(
        self,
        workflow: Workflow,
        context: WorkflowContext,
    ) -> WorkflowState:
        state = WorkflowState(
            workflow_id=workflow.id,
            status=WorkflowStatus.RUNNING,
            started_at=time.time(),
        )
        workflow.status = WorkflowStatus.RUNNING
        context.logger.info(f"Starting workflow: {workflow.name} (id={workflow.id})")
        executed_steps: list[str] = []
        try:
            for step in workflow.steps:
                state.current_step = step.name
                context.logger.info(f"Executing step: {step.name}")
                step_start = time.time()
                result = await self._execute_step_with_retry(step, context)
                step_duration = time.time() - step_start
                result.duration_seconds = step_duration
                state.add_result(result)
                if result.success:
                    executed_steps.append(step.name)
                    result.status = StepStatus.COMPLETED
                    context.logger.info(f"Step {step.name} completed in {step_duration:.2f}s")
                else:
                    result.status = StepStatus.FAILED
                    context.logger.error(f"Step {step.name} failed: {result.error}")
                    await self._handle_failure(
                        workflow, context, state, executed_steps, step, result.error or "Unknown error"
                    )
                    return state
            state.status = WorkflowStatus.COMPLETED
            state.completed_at = time.time()
            workflow.status = WorkflowStatus.COMPLETED
            context.logger.info(f"Workflow {workflow.name} completed successfully")
        except Exception as exc:
            state.status = WorkflowStatus.FAILED
            state.error = str(exc)
            state.completed_at = time.time()
            workflow.status = WorkflowStatus.FAILED
            context.logger.error(f"Workflow {workflow.name} failed with exception: {exc}")
        return state

    async def _execute_step_with_retry(
        self,
        step: Step,
        context: WorkflowContext,
    ) -> StepResult:
        attempt = 0
        max_retries = self.policy.retry.max_retries
        last_error: Exception | None = None
        while attempt <= max_retries:
            try:
                output = await asyncio.wait_for(
                    step.execute(context),
                    timeout=self.policy.timeout.timeout_seconds,
                )
                return StepResult(
                    step_name=step.name,
                    success=True,
                    output=output,
                    status=StepStatus.COMPLETED,
                )
            except TimeoutError as exc:
                last_error = exc
                context.logger.warning(f"Step {step.name} timed out (attempt {attempt + 1})")
                if self.policy.timeout.on_timeout_callback:
                    self.policy.timeout.on_timeout_callback(step.name)
                if not self.policy.timeout.raise_on_timeout:
                    return StepResult(
                        step_name=step.name,
                        success=False,
                        error=f"Timeout after {self.policy.timeout.timeout_seconds}s",
                        status=StepStatus.FAILED,
                    )
            except Exception as exc:
                last_error = exc
                context.logger.warning(f"Step {step.name} failed (attempt {attempt + 1}): {exc}")
                if not self.policy.retry.should_retry(attempt, exc):
                    break
                delay = self.policy.retry.delay_for(attempt)
                if delay > 0:
                    await asyncio.sleep(delay)
            attempt += 1
        return StepResult(
            step_name=step.name,
            success=False,
            error=str(last_error) or "Unknown error",
            status=StepStatus.FAILED,
        )

    async def _handle_failure(
        self,
        workflow: Workflow,
        context: WorkflowContext,
        state: WorkflowState,
        executed_steps: list[str],
        failed_step: Step,
        error: str,
    ) -> None:
        workflow.status = WorkflowStatus.FAILED
        if self.policy.compensation.compensate_on_failure:
            state.status = WorkflowStatus.FAILED
            context.logger.info(f"Starting compensation for workflow {workflow.name}")
            for step_name in reversed(executed_steps):
                step = workflow.get_step(step_name)
                if step:
                    try:
                        context.logger.info(f"Compensating step: {step_name}")
                        await step.compensate(context)
                        state.results.append(
                            StepResult(
                                step_name=step_name,
                                success=True,
                                status=StepStatus.COMPENSATED,
                            )
                        )
                    except Exception as comp_exc:
                        context.logger.error(f"Compensation failed for step {step_name}: {comp_exc}")
                        state.results.append(
                            StepResult(
                                step_name=step_name,
                                success=False,
                                error=str(comp_exc),
                                status=StepStatus.FAILED,
                            )
                        )
            state.status = WorkflowStatus.FAILED
        state.error = error
        state.completed_at = time.time()


class AsyncWorkflowRunner:
    def __init__(
        self,
        policy: WorkflowPolicy | None = None,
        max_concurrency: int = 5,
    ) -> None:
        self.policy = policy or default_workflow_policy
        self.max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def run(
        self,
        workflow: Workflow,
        context: WorkflowContext,
    ) -> WorkflowState:
        state = WorkflowState(
            workflow_id=workflow.id,
            status=WorkflowStatus.RUNNING,
            started_at=time.time(),
        )
        workflow.status = WorkflowStatus.RUNNING
        context.logger.info(
            f"Starting async workflow: {workflow.name} (id={workflow.id}, concurrency={self.max_concurrency})"
        )
        try:
            tasks = []
            for step in workflow.steps:
                task = self._run_step_with_semaphore(step, context)
                tasks.append((step.name, task))
            results: dict[str, StepResult] = {}
            for step_name, task in tasks:
                try:
                    result = await asyncio.wait_for(task, timeout=self.policy.timeout.timeout_seconds)
                    results[step_name] = result
                    state.add_result(result)
                except TimeoutError:
                    result = StepResult(
                        step_name=step_name,
                        success=False,
                        error=f"Timeout after {self.policy.timeout.timeout_seconds}s",
                        status=StepStatus.FAILED,
                    )
                    results[step_name] = result
                    state.add_result(result)
                except Exception as exc:
                    result = StepResult(
                        step_name=step_name,
                        success=False,
                        error=str(exc),
                        status=StepStatus.FAILED,
                    )
                    results[step_name] = result
                    state.add_result(result)
            all_success = all(r.success for r in results.values())
            if all_success:
                state.status = WorkflowStatus.COMPLETED
                workflow.status = WorkflowStatus.COMPLETED
            else:
                state.status = WorkflowStatus.FAILED
                state.error = "One or more parallel steps failed"
                workflow.status = WorkflowStatus.FAILED
                if self.policy.compensation.compensate_on_failure:
                    await self._compensate_all(workflow, context, results)
            state.completed_at = time.time()
            context.logger.info(f"Async workflow {workflow.name} finished with status: {state.status.value}")
        except Exception as exc:
            state.status = WorkflowStatus.FAILED
            state.error = str(exc)
            state.completed_at = time.time()
            workflow.status = WorkflowStatus.FAILED
            context.logger.error(f"Async workflow {workflow.name} failed: {exc}")
        return state

    async def _run_step_with_semaphore(self, step: Step, context: WorkflowContext) -> StepResult:
        async with self._semaphore:
            return await self._execute_step(step, context)

    async def _execute_step(self, step: Step, context: WorkflowContext) -> StepResult:
        step_start = time.time()
        try:
            output = await asyncio.wait_for(
                step.execute(context),
                timeout=self.policy.timeout.timeout_seconds,
            )
            duration = time.time() - step_start
            return StepResult(
                step_name=step.name,
                success=True,
                output=output,
                status=StepStatus.COMPLETED,
                duration_seconds=duration,
            )
        except TimeoutError:
            return StepResult(
                step_name=step.name,
                success=False,
                error=f"Timeout after {self.policy.timeout.timeout_seconds}s",
                status=StepStatus.FAILED,
            )
        except Exception as exc:
            return StepResult(
                step_name=step.name,
                success=False,
                error=str(exc),
                status=StepStatus.FAILED,
            )

    async def _compensate_all(
        self,
        workflow: Workflow,
        context: WorkflowContext,
        results: dict[str, StepResult],
    ) -> None:
        for step_name, result in results.items():
            if not result.success:
                step = workflow.get_step(step_name)
                if step:
                    try:
                        context.logger.info(f"Compensating parallel step: {step_name}")
                        await step.compensate(context)
                    except Exception as comp_exc:
                        context.logger.error(f"Compensation failed for step {step_name}: {comp_exc}")
