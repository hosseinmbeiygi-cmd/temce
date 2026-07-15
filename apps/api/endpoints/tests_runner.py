from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from schemas.common.responses import ApiResponse

router = APIRouter()


class TestResultItem(BaseModel):
    name: str
    status: str
    duration: float = 0.0
    message: str = ""


class TestRunData(BaseModel):
    total: int
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    results: list[TestResultItem]


@router.post("/run")
async def run_all_tests() -> ApiResponse[TestRunData]:
    try:
        test_dir = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "comprehensive"
        test_file = test_dir / "test_all.py"

        start = time.monotonic()
        stdout, stderr = _execute_pytest(test_file, test_dir)
        elapsed = round(time.monotonic() - start, 2)

        results = _parse_pytest_output(stdout)

        total = len(results)
        passed = sum(1 for r in results if r.status == "passed")
        failed = sum(1 for r in results if r.status == "failed")
        skipped = sum(1 for r in results if r.status == "skipped")
        errors = sum(1 for r in results if r.status == "error")

        return ApiResponse[TestRunData](
            success=True,
            data=TestRunData(
                total=total,
                passed=passed,
                failed=failed,
                skipped=skipped,
                errors=errors,
                duration=elapsed,
                results=results,
            ),
        )

    except subprocess.TimeoutExpired:
        return ApiResponse[TestRunData](success=False, data=None, error={"message": "Test execution timed out"})
    except Exception as e:
        return ApiResponse[TestRunData](success=False, data=None, error={"message": f"Test runner error: {e}"})


def _execute_pytest(test_file: Path, cwd: Path) -> tuple[str, str]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(test_file),
            "-v",
            "--tb=line",
            "--no-header",
            "-p", "no:cacheprovider",
            "-p", "no:cov",
        ],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=cwd.parent.parent,
    )
    return proc.stdout or "", proc.stderr or ""


def _parse_pytest_output(stdout: str) -> list[TestResultItem]:
    results: list[TestResultItem] = []

    # Strategy 1: Look for specific test file prefix
    for line in stdout.split("\n"):
        if line.startswith("tests/comprehensive/test_all.py::"):
            results.append(_parse_single_line(line))

    # Strategy 2: Fallback to general pattern matching
    if not results:
        for line in stdout.split("\n"):
            line = line.strip()
            if "::" in line and any(s in line for s in ("PASSED", "FAILED", "ERROR")):
                results.append(_parse_single_line(line))

    return [r for r in results if r is not None]


def _parse_single_line(line: str) -> TestResultItem | None:
    parts = line.split(" ")
    if not parts:
        return None

    test_name_full = parts[0]
    test_name = test_name_full.split("::")[-1] if "::" in test_name_full else test_name_full

    status = "passed"
    msg = ""

    for p in parts:
        if p == "PASSED":
            status = "passed"
            break
        if p == "FAILED":
            status = "failed"
            break
        if p == "ERROR":
            status = "error"
            break
        if p == "SKIPPED":
            status = "skipped"
            break

    if status != "passed":
        msg = line

    return TestResultItem(name=test_name, status=status, duration=0.0, message=msg)
