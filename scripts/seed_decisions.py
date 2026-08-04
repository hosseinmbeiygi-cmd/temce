#!/usr/bin/env python3
"""
📊 Seed Decisions — بارگذاری تصمیمات نمونه در دیتابیس

این اسکریپت چند تصمیم واقعی (BUY, WATCHLIST, HOLD, REDUCE, REJECT)
برای نمادهای بورس تهران از طریق POST /decision-engine/decisions
به دیتابیس اضافه می‌کند.

مصرف:
    python scripts/seed_decisions.py
    python scripts/seed_decisions.py --url http://localhost:8000/api/v1
    python scripts/seed_decisions.py --run-id run-2026-07-27 --limit 5
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

try:
    import httpx
except ImportError:
    print("❌ httpx نصب نیست. دستور زیر را اجرا کنید:")
    print("   pip install httpx")
    sys.exit(1)

# ── Sample decisions ────────────────────────────────────────────────

SAMPLE_DECISIONS: list[dict[str, Any]] = [
    # ═══ BUY ═════════════════════════════════════════════════════════
    {
        "symbol": "فولاد",
        "run_id": "",
        "decision": "BUY",
        "final_score": 82.5,
        "confidence": 0.85,
        "score_fundamental": 88.0,
        "score_valuation": 72.0,
        "score_technical": 76.0,
        "score_liquidity": 85.0,
        "score_orderflow": 91.0,
        "score_micro": 78.0,
        "score_macro": 65.0,
        "score_event": 70.0,
        "base_score": 78.4,
        "micro_adjustment": 6.0,
        "penalty": 0.08,
        "details": {
            "reasons": [
                "رشد ۳۴٪ سود خالص در صورت‌های مالی ۱۲ ماهه",
                "ورود پول حقوقی به مدت ۵ روز متوالی",
                "قیمت بالاتر از VWAP روزانه",
                "نسبت P/E صنعت ۶.۲ در مقابل سهم ۴.۸",
            ],
            "reason_codes": ["FUN-03", "FLW-01", "MIC-02", "VAL-01"],
            "risk_flags": [],
        },
    },
    {
        "symbol": "شپنا",
        "run_id": "",
        "decision": "BUY",
        "final_score": 76.0,
        "confidence": 0.78,
        "score_fundamental": 82.0,
        "score_valuation": 70.0,
        "score_technical": 68.0,
        "score_liquidity": 80.0,
        "score_orderflow": 75.0,
        "score_micro": 72.0,
        "score_macro": 60.0,
        "score_event": 55.0,
        "base_score": 72.8,
        "micro_adjustment": 5.0,
        "penalty": 0.10,
        "details": {
            "reasons": [
                "حاشیه سود ناخالص بهبود یافته به ۳۸٪",
                "تأیید الگوی انباشت در تایم‌فریم روزانه",
                "نقدشوندگی بالا (گردش شناور ۸٪)",
            ],
            "reason_codes": ["FUN-05", "PAT-02", "LIQ-01"],
            "risk_flags": ["MAC-01"],
        },
    },
    # ═══ WATCHLIST ═══════════════════════════════════════════════════
    {
        "symbol": "وبملت",
        "run_id": "",
        "decision": "WATCHLIST",
        "final_score": 65.0,
        "confidence": 0.72,
        "score_fundamental": 70.0,
        "score_valuation": 75.0,
        "score_technical": 62.0,
        "score_liquidity": 78.0,
        "score_orderflow": 68.0,
        "score_micro": 60.0,
        "score_macro": 55.0,
        "score_event": 50.0,
        "base_score": 66.5,
        "micro_adjustment": 2.0,
        "penalty": 0.12,
        "details": {
            "reasons": [
                "P/E جذاب ۵.۲ در مقابل میانگین صنعت ۷.۸",
                "افزایش سرمایه از محل تجدید ارزیابی در راه",
                "شکاف دلار آزاد و نیما بالاست (ریسک ارزی)",
            ],
            "reason_codes": ["VAL-03", "EVT-04", "MAC-02"],
            "risk_flags": ["MAC-02", "EVT-01"],
        },
    },
    {
        "symbol": "خودرو",
        "run_id": "",
        "decision": "WATCHLIST",
        "final_score": 60.5,
        "confidence": 0.65,
        "score_fundamental": 55.0,
        "score_valuation": 68.0,
        "score_technical": 58.0,
        "score_liquidity": 82.0,
        "score_orderflow": 72.0,
        "score_micro": 65.0,
        "score_macro": 50.0,
        "score_event": 45.0,
        "base_score": 62.0,
        "micro_adjustment": 3.0,
        "penalty": 0.15,
        "details": {
            "reasons": [
                "رشد فروش ۲۲٪ در گزارش فصلی",
                "روند صعودی قیمت با حمایت میانگین ۵۰ روزه",
                "ریسک نرخ‌گذاری دستوری (خبر منفی)",
            ],
            "reason_codes": ["FUN-02", "TEC-01", "EVT-03"],
            "risk_flags": ["EVT-03", "REG-01"],
        },
    },
    # ═══ HOLD ════════════════════════════════════════════════════════
    {
        "symbol": "وغدیر",
        "run_id": "",
        "decision": "HOLD",
        "final_score": 55.0,
        "confidence": 0.60,
        "score_fundamental": 60.0,
        "score_valuation": 50.0,
        "score_technical": 52.0,
        "score_liquidity": 70.0,
        "score_orderflow": 62.0,
        "score_micro": 55.0,
        "score_macro": 48.0,
        "score_event": 40.0,
        "base_score": 55.5,
        "micro_adjustment": 1.0,
        "penalty": 0.10,
        "details": {
            "reasons": [
                "پرتفوی متنوع با سهم‌های بنیادی",
                "تخفیف NAV حدود ۴۰٪ (جذاب)",
                "خالص فروش حقوقی در ۱۰ روز گذشته",
            ],
            "reason_codes": ["VAL-04", "FLW-02"],
            "risk_flags": ["FLW-02"],
        },
    },
    # ═══ REDUCE ══════════════════════════════════════════════════════
    {
        "symbol": "ذوب",
        "run_id": "",
        "decision": "REDUCE",
        "final_score": 40.0,
        "confidence": 0.55,
        "score_fundamental": 35.0,
        "score_valuation": 45.0,
        "score_technical": 38.0,
        "score_liquidity": 50.0,
        "score_orderflow": 42.0,
        "score_micro": 35.0,
        "score_macro": 45.0,
        "score_event": 30.0,
        "base_score": 40.2,
        "micro_adjustment": -3.0,
        "penalty": 0.25,
        "details": {
            "reasons": [
                "نسبت زیان به سرمایه > ۱ (ماده ۱۴۱)",
                "خروج سنگین حقوقی در هفته گذشته",
                "حجم معاملات پایین (نقدشوندگی ضعیف)",
            ],
            "reason_codes": ["FUN-07", "FLW-03", "LIQ-02"],
            "risk_flags": ["FUN-07", "LIQ-02"],
        },
    },
    # ═══ REJECT ══════════════════════════════════════════════════════
    {
        "symbol": "کتوسعه",
        "run_id": "",
        "decision": "REJECT",
        "final_score": 22.0,
        "confidence": 0.92,
        "score_fundamental": 18.0,
        "score_valuation": 30.0,
        "score_technical": 20.0,
        "score_liquidity": 25.0,
        "score_orderflow": 15.0,
        "score_micro": 20.0,
        "score_macro": 35.0,
        "score_event": 25.0,
        "base_score": 22.8,
        "micro_adjustment": -5.0,
        "penalty": 0.35,
        "details": {
            "reasons": [
                "۳ سال متوالی زیان ده (زیان انباشته ۲۰۰٪ سرمایه)",
                "۵ رویداد منفی فعال (مجمع، زیان، تغییر مدیریت)",
                "الگوی توزیع تأیید شده (کدبه‌کد فروش)",
            ],
            "reason_codes": ["FUN-08", "EVT-05", "PAT-04"],
            "risk_flags": ["FUN-08", "EVT-05", "REJ-01"],
        },
    },
]


# ── Runner ──────────────────────────────────────────────────────────


def build_payload(decision: dict[str, Any], run_id: str | None = None) -> dict[str, Any]:
    """Build the API payload from a decision dict."""
    payload = dict(decision)
    if run_id:
        payload["run_id"] = run_id
    elif not payload.get("run_id"):
        payload["run_id"] = f"seed-{int(time.time())}"
    # Set defaults for optional fields
    payload.setdefault("model_version", "Enterprise-Final-1.0")
    payload.setdefault("rulebook_version", "RB-1.0")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed sample decisions into the Decision Engine database",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000/api/v1",
        help="API base URL (default: http://localhost:8000/api/v1)",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run ID for all decisions (default: auto-generated per decision)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=len(SAMPLE_DECISIONS),
        help=f"Number of decisions to seed (default: all {len(SAMPLE_DECISIONS)})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be sent without actually posting",
    )

    args = parser.parse_args()
    endpoint = f"{args.url.rstrip('/')}/decision-engine/decisions"
    decisions = SAMPLE_DECISIONS[: args.limit]

    print("=" * 60)
    print(f"📊 Seed Decisions — {len(decisions)} نمونه")
    print(f"📍 {endpoint}")
    print("=" * 60)

    if args.dry_run:
        print("\n🔍 Dry-run mode — showing payloads:\n")
        for d in decisions:
            payload = build_payload(d, args.run_id)
            print(f"  {payload['decision']:10s} | {payload['symbol']:8s} | score={payload['final_score']:5.1f} | confidence={payload['confidence']:.2f}")
        print(f"\n✅ Dry-run complete — {len(decisions)} decisions would be sent")
        return

    results = {"ok": 0, "fail": 0, "errors": []}

    with httpx.Client(timeout=30) as client:
        for i, decision in enumerate(decisions, 1):
            payload = build_payload(decision, args.run_id)

            try:
                resp = client.post(endpoint, json=payload)
                data = resp.json()

                if resp.status_code == 200 and data.get("success"):
                    symbol = payload["symbol"]
                    decision_type = payload["decision"]
                    score = payload["final_score"]
                    print(f"  ✅ [{i}/{len(decisions)}] {decision_type:10s} | {symbol:8s} | score={score:5.1f}")
                    results["ok"] += 1
                else:
                    error_msg = data.get("error", {}).get("message", resp.text)
                    print(f"  ❌ [{i}/{len(decisions)}] {payload['symbol']}: {error_msg[:100]}")
                    results["fail"] += 1
                    results["errors"].append({"symbol": payload["symbol"], "error": error_msg})

            except httpx.RequestError as exc:
                print(f"  ❌ [{i}/{len(decisions)}] {payload['symbol']}: Connection error — {exc}")
                results["fail"] += 1

    print("\n" + "=" * 60)
    print(f"📊 نتایج: ✅ {results['ok']} موفق | ❌ {results['fail']} ناموفق")
    if results["errors"]:
        print("\n⚠️  خطاها:")
        for err in results["errors"][:5]:
            print(f"   {err['symbol']}: {err['error'][:80]}")
    print("=" * 60)

    if results["fail"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
