"""Harness checks are separate from the deliberately failing product contracts."""
import json
import math
from pathlib import Path
import socket
import unittest

import run as audit


class HarnessTests(unittest.TestCase):
    def test_exact_case_budget(self):
        self.assertEqual(len(audit.CASES), 200)
        self.assertEqual(audit.Counter(c['category'] for c in audit.CASES),
                         {'BT': 75, 'ML': 55, 'SC': 50, 'SP': 20})
        self.assertEqual(len({c['id'] for c in audit.CASES}), 200)

    def test_strict_json(self):
        value = audit.clean({'nan': float('nan'), 'inf': float('inf'),
                             'np': audit.np.float64(3.5), 'tuple': (1, 2)})
        self.assertEqual(json.loads(json.dumps(value, allow_nan=False)),
                         {'nan': 'nan', 'inf': 'inf', 'np': 3.5, 'tuple': [1, 2]})

    def test_nan_does_not_pass_numeric_assertion(self):
        with self.assertRaises(AssertionError):
            audit.check(float('nan'), 0., 'nan_rejection')

    def test_assertion_observations_are_preserved(self):
        with self.assertRaises(AssertionError):
            audit.check(5., 20., 'probe')
        self.assertEqual(audit.EVIDENCE['probe'], {'actual': 5., 'expected': 20.})

    def test_tolerance_does_not_hide_single_rial_boundary(self):
        with self.assertRaises(AssertionError):
            audit.check(int(float(10**16 - 1)) == 10**16 - 1, True, 'exact_rial')

    def test_network_guard_blocks_connect_and_connect_ex(self):
        before = list(audit.BLOCKED_NETWORK)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                with self.assertRaisesRegex(RuntimeError, 'blocked'):
                    sock.connect(('203.0.113.1', 443))
                with self.assertRaisesRegex(RuntimeError, 'blocked'):
                    sock.connect_ex(('127.0.0.1', 1))
            self.assertEqual(len(audit.BLOCKED_NETWORK), len(before) + 2)
        finally:
            audit.BLOCKED_NETWORK[:] = before

    def test_original_file_manifest_not_changed_by_import(self):
        self.assertEqual(audit.tracked_hashes(), audit.BASELINE)
        self.assertTrue(audit.BASELINE)
        self.assertFalse(any(p.startswith('qa/') for p in audit.BASELINE))

    def test_fresh_microstructure_fixture_is_deterministic(self):
        audit.pd.testing.assert_frame_equal(audit.micro_data(2), audit.micro_data(2))
        self.assertFalse(audit.micro_data(2).equals(audit.micro_data(3)))

    def test_future_mutation_keeps_first_input_row_unchanged(self):
        audit.pd.testing.assert_series_equal(audit.micro_data(1).iloc[0],
                                            audit.micro_data(15).iloc[0])

    def test_synthetic_history_has_monotonic_dates(self):
        quote, history = audit.quote_history(0)
        dates = [r['date'] for r in history]
        self.assertEqual(dates, sorted(set(dates)))
        self.assertEqual(len(dates), 160)
        self.assertEqual(quote['price_close'], history[-1]['price_close'])


if __name__ == '__main__':
    unittest.main()
