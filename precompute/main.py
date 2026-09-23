"""precompute/main.py — CLI entrypoint for a precompute run.

Runs the full A -> B -> C priority pipeline. Symbols are loaded from the
ingestion hot layer (decoupled read); if that is empty, an optional JSON file
of raw snapshots can be supplied via --input.

Usage:
    python -m precompute.main
    python -m precompute.main --input snapshots.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging

logger = logging.getLogger("precompute.main")


async def _run(input_path: str | None) -> dict[str, object]:
    from .workers.celery_tasks import dispatch_armor_pipeline_async, load_symbols_from_ingestion

    if input_path:
        with open(input_path, encoding="utf-8") as fh:
            rows = json.load(fh)
        from .classifier import classify_from_dicts

        grouping = classify_from_dicts(rows)
        from contracts.schemas import SymbolGroup

        groups: dict[str, list[dict]] = {"A": [], "B": [], "C": []}
        for row in rows:
            grp = grouping.get(row.get("symbol", ""), SymbolGroup.C)
            groups[grp.value].append(row)
    else:
        groups = await load_symbols_from_ingestion()

    logger.info(
        "Precompute groups: A=%d B=%d C=%d",
        len(groups.get("A", [])),
        len(groups.get("B", [])),
        len(groups.get("C", [])),
    )
    return await dispatch_armor_pipeline_async(groups)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Run the Armor precompute pipeline.")
    parser.add_argument("--input", help="Optional JSON file of raw symbol snapshots.")
    args = parser.parse_args()
    result = asyncio.run(_run(args.input))
    logger.info("Precompute finished: %s", result)


if __name__ == "__main__":
    main()
