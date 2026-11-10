"""TDD tests for GoldhubProvider (World Gold Council file importer).

RED: GoldhubProvider not yet implemented.
GREEN: provider reads Excel/CSV and normalises Goldhub columns.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from unittest.mock import patch

import pytest


# ── 1. Import ─────────────────────────────────────────────────────────────────

def test_goldhub_provider_importable():
    from providers.macro_sources.goldhub import (  # noqa: F401
        SUPPORTED_DATASETS,
        GoldhubProvider,
    )


def test_supported_datasets_contains_expected():
    from providers.macro_sources.goldhub import SUPPORTED_DATASETS

    assert "gold-demand-statistics" in SUPPORTED_DATASETS
    assert "central-bank-statistics" in SUPPORTED_DATASETS
    assert "mine-production" in SUPPORTED_DATASETS


# ── 2. fetch() — unknown dataset ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_unknown_dataset_returns_fail():
    from providers.macro_sources.goldhub import GoldhubProvider

    result = await GoldhubProvider().fetch(dataset="nonexistent-dataset")
    assert not result.success
    assert "Unknown dataset" in result.error


# ── 3. fetch() — file not found ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_missing_file_returns_fail(tmp_path):
    from providers.macro_sources.goldhub import GoldhubProvider

    provider = GoldhubProvider(fs_root=tmp_path)
    result = await provider.fetch(dataset="gold-demand-statistics")

    assert not result.success
    assert "not found" in result.error.lower() or "download" in result.error.lower()


# ── 4. fetch() — CSV happy path ───────────────────────────────────────────────

def _write_demand_csv(path: Path) -> None:
    rows = [
        {
            "Date": "2024Q1",
            "Jewellery": "478.5",
            "Technology": "82.3",
            "Investment": "290.1",
            "Central banks & other inst.": "290.0",
            "Total demand": "1140.9",
            "Total supply": "1180.0",
            "Mine production": "893.0",
            "Recycled gold": "287.0",
        }
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.asyncio
async def test_fetch_csv_demand_statistics(tmp_path):
    from providers.macro_sources.goldhub import GoldhubProvider

    csv_path = tmp_path / "gold-demand-statistics.csv"
    _write_demand_csv(csv_path)

    provider = GoldhubProvider(fs_root=tmp_path)
    result = await provider.fetch(dataset="gold-demand-statistics")

    assert result.success
    payload = result.value
    assert payload["dataset"] == "gold-demand-statistics"
    assert len(payload["rows"]) == 1

    row = payload["rows"][0]
    assert "as_of" in row
    assert "jewellery_tonnes" in row
    assert row["as_of"] == "2024Q1"


@pytest.mark.asyncio
async def test_fetch_explicit_file_path(tmp_path):
    from providers.macro_sources.goldhub import GoldhubProvider

    csv_path = tmp_path / "my_custom_file.csv"
    _write_demand_csv(csv_path)

    provider = GoldhubProvider(fs_root=tmp_path)
    result = await provider.fetch(
        file_path=csv_path,
        dataset="gold-demand-statistics",
    )

    assert result.success
    assert len(result.value["rows"]) == 1


# ── 5. fetch() — empty file ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_empty_csv_returns_zero_rows(tmp_path):
    from providers.macro_sources.goldhub import GoldhubProvider

    csv_path = tmp_path / "gold-demand-statistics.csv"
    csv_path.write_text("Date,Jewellery\n", encoding="utf-8")

    provider = GoldhubProvider(fs_root=tmp_path)
    result = await provider.fetch(dataset="gold-demand-statistics")

    assert result.success
    assert result.value["rows"] == []


# ── 6. health() ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_unhealthy_when_no_files(tmp_path):
    from providers.macro_sources.goldhub import GoldhubProvider

    provider = GoldhubProvider(fs_root=tmp_path)
    result = await provider.health()

    assert result["healthy"] is False
    assert "download" in result["message"].lower() or "goldhub" in result["message"].lower()


@pytest.mark.asyncio
async def test_health_healthy_when_files_present(tmp_path):
    from providers.macro_sources.goldhub import GoldhubProvider

    csv_path = tmp_path / "gold-demand-statistics.csv"
    _write_demand_csv(csv_path)

    provider = GoldhubProvider(fs_root=tmp_path)
    result = await provider.health()

    assert result["healthy"] is True
    assert "gold-demand-statistics" in result["available_datasets"]
