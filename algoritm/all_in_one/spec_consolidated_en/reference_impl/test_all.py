import random
import unittest
from datetime import date, timedelta

import adjust
import labels
import pandas as pd
import pit
import purged_cv
import queue_tracker
import returns
import rules


class TestPIT(unittest.TestCase):
    def test_latest_known_version_and_no_future(self):
        df = pd.DataFrame({
            "instrument_id": ["A", "A", "A"],
            "event_time": pd.to_datetime(["2024-01-01"] * 3),
            "knowledge_time": pd.to_datetime(["2024-01-02", "2024-01-05", "2024-01-09"]),
            "px": [1.0, 2.0, 3.0]})
        v = pit.visible_asof(df, pd.Timestamp("2024-01-06"))
        self.assertEqual(float(v.px.iloc[0]), 2.0)           # correction known at the 5th wins; the 9th is invisible
        with self.assertRaises(pit.LookAheadError):
            pit.assert_no_lookahead(df, pd.Timestamp("2024-01-06"))


class TestRules(unittest.TestCase):
    def test_overlap_is_per_scope_and_missing_raises(self):
        R = rules.Rule
        ok = rules.RuleRegistry([R("k", "market:M", 1, date(2020, 1, 1), date(2021, 1, 1)),
                                 R("k", "symbol:S", 2, date(2020, 6, 1), date(2021, 6, 1))])   # different scopes: fine
        self.assertEqual(ok.rule_at("k", ["symbol:S", "market:M"], date(2020, 7, 1)).value, 2)
        self.assertEqual(ok.rule_at("k", ["symbol:S", "market:M"], date(2020, 3, 1)).value, 1)
        self.assertEqual(ok.rule_at("k", ["market:M"], date(2020, 1, 1)).confidence, "D")      # default D
        with self.assertRaises(rules.RuleNotFound):
            ok.rule_at("k", ["market:M"], date(2021, 1, 1))                                     # half-open end
        with self.assertRaises(rules.RuleOverlap):
            rules.RuleRegistry([R("k", "g", 1, date(2020, 1, 1), date(2021, 1, 1)), R("k", "g", 2, date(2020, 12, 31), None)])


class TestAdjust(unittest.TestCase):
    def _series(self, drops):
        d0 = date(2024, 1, 1)
        idx = [d0 + timedelta(days=i) for i in range(10)]
        s = pd.Series([100.0] * 10, index=idx)
        return s, idx

    def test_bonus_dividend_rights_continuity(self):
        s, idx = self._series(None)
        ex = idx[5]
        # bonus g=0.25 -> price falls by 1/(1.25)
        raw = s.copy()
        raw[raw.index >= ex] = 100.0 / 1.25
        adj = adjust.adjusted_close(raw, [adjust.Event(ex, "bonus", g=0.25)])
        self.assertTrue(((adj / adj.shift(1)).dropna() - 1).abs().max() < 1e-12)
        # cash dividend D=10
        raw = s.copy()
        raw[raw.index >= ex] = 90.0
        adj = adjust.adjusted_close(raw, [adjust.Event(ex, "cash_dividend", dividend=10.0)])
        self.assertTrue(((adj / adj.shift(1)).dropna() - 1).abs().max() < 1e-12)
        # rights g=0.5 at K=40 -> TERP=(100+20)/1.5=80
        raw = s.copy()
        raw[raw.index >= ex] = 80.0
        adj = adjust.adjusted_close(raw, [adjust.Event(ex, "rights", g=0.5, subscription_price=40.0)])
        self.assertTrue(((adj / adj.shift(1)).dropna() - 1).abs().max() < 1e-12)


class TestPurgedCV(unittest.TestCase):
    def test_no_overlap_with_embargo(self):
        rnd = random.Random(1)
        for _ in range(50):
            n = rnd.randint(60, 200)
            dec = list(range(n))
            h = rnd.randint(1, 10)
            end = [d + h for d in dec]
            emb = rnd.randint(0, 5)
            for train, test in purged_cv.purged_walk_forward(dec, end, 4, 30, emb):
                ts = min(dec[i] for i in test)
                self.assertTrue(all(end[i] + emb < ts for i in train))
                self.assertFalse(set(train) & set(test))


class TestReturns(unittest.TestCase):
    def test_withdrawals_add(self):
        self.assertEqual(returns.nominal_pnl(ending_value=120, contributions=100, withdrawals=30), 50)

    def test_real_and_usd(self):
        d0, d1 = date(2023, 1, 1), date(2024, 1, 1)   # exactly 365 days
        flows = [(d0, -100.0), (d1, 200.0)]
        self.assertAlmostEqual(returns.xirr(flows), 1.0, places=6)
        real = returns.deflate(flows, {d0: 100.0, d1: 200.0}, base=d0)          # prices doubled -> real return 0
        self.assertAlmostEqual(returns.xirr(real), 0.0, places=6)
        usd = returns.to_usd(flows, {d0: 10.0, d1: 20.0})                       # FX doubled -> USD return 0
        self.assertAlmostEqual(returns.xirr(usd), 0.0, places=6)


class TestQueue(unittest.TestCase):
    def test_properties(self):
        rnd = random.Random(7)
        for _ in range(300):
            q = queue_tracker.QueueTracker(qty=rnd.randint(1, 500), ahead=rnd.randint(0, 5000), submit_ts=10.0)
            prev = 0
            for k in range(rnd.randint(1, 30)):
                ts = 10.0 + k
                if rnd.random() < 0.3:
                    q.on_cancel_ahead(ts, rnd.randint(0, 1000))
                else:
                    q.on_trade(ts, rnd.randint(0, 1500))
                self.assertLessEqual(q.filled, q.qty)
                self.assertGreaterEqual(q.ahead, 0)
                self.assertGreaterEqual(q.filled, prev)
                prev = q.filled
        with self.assertRaises(queue_tracker.QueueError):
            queue_tracker.QueueTracker(10, 0, 5.0).on_trade(4.0, 10)

    def test_no_fill_until_ahead_cleared_and_locked_rule(self):
        q = queue_tracker.QueueTracker(qty=100, ahead=1000, submit_ts=0.0)
        self.assertEqual(q.on_trade(1.0, 900), 0)
        self.assertEqual(q.on_trade(2.0, 250), 100)      # 100 still ahead is consumed first, then our 100 fills
        self.assertEqual(q.status, "FILLED")
        self.assertEqual(queue_tracker.locked_entry_status(True, False), "unfillable")
        self.assertEqual(queue_tracker.locked_entry_status(True, True), "ok")


class TestLabels(unittest.TestCase):
    def test_label_and_reasons(self):
        y = labels.executable_label(100, 110, 0, 0, 0, 0, True, True, True)
        self.assertAlmostEqual(y["label"], 0.10)
        self.assertEqual(labels.executable_label(100, 110, 0, 0, 0, 0, True, True, False)["reason"], "missing_execution_rule")
        self.assertEqual(labels.executable_label(100, 110, 0, 0, 0, 0, False, True, True)["reason"], "untradable_entry")


if __name__ == "__main__":
    unittest.main(verbosity=2)
