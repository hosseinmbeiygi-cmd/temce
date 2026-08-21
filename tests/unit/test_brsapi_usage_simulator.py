"""
Unit tests for scripts/simulate_brsapi_usage.py.

The simulator runs the REAL ``brsapi.rate_limiter.RateLimiter`` against a
virtual clock, so these tests verify both the simulator's own verification
logic and the limiter's invariant guarantees (never exceed the caps).
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from datetime import timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import simulate_brsapi_usage as sim  # noqa: E402
from brsapi.rate_limiter import RateLimiter  # noqa: E402

TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))


def run(coro):
    return asyncio.run(coro)


class TestSlidingWindow(unittest.TestCase):
    def test_plain_cases(self):
        # 4 events, all inside 300s → max = 4
        self.assertEqual(sim._sliding_window_max([0, 1, 2, 3], 300.0), 4)
        # 2 events 301s apart → never in the same window → max = 1
        self.assertEqual(sim._sliding_window_max([0, 301], 300.0), 1)
        # 3 events: 0, 250, 500 → window [250..550] holds 2; max = 2
        self.assertEqual(sim._sliding_window_max([0, 250, 500], 300.0), 2)
        # Empty
        self.assertEqual(sim._sliding_window_max([], 300.0), 0)

    def test_burst_splits_across_windows(self):
        # 100 events at t=0 and 100 at t=300: at the exact boundary the
        # t=300 event belongs to the NEXT window (limiter prunes with <=)
        ts = [0.0] * 100 + [300.0] * 100
        self.assertEqual(sim._sliding_window_max(ts, 300.0), 100)


class TestSimulatorInvariants(unittest.TestCase):
    """End-to-end simulator runs — the real limiter under the virtual clock."""

    def _run_scenario(self, name, daily=4000, five_min=1000):
        sim.reset_clock()
        sim._install_clock()
        try:
            return run(
                sim.run_scenario(
                    name, sim.SCENARIOS[name],
                    {"daily": daily, "5min": five_min},
                )
            )
        finally:
            sim._restore_clock()

    def test_sweep_covers_every_endpoint(self):
        result = self._run_scenario("sweep")
        catalog_size = len(sim.BrsApiEndpoints.all())
        self.assertEqual(result.total_accepted, catalog_size)
        self.assertEqual(result.total_rejected, 0)
        self.assertTrue(result.ok)

    def test_realtime_day_within_budget(self):
        result = self._run_scenario("realtime-day")
        self.assertEqual(result.total_rejected, 0)
        self.assertLessEqual(result.max_5min, 1000)
        self.assertLessEqual(result.max_daily, 4000)
        self.assertTrue(result.ok)

    def test_backlog_sync_fits_exactly(self):
        # The run_backlog_sync plan = 3,999 requests — must fit in 4,000
        result = self._run_scenario("backlog-sync")
        self.assertEqual(result.total_rejected, 0)
        self.assertEqual(result.max_daily, 3999)
        self.assertTrue(result.ok)

    def test_nightly_over_budget_is_protected_by_fail_fast(self):
        # Demand = 6,000 on a 4,000 budget → ~2,000 rejected, 0 exceeded
        result = self._run_scenario("nightly")
        self.assertGreater(result.total_rejected, 0)
        self.assertEqual(result.max_daily, 4000)  # capped exactly at limit
        self.assertTrue(result.ok)  # no limit was ever exceeded

    def test_daily_limit_resets_across_virtual_days(self):
        result = self._run_scenario("multi-day")
        self.assertEqual(result.total_rejected, 0)
        # each virtual day stays far under the daily cap (no accumulation)
        self.assertLess(result.max_daily, 4000)
        self.assertTrue(result.ok)

    def test_very_small_budget_fails_fast_without_exceeding(self):
        # A 50/day budget with 800 fuzz requests: never exceed, reject the rest
        sim.reset_clock()
        sim._install_clock()
        try:
            result = run(
                sim.run_scenario(
                    "fuzz", sim.workload_fuzz,
                    {"daily": 50, "5min": 1000}, seed=7,
                )
            )
        finally:
            sim._restore_clock()
        self.assertEqual(result.max_daily, 50)
        self.assertGreater(result.total_rejected, 0)
        self.assertTrue(result.ok)


class TestLimiterBehavior(unittest.TestCase):
    """Direct limiter checks under the virtual clock (no scenario wrapper)."""

    def test_five_min_window_slides(self):
        sim.reset_clock()
        sim._install_clock()
        try:
            limiter = sim.make_limiter(daily_limit=4000, five_min_limit=3)
            rec = sim.Recorder()
            # fire 3 instantly (window full), then wait 5 min, fire again
            run(sim._backfill(
                limiter, rec, category="tsetmc", endpoint="/x",
                n_symbols=3, requests_per_symbol=1, delay_s=0.0,
            ))
            self.assertEqual(len(rec.accepted), 3)
            sim._clock.advance(301.0)
            run(sim._backfill(
                limiter, rec, category="tsetmc", endpoint="/x",
                n_symbols=3, requests_per_symbol=1, delay_s=0.0,
            ))
            self.assertEqual(len(rec.accepted), 6)
            # recorded timeline still obeys the 5-min invariant
            max5 = sim._sliding_window_max(
                [r.mono for r in rec.accepted], 300.0
            )
            self.assertLessEqual(max5, 3)
        finally:
            sim._restore_clock()

    def test_fail_fast_raises_at_daily_cap(self):
        sim.reset_clock()
        sim._install_clock()
        try:
            limiter = RateLimiter(
                daily_limit=5, five_min_limit=1000, fail_fast=True
            )
            rec = sim.Recorder()
            for _ in range(7):
                run(sim.sim_request(limiter, rec, "tsetmc", "/x"))
            self.assertEqual(len(rec.accepted), 5)
            self.assertEqual(len(rec.rejected), 2)
        finally:
            sim._restore_clock()

    def test_five_min_full_at_bucket_wait_does_not_crash(self):
        """Regression: 5-min window full at the bucket-wait exit must NOT
        recurse under the held lock (asyncio.Lock is non-reentrant) — the
        previous fix crashed there. The loop re-check must wait and resume."""
        sim.reset_clock()
        sim._install_clock()
        try:
            # Tiny 5-min cap + slow refill bucket forces the scenario:
            # fill the 5-min window, then a request lands in the bucket wait
            # path while the window is still full.
            limiter = RateLimiter(
                daily_limit=1000, five_min_limit=3, fail_fast=True
            )
            limiter.configure("tsetmc", 1)  # 1 token/min → bucket wait
            rec = sim.Recorder()
            # Fill the 5-min window with 3 requests at t=0
            for _ in range(3):
                run(sim.sim_request(limiter, rec, "tsetmc", "/x"))
            self.assertEqual(len(rec.accepted), 3)

            # Next request: 5-min window full → acquire() waits (virtual).
            # It must eventually succeed after the window slides, not crash.
            async def one_more():
                await sim.sim_request(limiter, rec, "tsetmc", "/x")

            run(one_more())
            self.assertEqual(len(rec.accepted), 4)
            # invariant still holds
            max5 = sim._sliding_window_max(
                [r.mono for r in rec.accepted], 300.0
            )
            self.assertLessEqual(max5, 3)
        finally:
            sim._restore_clock()


class TestNewScenarios(unittest.TestCase):
    """The per-endpoint / all-max / starvation / max-stress scenarios."""

    def _run(self, name, daily=10000, five_min=1000):
        sim.reset_clock()
        sim._install_clock()
        try:
            return run(
                sim.run_scenario(
                    name, sim.SCENARIOS[name],
                    {"daily": daily, "5min": five_min},
                )
            )
        finally:
            sim._restore_clock()

    def test_per_endpoint_every_endpoint_covered(self):
        result = self._run("per-endpoint")
        catalog_size = len(sim.BrsApiEndpoints.all())
        self.assertEqual(len(result.per_endpoint_stats), catalog_size)
        self.assertTrue(result.ok)

    def test_per_endpoint_no_endpoint_exceeds_5min_cap(self):
        result = self._run("per-endpoint", daily=10000, five_min=1000)
        for name, s in result.per_endpoint_stats.items():
            self.assertLessEqual(
                s["max5min"], 1000, f"{name} exceeded 5-min cap"
            )
            self.assertLessEqual(
                s["maxday"], 10000, f"{name} exceeded daily cap"
            )

    def test_per_endpoint_small_budget_still_never_exceeds(self):
        # Even a 500/day budget: the endpoint is capped exactly at 500,
        # remaining requests are fail-fast rejected — never above the cap.
        result = self._run("per-endpoint", daily=500, five_min=1000)
        self.assertTrue(result.ok)
        for name, s in result.per_endpoint_stats.items():
            self.assertLessEqual(s["maxday"], 500, name)
            self.assertLessEqual(s["max5min"], 1000, name)

    def test_all_max_combined_ceiling_holds(self):
        result = self._run("all-max", daily=10000, five_min=1000)
        self.assertTrue(result.ok)
        # Daily cap is the binding constraint under full simultaneous load.
        self.assertEqual(result.max_daily, 10000)
        self.assertLessEqual(result.max_5min, 1000)
        self.assertGreater(result.total_rejected, 0)

    def test_starvation_others_still_get_through_or_wait(self):
        result = self._run("starvation", daily=10000, five_min=1000)
        self.assertTrue(result.ok)
        self.assertEqual(len(result.starvation_stats), 4)
        for cat, s in result.starvation_stats.items():
            # The shared 5-min window caps EVERYONE (incl. the hog) at 1,000.
            self.assertEqual(s["hog_accepted"], 1001)
            # Others may be heavily delayed but never push past the cap.
            self.assertLessEqual(result.max_5min, 1000)

    def test_starvation_small_daily_budget_others_get_rejected(self):
        # When the hog also eats the daily budget, the others are rejected
        # by fail-fast instead of waiting — they receive nothing.
        result = self._run("starvation", daily=800, five_min=1000)
        self.assertTrue(result.ok)
        total_other_rejected = sum(
            s["rejected"] for s in result.starvation_stats.values()
        )
        self.assertGreater(total_other_rejected, 0)
        self.assertLessEqual(result.max_daily, 800)

    def test_max_stress_never_exceeds_caps(self):
        result = self._run("max-stress", daily=10000, five_min=1000)
        self.assertTrue(result.ok)
        self.assertLessEqual(result.max_5min, 1000)
        self.assertLessEqual(result.max_daily, 10000)
        # Demand far exceeds the budget → fail-fast protection kicks in.
        self.assertGreater(result.total_rejected, 0)


class TestEnvMismatchWarning(unittest.TestCase):
    def test_no_warning_with_env_below_cap(self):
        with patch.dict(
            "os.environ", {"BRSAPI_GLOBAL_DAILY_LIMIT": "4000"}
        ):
            self.assertIsNone(sim._limit_mismatch_warning())

    def test_warning_when_env_overrides_above_cap(self):
        with patch.dict(
            "os.environ", {"BRSAPI_GLOBAL_DAILY_LIMIT": "10000"}
        ):
            warning = sim._limit_mismatch_warning()
            self.assertIsNotNone(warning)
            self.assertIn("10000", warning)
            self.assertIn("unset", warning)


if __name__ == "__main__":
    unittest.main()
