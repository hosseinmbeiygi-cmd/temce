"""Unit tests for FOF valuation + cycle detection (no DB required)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from services.fund_fof import compute_fof_value, detect_cycles, expand_fof_lookthrough  # noqa: E402


def test_expand_lookthrough_depth_and_shares() -> None:
    positions = {
        "root": [
            {"sub_fund_id": "A", "value": 100.0},
            {"sub_fund_id": "B", "value": 100.0},
        ],
        "A": [
            {"sub_fund_id": "C", "value": 50.0},
            {"sub_fund_id": "D", "value": 50.0},
        ],
        "B": [],
        "C": [],
        "D": [],
    }
    rows = expand_fof_lookthrough("root", positions, max_depth=3)
    depths = {r["sub_fund_id"]: r["depth"] for r in rows}
    assert depths["A"] == 1
    assert depths["C"] == 2
    c_row = next(r for r in rows if r["sub_fund_id"] == "C")
    assert c_row["value"] == 25.0  # 50 × سهم ۰.۵
    assert c_row["circular_flag"] is False


def test_expand_lookthrough_detects_cycle_on_path() -> None:
    positions = {
        "A": [{"sub_fund_id": "B", "value": 100.0}],
        "B": [{"sub_fund_id": "A", "value": 100.0}],
    }
    rows = expand_fof_lookthrough("A", positions, max_depth=3)
    circular = [r for r in rows if r["circular_flag"]]
    assert circular and circular[0]["sub_fund_id"] == "A"
    assert circular[0]["depth"] == 2


def test_expand_lookthrough_respects_max_depth() -> None:
    chain = {
        "F0": [{"sub_fund_id": "F1", "value": 100.0}],
        "F1": [{"sub_fund_id": "F2", "value": 100.0}],
        "F2": [{"sub_fund_id": "F3", "value": 100.0}],
        "F3": [],
    }
    rows = expand_fof_lookthrough("F0", chain, max_depth=2)
    assert max(r["depth"] for r in rows) == 2
    assert not any(r["sub_fund_id"] == "F3" for r in rows)


def test_detect_cycles_simple_cycle() -> None:
    graph = {"A": ["B"], "B": ["A"], "C": ["A"]}
    cycles = detect_cycles(graph)
    assert any(set(c) >= {"A", "B"} for c in cycles)


def test_detect_cycles_none() -> None:
    graph = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
    assert detect_cycles(graph) == []


def test_detect_cycles_self_loop() -> None:
    cycles = detect_cycles({"A": ["A"]})
    assert cycles and "A" in cycles[0]


def test_compute_fof_value_basic() -> None:
    positions = [
        {"sub_fund_id": "tse:X", "units": 100, "sub_nav_per_unit": 2000, "circular_flag": False},
        {"sub_fund_id": "tse:Y", "units": 50, "sub_nav_per_unit": 1000, "circular_flag": False},
    ]
    result = compute_fof_value(positions)
    assert result["total_value"] == 250_000
    assert result["circular_value"] == 0
    assert result["coverage_pct"] == 100.0


def test_compute_fof_value_separates_circular() -> None:
    positions = [
        {"sub_fund_id": "tse:X", "units": 100, "sub_nav_per_unit": 2000, "circular_flag": False},
        {"sub_fund_id": "tse:A", "units": 10, "sub_nav_per_unit": 500, "circular_flag": True},
    ]
    result = compute_fof_value(positions)
    assert result["total_value"] == 200_000
    assert result["circular_value"] == 5_000
    assert result["valued_positions"] == 1


def test_compute_fof_value_missing_nav_reduces_coverage() -> None:
    positions = [
        {"sub_fund_id": "tse:X", "units": 100, "sub_nav_per_unit": 2000, "circular_flag": False},
        {"sub_fund_id": "tse:Z", "units": 100, "sub_nav_per_unit": None, "circular_flag": False},
    ]
    result = compute_fof_value(positions)
    assert result["missing_positions"] == 1
    assert result["coverage_pct"] == 50.0


def test_compute_fof_value_empty() -> None:
    result = compute_fof_value([])
    assert result["total_value"] == 0
    assert result["coverage_pct"] == 0.0
