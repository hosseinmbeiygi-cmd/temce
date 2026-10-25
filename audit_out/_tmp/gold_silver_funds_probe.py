"""Probe — اجرای واقعی کد GoldDesk / Antigravity / FundNavEngine برای شواهد گزارش.

هیچ فایل موجودی تغییر داده نمی‌شود؛ هیچ نوشتنی روی DB انجام نمی‌شود.
خروجی: خطوط ساختاریافته در stdout.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


def banner(t: str) -> None:
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


# ── 1. تناقض عیار سکه: constants vs antigravity ────────────────────────────
banner("1) coin purity: gold_desk.constants vs antigravity.calculations")
from gold_desk.antigravity.calculations import (
    _COIN_PURITY,  # noqa: E402
    calculate_coin_bubble,  # noqa: E402
)
from gold_desk.constants import GOLD_PURITY_COIN  # noqa: E402
from gold_desk.pricer import fair_coin  # noqa: E402

print(f"constants.GOLD_PURITY_COIN        = {GOLD_PURITY_COIN}  (= {GOLD_PURITY_COIN/1000:.4f})")
print(f"antigravity.calculations._COIN_PURITY = {_COIN_PURITY}")
print(f"ratio = {_COIN_PURITY / (GOLD_PURITY_COIN/1000):.6f}  ({( _COIN_PURITY/(GOLD_PURITY_COIN/1000) - 1)*100:.4f}% اختلاف)")

XAU = 4000.0
USD = 900_000.0
fair_desk = fair_coin("IR_COIN_EMAMI", XAU, USD)
ag = calculate_coin_bubble(0.0, XAU, USD)
print(f"\ninputs: XAU={XAU} USD/oz, usd_irt={USD:,.0f}")
print(f"gold_desk.pricer.fair_coin(IR_COIN_EMAMI) = {fair_desk:,.0f}")
print(f"antigravity intrinsic                     = {ag.coin_intrinsic:,.0f}")
print(f"diff = {ag.coin_intrinsic - fair_desk:,.0f}  ({(ag.coin_intrinsic/fair_desk-1)*100:+.3f}%)")

market = fair_desk * 1.05
from gold_desk.bubbler import calc_bubble  # noqa: E402

b_desk = calc_bubble("IR_COIN_EMAMI", market, fair_desk, XAU)
b_ag = calculate_coin_bubble(market, XAU, USD)
print(f"\nmarket={market:,.0f}")
print(f"bubble via gold_desk (bubbler)      = {b_desk.bubble_pct:+.3f}%   signal={'(n/a)'}")
print(f"bubble via antigravity.calculations = {b_ag.bubble_pct:+.3f}%   signal={b_ag.signal}")

# ── 2. آستانه‌های P/NAV: سه مجموعه متفاوت در یک مخزن ──────────────────────
banner("2) P/NAV thresholds: constants vs antigravity vs fund_scoring")
from gold_desk.antigravity.calculations import calculate_nav_premium  # noqa: E402
from gold_desk.constants import NAV_GREEN_MAX, NAV_RED_MAX, NAV_YELLOW_MAX  # noqa: E402

print(f"gold_desk.constants: NAV_GREEN_MAX={NAV_GREEN_MAX}  NAV_YELLOW_MAX={NAV_YELLOW_MAX}  NAV_RED_MAX={NAV_RED_MAX}")
print("antigravity.calculations.calculate_nav_premium: BUY<int(-1.0)  SELL>2.0")
print("services/fund_scoring.py docstring: bubble > +3% → سقف سیگنال «اجتناب از خرید»")
for p in (-2.0, -0.5, 0.0, 1.0, 1.8, 2.0, 3.0, 5.0):
    r = calculate_nav_premium(100.0 + p, 100.0)
    nav_pts = (
        "کامل" if p <= NAV_GREEN_MAX else ("75%" if p <= NAV_YELLOW_MAX else ("30%" if p <= NAV_RED_MAX else "0"))
    )
    print(f"  premium={p:+5.2f}%  antigravity={r.signal:<8}  gold_desk_scorer_nav={nav_pts}")

# ── 3. alert_engine: جهت پیام برای قوانین *_below ─────────────────────────
banner("3) alert_engine message direction vs rule_type")
from gold_desk.alert_engine import DEFAULT_RULES, _check_condition  # noqa: E402

for r in DEFAULT_RULES:
    rt = r["rule_type"]
    thr = r["threshold"]
    direction = ">" if thr > 0 else "<"
    print(f"  rule_type={rt:<18} threshold={thr:<6} msg_operator='{direction}'  name={r['name']}")
# شرط واقعی rule از _check_condition می‌آید، نه از threshold sign
print("\n  _check_condition('bubble_below', value=2.0, threshold=3.0) =", _check_condition("bubble_below", 2.0, 3.0))
print("  اما پیام ساخته‌شده با threshold=3.0 به‌صورت '>' رندر می‌شود (نگاه بالا).")

# ── 4. FundNavEngine.compute_nav: کسر مضاعف بدهی در مسیر fallback ──────────
banner("4) FundNavEngine.compute_nav — double subtraction در مسیر holdings_missing")
from services.fund_nav_engine import compute_nav  # noqa: E402

report_total_assets = 1_000_000_000.0
report_liabilities = 100_000_000.0
report_net_asset_value = report_total_assets - report_liabilities  # آنچه در گزارش دوره است
units = 1_000_000

net_ok, nav_ok = compute_nav(report_total_assets, report_liabilities, units)
net_desk, nav_desk = compute_nav(report_net_asset_value, report_liabilities, units)
print(f"  مسیر A (assets - liabilities)          : net={net_ok:,.0f}  nav/unit={nav_ok:,.2f}")
print(f"  مسیر B (net_asset_value - liabilities) : net={net_desk:,.0f}  nav/unit={nav_desk:,.2f}")
print(f"  اختلاف nav/unit = {nav_desk - nav_ok:,.2f} ({((nav_desk/nav_ok)-1)*100:+.3f}%)")

# ── 5. forecaster: band/EMA ───────────────────────────────────────────────
banner("5) forecaster — band و EMA trend")
from gold_desk.forecaster import _calc_volatility, _forecast_ema_trend, build_forecast  # noqa: E402

quiet = [100.0 * (1.001 ** i) for i in range(60)]
r_quiet = build_forecast(quiet, "IR_COIN_EMAMI")
print(f"  quiet  : vol={r_quiet.volatility_daily_pct}%  h=30 lower={r_quiet.forecasts[1].lower_band:,.0f} pred={r_quiet.forecasts[1].predicted_price:,.0f}")

vol_series = [100.0]
for i in range(59):
    vol_series.append(vol_series[-1] * (1.12 if i % 2 == 0 else 0.88))
r_vol = build_forecast(vol_series, "IR_COIN_EMAMI")
v = _calc_volatility(vol_series)
import math  # noqa: E402

band_pct_30 = 1.96 * v * math.sqrt(30)
print(f"  volatile: vol={r_vol.volatility_daily_pct}%  band_pct(30d)={band_pct_30:.3f}  h=30 pred={r_vol.forecasts[1].predicted_price:,.0f} lower={r_vol.forecasts[1].lower_band:,.0f} upper={r_vol.forecasts[1].upper_band:,.0f}")

closes = [100.0 * (1.002 ** i) for i in range(60)]
ema_returned = _forecast_ema_trend(closes, 7)
# EMA واقعی سری
alpha = 2.0 / 15.0
ema = closes[0]
for p in closes[1:]:
    ema = p * alpha + ema * (1 - alpha)
print(f"  EMA(14) واقعی={ema:,.2f}   اما _forecast_ema_trend(h=7)={ema_returned:,.2f}  (خروجی بر مبنای drift است نه EMA)")

# ── 6. fund_scoring: پیوستگی توابع نمره‌دهی ────────────────────────────────
banner("6) fund_scoring — discontinuity در آستانه‌ها")
from services import fund_scoring as fs  # noqa: E402

for fn, name, pairs in [
    (fs._score_style_drift, "style_drift", [(5.0, 5.01), (20.0, 20.01)]),
    (fs._score_ter, "ter", [(0.5, 0.51), (2.0, 2.01)]),
    (fs._score_ir, "information_ratio", [(0.5, 0.5001), (1.4999, 1.5)]),
    (fs._score_tracking_diff, "tracking_difference", [(0.5, 0.51)]),
]:
    for a, b in pairs:
        print(f"  {name:<22} f({a})={fn(a):.3f}  f({b})={fn(b):.3f}  jump={fn(b)-fn(a):+.3f}")

# ── 7. auto_trade: سقف مبلغ hard-coded ────────────────────────────────────
banner("7) auto_trade — سقف مبلغ و ثبت dry-run")
from gold_desk.auto_trade import AutoTradeConfig, default_config  # noqa: E402

cfg = AutoTradeConfig(
    enabled=True, dry_run=True, max_position_irt=500_000_000.0,
    min_score_to_buy=80, min_score_to_sell=20, cooldown_hours=24,
)
print(f"  config.max_position_irt={cfg.max_position_irt:,.0f}  → amount=min(cfg, 50_000_000)={min(cfg.max_position_irt, 50_000_000):,.0f}")
print(f"  default_config(): {default_config()}")

print("\nDONE")
