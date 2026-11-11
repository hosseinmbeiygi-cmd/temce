"""The 10-minute news ingest must not overlap itself.

Audit SCH-06. APScheduler's default ``max_instances`` is 3, so a slow feed let
the next tick start while the previous ingest was still running.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _add_job_calls() -> list[ast.Call]:
    tree = ast.parse((ROOT / "apps" / "scheduler" / "app.py").read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_job"
    ]


def test_news_ingestion_job_runs_single_instance() -> None:
    targets = [
        call
        for call in _add_job_calls()
        if call.args
        and isinstance(call.args[0], ast.Constant)
        and call.args[0].value == "NewsIngestionJob"
    ]

    assert targets, "NewsIngestionJob is not scheduled"
    kwargs = {kw.arg: kw.value for kw in targets[0].keywords}
    max_instances = kwargs.get("max_instances")
    assert isinstance(max_instances, ast.Constant) and max_instances.value == 1, (
        "NewsIngestionJob must set max_instances=1 so a slow feed cannot overlap the next tick"
    )
