#!/usr/bin/env python3
"""Write review-only diffs; NEVER edit an original source file or apply a patch.

These sketches address a subset of freshly reproduced cases, not all findings.
They require review and follow-up tests (especially Greeks and cache semantics).
"""
from difflib import unified_diff
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'reports/QA_PROPOSED_FIXES_2026-10-03.diff'
changes = []


def propose(path, replacements):
    original = (ROOT / path).read_text()
    updated = original
    for old, new in replacements:
        if old not in updated:
            raise RuntimeError(f'Proposal context absent in {path}: {old[:60]!r}')
        updated = updated.replace(old, new, 1)
    changes.extend(unified_diff(original.splitlines(keepends=True),
                                updated.splitlines(keepends=True),
                                fromfile='a/' + path, tofile='b/' + path))


propose('backtesting/analytics/engine.py', [
    ('            if dd > max_dd:\n                max_dd, max_dd_pct = dd, dd_pct\n',
     '            max_dd = max(max_dd, dd)\n            max_dd_pct = max(max_dd_pct, dd_pct)\n'),
])
propose('ml/features/trade_features.py', [
    ('df["real_net_flow_ma{w}"]', 'df[f"real_net_flow_ma{w}"]'),
    ('df["legal_net_flow_ma{w}"]', 'df[f"legal_net_flow_ma{w}"]'),
    ('df[feature_names].ffill(limit=3).bfill(limit=1)', 'df[feature_names].ffill(limit=3)'),
])
propose('ml/features/microstructure_features.py', [
    ('df[feature_names].ffill(limit=3).bfill(limit=1)', 'df[feature_names].ffill(limit=3)'),
])
propose('services/gold/calculator.py', [
    ('from dataclasses import dataclass\n', 'import math\nfrom dataclasses import dataclass\n'),
    ('    if nav <= 0:\n        raise ValueError("nav must be > 0")\n',
     '    if not math.isfinite(market_price) or not math.isfinite(nav):\n'
     '        raise ValueError("price and nav must be finite")\n'
     '    if market_price <= 0 or nav <= 0:\n'
     '        raise ValueError("price and nav must be > 0")\n'),
])
propose('domain/options/pricing.py', [
    ('    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:\n        return max(0.0, S - K)\n',
     '    if T <= 0 or S <= 0 or K <= 0:\n        return max(0.0, S - K)\n'
     '    if sigma == 0:\n        return max(0.0, S - K * math.exp(-r * T))\n'
     '    if sigma < 0:\n        raise ValueError("sigma must be nonnegative")\n'),
    ('    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:\n        return max(0.0, K - S)\n',
     '    if T <= 0 or S <= 0 or K <= 0:\n        return max(0.0, K - S)\n'
     '    if sigma == 0:\n        return max(0.0, K * math.exp(-r * T) - S)\n'
     '    if sigma < 0:\n        raise ValueError("sigma must be nonnegative")\n'),
    ('    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:\n        intrinsic =',
     '    if sigma < 0:\n        raise ValueError("sigma must be nonnegative")\n'
     '    if T > 0 and sigma == 0 and S > 0 and K > 0:\n'
     '        # Review-only sketch: deterministic-case Greeks need separate tests.\n'
     '        price = (black_scholes_call(S, K, T, r, sigma) if option_type == "call"\n'
     '                 else black_scholes_put(S, K, T, r, sigma))\n'
     '        intrinsic = max(0.0, S - K) if option_type == "call" else max(0.0, K - S)\n'
     '        return OptionPrice(model=PRICING_MODEL_BLACK_SCHOLES, price=price,\n'
     '                           intrinsic_value=intrinsic, time_value=price - intrinsic,\n'
     '                           parameters={"S": S, "K": K, "T": T, "r": r, "sigma": sigma,\n'
     '                                       "option_type": option_type})\n'
     '    if T <= 0 or S <= 0 or K <= 0:\n        intrinsic ='),
])
propose('services/smart_screener_v2.py', [
    ('import time\n', 'import hashlib\nimport json\nimport time\n'),
    ('        cache_key = f"analysis:{symbol}:{len(history)}"\n',
     '        # Include the mutable numerical inputs, not just history length.\n'
     '        payload = {"symbol": symbol, "quote": quote, "history": history,\n'
     '                   "sector_history": sector_history}\n'
     '        content = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")\n'
     '        cache_key = "analysis:" + hashlib.sha256(content).hexdigest()\n'),
])
# Git accepts bare blank context lines; omit their space to keep artifact whitespace clean.
OUTPUT.write_text(''.join('\n' if line == ' \n' else line for line in changes))
print(f'Wrote {OUTPUT.relative_to(ROOT)}; no application source changed.')
