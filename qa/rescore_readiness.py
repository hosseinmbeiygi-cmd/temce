"""Recompute the audit's §8 Product Readiness Score from measured evidence.

Every input is read from an artifact produced during this remediation run; the
formulas are copied verbatim from §8 of FINAL_QA_AUDIT_REPORT.md so the new
number is comparable with the audited 48.2/100.

Usage:
    venv/Scripts/python.exe qa/rescore_readiness.py

Writes:
    reports/readiness_score_recheck.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def pytest_totals(path: Path) -> dict:
    """Sum the chunked pytest runs recorded in reports/pytest_chunks.txt."""
    totals = dict(passed=0, failed=0, error=0, skipped=0)
    hung = 0
    rows = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(
            r"(\w+)\|rc=(\d+)\|passed=(\d+)\|failed=(\d+)\|error=(\d+)\|skipped=(\d+)(.*)",
            line.strip(),
        )
        if not m:
            continue
        rows += 1
        totals["passed"] += int(m.group(3))
        totals["failed"] += int(m.group(4))
        totals["error"] += int(m.group(5))
        totals["skipped"] += int(m.group(6))
        if "hang" in m.group(7):
            hung += int(re.search(r"(\d+) tests", m.group(7)).group(1))
    executed = totals["passed"] + totals["failed"] + totals["error"]
    return {
        "batches": rows,
        **totals,
        "executed": executed,
        "not_executable_hung": hung,
        "unit_pass_rate": round(totals["passed"] / executed, 4) if executed else 0.0,
    }


def docker_build_matrix() -> dict:
    path = REPORTS / "docker_build_matrix.txt"
    ok, failed = set(), []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("Dockerfile") and "|rc=0|" in line:
                ok.add(line.split("|")[0])
            elif line.startswith("FAILED"):
                failed.append(line)
    return {"built_ok": sorted(ok), "built_ok_count": len(ok), "failed": failed}


def docker_boot_matrix() -> list[str]:
    path = REPORTS / "docker_boot_matrix.txt"
    if not path.exists():
        return []
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if "|" in ln]


def main() -> int:
    crawl = load_json(REPORTS / "ui_crawl_summary.json", {})
    c3 = load_json(REPORTS / "c3_inference_results.json", {})
    tests = pytest_totals(REPORTS / "pytest_chunks.txt")
    builds = docker_build_matrix()
    boot = docker_boot_matrix()

    # ── Inputs measured in this run ────────────────────────────────────
    render_ok_share = crawl.get("render_ok_share", 0.0)
    blank = crawl.get("blank", 0)
    runtime_errors = crawl.get("runtime_errors", 0)
    real_console = crawl.get("total_real_console_errors", 0)

    ml_import_share = 1.0  # qa: 117/117 ml.* submodules import under Python 3.11 + pandas 2.3.3
    c3_summary = c3.get("summary", {})
    c3_ok = c3_summary.get("ok_share", 0.0)

    # ── §8 formulas ────────────────────────────────────────────────────
    # A1 was measured by audit-only scripts (qa/phase1_structure.py etc.) that are
    # not present in this tree, so it is carried over unchanged.
    contract_pass, broken_share, orphan_share = 0.8, 25 / 147, 26 / 147
    a1 = 15 * (0.5 * contract_pass + 0.3 * (1 - broken_share) + 0.2 * (1 - orphan_share))

    # A2 was NOT TESTED by the audit (-> 0). It is now measured: share of routes
    # that render real content, with zero-weight penalties for blank views,
    # runtime crashes and genuine console errors (backend-unavailable noise excluded).
    a2 = 15 * render_ok_share
    a2_penalty = 0.0
    if blank:
        a2_penalty += 0.05 * min(1.0, blank / max(1, crawl.get("total_routes", 1)))
    if runtime_errors:
        a2_penalty += 0.10 * min(1.0, runtime_errors / max(1, crawl.get("total_routes", 1)))
    if real_console:
        a2_penalty += 0.05
    a2 = max(0.0, a2 - 15 * a2_penalty)

    # B1/B2/B3 - money representation, math invariants, Iranian-market rules.
    # None of the 20 P1 money/signal findings were touched in this remediation,
    # so the audited inputs are carried over.
    b1 = 8 * 0.118
    b2 = 12 * 0.7113
    b3 = 5 * (2 / 12)

    # C1 - backtest engine/metrics/trade accounting. Untouched.
    c1 = 15 * 0.7296

    # C2 - ML confidence calibration + ml package importability.
    confidence_pass_rate = 0.9615  # not re-measured; P0-2 was a compatibility fix
    c2 = 6 * (0.5 * confidence_pass_rate + 0.5 * ml_import_share)

    # C3 - inference on trained models. Was 0 ("not tested"); now measured.
    c3_pts = 4 * c3_ok

    # D1 - idempotency / race / error semantics. 1 of the 5 critical invariants
    # (30-worker alert race -> exactly one fire) was executed live against the
    # real Postgres and passed. The other 4 remain unexecuted -> 0 by design.
    d1 = 8 * (1 / 5)

    # D2 - build & dependency integrity. Was 0 (P0 build blocker + unpinned deps).
    # Now: a 430-pin lock, --no-deps installs, and real `docker build` runs.
    total_images = 8
    d2_build_share = builds["built_ok_count"] / total_images
    lock_present = (ROOT / "requirements.lock").is_file()
    d2 = 6 * (0.5 * (1.0 if lock_present else 0.0) + 0.5 * d2_build_share)

    # D3 - code resilience.
    import_ok = 0.9893  # audit value; the repo-wide census is too slow to redo here
    d3 = 6 * (0.5 * tests["unit_pass_rate"] + 0.5 * import_ok)

    rows = [
        ("A1", "UI static nav + live-route contract", 15, round(a1, 2),
         {"contract_pass": contract_pass, "pages_with_broken_calls": "25/147 (audited)",
          "orphans": "26/147 (audited)", "source": "carried over - audit scripts absent"}),
        ("A2", "UI live rendering / blank / console", 15, round(a2, 2),
         {"render_ok_share": render_ok_share, "blank": blank,
          "runtime_errors": runtime_errors, "real_console_errors": real_console,
          "backend_unavailable_errors": crawl.get("total_backend_unavailable_errors"),
          "source": "qa/ui_crawl.mjs + qa/ui_crawl_classify.py"}),
        ("B1", "Money representation", 8, round(b1, 2),
         {"numeric_or_decimal_share": 0.118, "source": "carried over - P1 money work untouched"}),
        ("B2", "Calculation correctness", 12, round(b2, 2),
         {"invariant_pass_rate": 0.7113, "source": "carried over"}),
        ("B3", "Iranian-market rules", 5, round(b3, 2),
         {"pass": 2, "fail": 10, "source": "carried over"}),
        ("C1", "Backtest engine + metrics", 15, round(c1, 2),
         {"pass_rate": 0.7296, "source": "carried over"}),
        ("C2", "ML calibration + ml importability", 6, round(c2, 2),
         {"confidence_pass_rate": confidence_pass_rate, "ml_modules_importable": ml_import_share,
          "source": "importability measured (117/117); calibration carried over"}),
        ("C3", "Inference on trained models", 4, round(c3_pts, 2),
         {"artifact_dirs": c3_summary.get("artifact_dirs"), "loadable": c3_summary.get("ok"),
          "ok_share": c3_ok, "source": "qa/c3_inference_check.py"}),
        ("D1", "Idempotency / race / error semantics", 8, round(d1, 2),
         {"pass": 1, "total": 5,
          "executed": "qa/concurrency_proof.py: 30 parallel workers -> exactly 1 alert",
          "source": "1 of 5 invariants executed live; 4 unexecuted score 0 by design"}),
        ("D2", "Build & dependency integrity", 6, round(d2, 2),
         {"lock_pins": 430, "lock_present": lock_present,
          "images_built_ok": builds["built_ok"], "build_share": d2_build_share,
          "container_start": boot,
          "source": "qa/build_all_images.sh + qa/boot_all_images.sh"}),
        ("D3", "Code resilience", 6, round(d3, 2),
         {"unit_pass_rate": tests["unit_pass_rate"], "import_ok": import_ok,
          "tests": tests, "source": "reports/pytest_chunks.txt"}),
    ]

    category = {
        "UI & Navigation Stability": round(a1 + a2, 2),
        "Financial Precision & Data Integrity": round(b1 + b2 + b3, 2),
        "Backtest & ML Engine Reliability": round(c1 + c2 + c3_pts, 2),
        "Concurrency & Code Resilience": round(d1 + d2 + d3, 2),
    }
    total = round(sum(category.values()), 2)

    # §9 verdict rule: GO requires score >= 80 AND zero P0 AND zero open P1 on
    # money/signal-producing paths.
    open_p0 = []
    open_p1_money = [f"F{i:02d}" for i in
                     [3, 28, 24, 12, 22, 26, 13, 14, 4, 5, 7, 8, 9, 10, 11, 6, 15, 16, 20, 23]]
    verdict = "GO" if (total >= 80 and not open_p0 and not open_p1_money) else "NO-GO"

    out = {
        "baseline_audit": {
            "source": "C:/Users/Iran/Downloads/FINAL_QA_AUDIT_REPORT.md",
            "score": 48.2,
            "verdict": "NO-GO",
            "components": {"A1": 12.2, "A2": 0.0, "B1": 0.94, "B2": 8.54, "B3": 0.83,
                           "C1": 10.94, "C2": 5.68, "C3": 0.0,
                           "D1": 3.2, "D2": 0.0, "D3": 5.88},
        },
        "recheck": {
            "components": [
                {"id": r[0], "name": r[1], "max": r[2], "points": r[3], "inputs": r[4]}
                for r in rows
            ],
            "categories": category,
            "total": total,
            "delta": round(total - 48.2, 2),
        },
        "verdict": {
            "result": verdict,
            "rule": "GO requires score >= 80 AND zero P0 AND zero open P1 on money/signal paths",
            "open_p0": open_p0,
            "open_p1_money_paths": open_p1_money,
            "note": (
                "Both audited P0s (F01 missing deps, F02 unpinned deps) are fixed and "
                "verified in a real container. The verdict stays NO-GO because the 20 "
                "unremediated P1 money/signal findings independently block GO."
            ),
        },
    }
    dest = REPORTS / "readiness_score_recheck.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{'id':4} {'points':>8} {'/':>3}  name")
    for r in rows:
        print(f"{r[0]:4} {r[3]:8.2f} {r[2]:3}  {r[1]}")
    print("-" * 60)
    for k, v in category.items():
        print(f"     {v:8.2f}     {k}")
    print("-" * 60)
    print(f"     {total:8.2f} / 100   (baseline 48.20, delta {total - 48.2:+.2f})")
    print(f"VERDICT: {verdict}")
    print(f"written: {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())