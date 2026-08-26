"""
ScreenerAIReportService — AI-style comprehensive report generation for symbols.

Generates a complete Persian-language analyst report for any symbol using ALL
available data:
  - 110-column model result (Screener110Service.run_symbol)
  - screener_profiles (fundamentals, valuation, filters)
  - screener_signals history (model track record for this symbol)
  - daily_history (technical trend, volume, ATR)
  - daily_real_legal (institutional money flow)
  - screener_snapshots (latest live snapshot)

Also produces market-level reports (top buy signals, sector distribution).

The service is self-sufficient: pass an optional session; if omitted it opens
its own short-lived session from core.database.get_session() so it can be used
from chat, CLI, jobs and the API alike.

Usage:
    svc = ScreenerAIReportService(session)          # reuse an API session
    report = await svc.generate_symbol_report("فولاد")
    market = await svc.generate_market_report()
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger

logger = get_logger(__name__)

# ── Weight labels (must match WEIGHTS in screener110_service) ──────────────
_SCORE_LABELS: dict[str, str] = {
    "score_fundamental": "بنیادی",
    "score_valuation": "ارزش‌گذاری",
    "score_institutional": "نهادی",
    "score_technical": "تکنیکال",
    "score_macro": "کلان",
    "score_gov_support": "حمایت دولتی",
    "score_liquidity": "نقدشوندگی",
    "score_farabourse": "فرابورس",
    "score_feedstock": "خوراک و انرژی",
}

_DECISION_LABELS: dict[str, str] = {
    "خرید": "✅ خرید",
    "نخرید": "⏸ نخرید (نگه‌داری)",
    "رد_ریسک": "🛑 رد — فیلتر ریسک",
    "رد_نمره": "🚫 رد — نمره پایین",
}


def _fmt(v: Any, digits: int = 2) -> str:
    """Format a number or return '—' for None."""
    if v is None:
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f == 0:
        return "0"
    if abs(f) >= 1e12:
        return f"{f/1e12:.2f}T"
    if abs(f) >= 1e9:
        return f"{f/1e9:.2f}B"
    if abs(f) >= 1e6:
        return f"{f/1e6:.1f}M"
    if abs(f) >= 1e3:
        return f"{f/1e3:.1f}K"
    return f"{f:.{digits}f}"


class ScreenerAIReportService:
    """Generates complete AI-style reports for symbols and the market."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    # ────────────────────────────────────────────────────────────────────────
    # Session management — own a short-lived session when none injected
    # ────────────────────────────────────────────────────────────────────────

    async def _sessions(self) -> AsyncGenerator[AsyncSession, None]:
        if self._session is not None:
            yield self._session
            return
        from core.database import get_session

        async for s in get_session():
            yield s

    # ────────────────────────────────────────────────────────────────────────
    # Data loading helpers
    # ────────────────────────────────────────────────────────────────────────

    async def _load_profile(self, session: AsyncSession, symbol: str) -> dict[str, Any] | None:
        r = await session.execute(
            text("SELECT * FROM screener_profiles WHERE symbol = :sym"), {"sym": symbol}
        )
        row = r.fetchone()
        return dict(row._mapping) if row else None

    async def _load_latest_signal(self, session: AsyncSession, symbol: str) -> dict[str, Any] | None:
        r = await session.execute(
            text(
                "SELECT * FROM screener_signals WHERE symbol = :sym "
                "ORDER BY generated_at DESC LIMIT 1"
            ),
            {"sym": symbol},
        )
        row = r.fetchone()
        return dict(row._mapping) if row else None

    async def _load_signals_history(self, session: AsyncSession, symbol: str, limit: int = 30) -> list[dict[str, Any]]:
        r = await session.execute(
            text(
                "SELECT generated_at, final_score, adjusted_score, decision, "
                "       current_price, stop_loss_price, risk_ok, negative_filters_count "
                "FROM screener_signals WHERE symbol = :sym "
                "ORDER BY generated_at DESC LIMIT :lim"
            ),
            {"sym": symbol, "lim": limit},
        )
        return [dict(row._mapping) for row in r.fetchall()]

    async def _load_symbol_meta(self, session: AsyncSession, symbol: str) -> dict[str, Any] | None:
        r = await session.execute(
            text(
                "SELECT symbol, name, industry, market_type, asset_class, "
                "       total_shares, eps, pe "
                "FROM symbols WHERE symbol = :sym"
            ),
            {"sym": symbol},
        )
        row = r.fetchone()
        return dict(row._mapping) if row else None

    async def _load_legal_30d(self, session: AsyncSession, symbol: str) -> dict[str, Any] | None:
        r = await session.execute(
            text(
                """
                SELECT
                    SUM(legal_buy_volume)  AS legal_buy,
                    SUM(legal_sell_volume) AS legal_sell,
                    SUM(real_buy_volume)   AS real_buy,
                    SUM(real_sell_volume)  AS real_sell,
                    SUM(legal_buy_value)   AS legal_buy_value,
                    SUM(legal_sell_value)  AS legal_sell_value,
                    COUNT(*) AS days
                FROM daily_real_legal drl
                JOIN symbols s ON s.id = drl.symbol_id
                WHERE s.symbol = :sym AND drl.trade_date >= NOW() - INTERVAL '36 days'
                """
            ),
            {"sym": symbol},
        )
        row = r.fetchone()
        return dict(row._mapping) if row else None

    async def _load_daily_60(self, session: AsyncSession, symbol: str) -> list[dict[str, Any]]:
        r = await session.execute(
            text(
                """
                SELECT dh.trade_date, dh.price_close, dh.price_max, dh.price_min,
                       dh.trade_volume, dh.trade_value, dh.price_last_change_pct
                FROM daily_history dh
                JOIN symbols s ON s.id = dh.symbol_id
                WHERE s.symbol = :sym
                ORDER BY dh.trade_date DESC LIMIT 60
                """
            ),
            {"sym": symbol},
        )
        return [dict(row._mapping) for row in r.fetchall()]

    # ────────────────────────────────────────────────────────────────────────
    # Public: symbol report
    # ────────────────────────────────────────────────────────────────────────

    async def generate_symbol_report(self, symbol: str) -> dict[str, Any]:
        """Generate a complete AI-style report for one symbol.

        Returns dict with:
          - symbol, name, generated_at
          - model: 110-column model output (or None)
          - profile: screener_profiles row
          - signal: latest screener_signals row
          - signals_history: last N runs
          - legal_30d, daily_60
          - text: full Persian narrative report
        """
        async for session in self._sessions():
            meta = await self._load_symbol_meta(session, symbol)
            profile = await self._load_profile(session, symbol)
            signal = await self._load_latest_signal(session, symbol)
            signals_history = await self._load_signals_history(session, symbol)
            legal_30d = await self._load_legal_30d(session, symbol)
            daily_60 = await self._load_daily_60(session, symbol)

            # Run the 110-column model fresh for this symbol
            model: dict[str, Any] | None = None
            try:
                from services.screener110_service import Screener110Service

                svc = Screener110Service(session)
                model = await svc.run_symbol(symbol)
            except Exception as exc:
                logger.warning("Screener110 model failed for %s: %s", symbol, exc)

            text_report = self._build_symbol_text(
                symbol=symbol,
                meta=meta,
                profile=profile,
                signal=signal,
                model=model,
                signals_history=signals_history,
                legal_30d=legal_30d,
                daily_60=daily_60,
            )

            return {
                "symbol": symbol,
                "name": (meta or {}).get("name"),
                "industry": (meta or {}).get("industry") or (profile or {}).get("industry"),
                "model": model,
                "profile": profile,
                "signal": signal,
                "signals_history": signals_history,
                "legal_30d": legal_30d,
                "daily_60": daily_60,
                "text": text_report,
            }
        return {"symbol": symbol, "text": "امکان اتصال به دیتابیس وجود ندارد.", "model": None}

    # ────────────────────────────────────────────────────────────────────────
    # Public: market report
    # ────────────────────────────────────────────────────────────────────────

    async def generate_market_report(self, limit: int = 25) -> dict[str, Any]:
        """Generate a market-wide AI report from the latest run-cycle signals."""
        async for session in self._sessions():
            # Latest generation timestamp
            r = await session.execute(
                text(
                    "SELECT MAX(generated_at) AS latest "
                    "FROM screener_signals"
                )
            )
            latest_row = r.fetchone()
            latest_ts = latest_row[0] if latest_row else None

            r = await session.execute(
                text(
                    """
                    SELECT s1.* FROM screener_signals s1
                    JOIN (
                        SELECT symbol, MAX(generated_at) AS g
                        FROM screener_signals GROUP BY symbol
                    ) s2 ON s1.symbol = s2.symbol AND s1.generated_at = s2.g
                    ORDER BY s1.final_score DESC
                    LIMIT :lim
                    """
                ),
                {"lim": limit},
            )
            latest_signals = [dict(row._mapping) for row in r.fetchall()]

            buy_signals = [s for s in latest_signals if s.get("decision") == "خرید"]

            # Stats across the market
            r = await session.execute(
                text(
                    """
                    SELECT COUNT(*) AS total,
                           COUNT(*) FILTER (WHERE decision = 'خرید') AS buys,
                           COUNT(*) FILTER (WHERE decision = 'رد_ریسک') AS risk_rejects,
                           COALESCE(AVG(final_score), 0) AS avg_score,
                           COALESCE(MAX(final_score), 0) AS max_score
                    FROM screener_signals s1
                    JOIN (
                        SELECT symbol, MAX(generated_at) AS g
                        FROM screener_signals GROUP BY symbol
                    ) s2 ON s1.symbol = s2.symbol AND s1.generated_at = s2.g
                    """
                )
            )
            stats_row = r.fetchone()
            stats = dict(stats_row._mapping) if stats_row else {}

            text_report = self._build_market_text(buy_signals, latest_signals, stats, latest_ts)

            return {
                "generated_at": latest_ts.isoformat() if latest_ts else None,
                "stats": stats,
                "buy_signals": buy_signals,
                "top_signals": latest_signals,
                "text": text_report,
            }
        return {"text": "امکان اتصال به دیتابیس وجود ندارد.", "buy_signals": []}

    # ────────────────────────────────────────────────────────────────────────
    # Text builders
    # ────────────────────────────────────────────────────────────────────────

    def _build_symbol_text(
        self,
        symbol: str,
        meta: dict[str, Any] | None,
        profile: dict[str, Any] | None,
        signal: dict[str, Any] | None,
        model: dict[str, Any] | None,
        signals_history: list[dict[str, Any]],
        legal_30d: dict[str, Any] | None,
        daily_60: list[dict[str, Any]],
    ) -> str:
        lines: list[str] = []
        price = (model or signal or {}).get("current_price") or (profile or {}).get("current_price") or 0

        # ── Header ──
        name = (meta or {}).get("name") if meta else None
        industry = (meta or {}).get("industry") or (profile or {}).get("industry") or "—"
        lines.append(f"🤖 **گزارش تحلیلی هوشمند — {symbol}**{(' (' + str(name) + ')') if name else ''}")
        lines.append("═" * 52)
        lines.append(f"صنعت: {industry}")

        # ── Model / decision summary ──
        if model:
            decision = model.get("decision", "")
            dec_label = _DECISION_LABELS.get(decision, decision)
            lines.append(f"**تصمیم مدل ۱۱۰ ستونی: {dec_label}**")
            lines.append(f"نمره نهایی: {model.get('final_score', 0):.1f} / 100 "
                         f"(تعدیل‌شده: {model.get('adjusted_score', 0):.1f})")
            lines.append(f"قیمت فعلی: {_fmt(price)} ریال | "
                         f"P/E: {model.get('live_pe', 0):.1f} | "
                         f"ضریب P/E به صنعت: {model.get('pe_ratio', 0):.2f}")
            lines.append(f"روند ۲۰ روزه: {model.get('trend_20d', '—')} | "
                         f"جهش حجمی: {model.get('volume_spike', 0):.2f}x")
            lines.append(f"خرید خالص حقوقی نسبت به شناور: {model.get('institutional_ratio', 0):.4f}")
            if model.get("stop_loss_price"):
                lines.append(f"🛡 حد ضرر پیشنهادی: {_fmt(model.get('stop_loss_price'))} ریال")
            if model.get("position_size"):
                lines.append(f"📦 سایز پوزیشن پیشنهادی: {_fmt(model.get('position_size'), 0)} سهم (۱٪ سرمایه)")

            # ── Score breakdown ──
            lines.append("")
            lines.append("📊 **تفکیک نمرات مدل (ستون‌های ۸۶-۹۴):**")
            lines.append("-" * 40)
            for key, label in _SCORE_LABELS.items():
                val = model.get(key)
                lines.append(f"• {label}: {_fmt(val, 1)}")
        elif signal:
            decision = signal.get("decision", "")
            dec_label = _DECISION_LABELS.get(decision, decision)
            lines.append(f"**آخرین تصمیم مدل: {dec_label}**")
            lines.append(f"نمره نهایی: {signal.get('final_score', 0):.1f} / 100")
            lines.append(f"قیمت: {_fmt(price)} ریال")
        else:
            lines.append("⚠️ این نماد هنوز توسط مدل ۱۱۰ ستونی ارزیابی نشده است.")

        # ── Profile / fundamentals ──
        if profile:
            lines.append("")
            lines.append("🏢 **داده‌های بنیادی:**")
            lines.append("-" * 40)
            eps = profile.get("eps_current")
            eps_prev = profile.get("eps_prev_year")
            lines.append(f"• EPS جاری: {_fmt(eps, 0)} ریال | EPS سال قبل: {_fmt(eps_prev, 0)} ریال")
            if eps and eps_prev:
                growth = (float(eps) / float(eps_prev) - 1) * 100 if float(eps_prev) else 0
                lines.append(f"• رشد EPS: {growth:+.1f}٪")
            if profile.get("industry_pe"):
                lines.append(f"• P/E میانگین صنعت: {float(profile['industry_pe']):.1f}")
            if profile.get("registered_capital"):
                lines.append(f"• سرمایه ثبت‌شده: {_fmt(profile['registered_capital'])} میلیارد")
            if profile.get("free_float_shares"):
                lines.append(f"• سهام شناور: {_fmt(profile['free_float_shares'], 0)}")
            if profile.get("avg_50d_volume"):
                lines.append(f"• میانگین حجم ۵۰ روزه: {_fmt(profile['avg_50d_volume'], 0)}")
            if profile.get("avg_daily_value"):
                lines.append(f"• ارزش معاملات روزانه: {_fmt(profile['avg_daily_value'])}")

            # Filters that fired
            filter_cols = [
                ("f77_dollar_eps_growth", "رشد دلاری EPS > ۱۵٪"),
                ("f78_real_eps_growth", "رشد واقعی EPS > ۱۵٪"),
                ("f79_pe_ratio_ok", "ضریب P/E < ۱.۲"),
                ("f80_yield_gt_bank", "بازده > سود بانکی"),
                ("f81_inst_ratio_ok", "خرید حقوقی > ۵٪ شناور"),
                ("f82_volume_spike", "جهش حجمی > ۳ برابر"),
                ("f83_liquidity_ok", "نقدشوندگی > ۰.۵٪"),
                ("f84_loss_ratio_ok", "نسبت زیان/سرمایه < ۵۰٪"),
            ]
            fired = [label for col, label in filter_cols if profile.get(col) == 1]
            if fired:
                lines.append("")
                lines.append("🎯 **فیلترهای محاسباتی فعال:**")
                for label in fired:
                    lines.append(f"  ✅ {label}")

        # ── Institutional flow ──
        if legal_30d:
            lines.append("")
            lines.append("🏦 **جریان پول نهادی (۳۰ روز اخیر):**")
            lines.append("-" * 40)
            lb = legal_30d.get("legal_buy") or 0
            ls = legal_30d.get("legal_sell") or 0
            lines.append(f"• خرید حقوقی: {_fmt(lb, 0)} | فروش حقوقی: {_fmt(ls, 0)}")
            net = float(lb or 0) - float(ls or 0)
            lines.append(f"• خالص خرید حقوقی: {_fmt(net, 0)} ({'+' if net >= 0 else ''}{net / max(float(lb or ls or 1), 1) * 100:.1f}٪ از گردش)")
            if legal_30d.get("days"):
                lines.append(f"• روزهای دارای داده: {legal_30d['days']}")

        # ── Technical from daily history ──
        if daily_60:
            lines.append("")
            lines.append("📈 **نقاط تکنیکال (۶۰ روز اخیر):**")
            lines.append("-" * 40)
            closes = [float(d.get("price_close") or 0) for d in daily_60 if d.get("price_close")]
            if closes:
                ma5 = sum(closes[:5]) / len(closes[:5]) if len(closes) >= 5 else 0
                ma20 = sum(closes[:20]) / len(closes[:20]) if len(closes) >= 20 else 0
                hi60 = max(float(d.get("price_max") or 0) for d in daily_60)
                lo60 = min(float(d.get("price_min") or 0) for d in daily_60)
                lines.append(f"• میانگین ۵ روزه: {_fmt(ma5)} | میانگین ۲۰ روزه: {_fmt(ma20)}")
                lines.append(f"• سقف ۶۰ روزه: {_fmt(hi60)} | کف ۶۰ روزه: {_fmt(lo60)}")
                if ma20 and price:
                    dist = (float(price) / ma20 - 1) * 100
                    lines.append(f"• فاصله قیمت تا MA20: {dist:+.1f}٪")
            recent_pct = [float(d.get("price_last_change_pct") or 0) for d in daily_60 if d.get("price_last_change_pct")]
            if recent_pct:
                last5 = sum(recent_pct[:5])
                lines.append(f"• مجموع تغییرات ۵ روز اخیر: {last5:+.1f}٪")

        # ── Model track record ──
        if signals_history:
            lines.append("")
            lines.append("🕘 **سابقه سیگنال‌های این نماد:**")
            lines.append("-" * 40)
            for s in signals_history[:6]:
                ts = s.get("generated_at")
                ts_str = str(ts)[:16] if ts else "—"
                dec = _DECISION_LABELS.get(s.get("decision", ""), s.get("decision", ""))
                lines.append(f"• {ts_str} | {dec} | نمره {s.get('final_score', 0):.1f}")

        # ── Verdict ──
        if model:
            lines.append("")
            lines.append("🎯 **جمع‌بندی:**")
            lines.append("-" * 40)
            final = model.get("final_score", 0)
            decision = model.get("decision", "")
            if decision == "خرید":
                lines.append("این نماد با عبور از آستانه نمره ۷۰ و بدون فیلتر ریسک منفی، کاندید خرید است. "
                             "حد ضرر پیشنهادی و سایز پوزیشن را رعایت کنید و ورود را در چند ترنچ انجام دهید.")
            elif decision == "رد_ریسک":
                lines.append("این نماد به دلیل فعال بودن فیلترهای ریسک منفی رد شده است — "
                             "حتی با نمره بالا نباید وارد شد.")
            elif decision == "رد_نمره":
                lines.append(f"نمره مدل ({final:.1f}) زیر آستانه ۷۰ است. بهبود بنیادی یا بازگشت روند لازم است.")
            else:
                lines.append(f"نمره مدل {final:.1f} از ۱۰۰ — وضعیت بینابینی. منتظر سیگنال واضح‌تر بمانید.")
            lines.append("")
            lines.append("⚠️ این گزارش صرفاً مبتنی بر داده‌های موجود است و توصیه مالی نیست.")

        return "\n".join(lines)

    def _build_market_text(
        self,
        buy_signals: list[dict[str, Any]],
        top_signals: list[dict[str, Any]],
        stats: dict[str, Any],
        latest_ts: Any,
    ) -> str:
        lines: list[str] = []
        lines.append("🤖 **گزارش هوشمند بازار (مدل ۱۱۰ ستونی)**")
        lines.append("═" * 52)
        ts_str = str(latest_ts)[:16] if latest_ts else "—"
        lines.append(f"آخرین اجرای مدل: {ts_str}")
        lines.append("")

        if stats:
            total = stats.get("total", 0)
            buys = stats.get("buys", 0)
            risk = stats.get("risk_rejects", 0)
            avg = stats.get("avg_score", 0)
            lines.append(f"📊 نمادهای ارزیابی‌شده: {total}")
            lines.append(f"✅ سیگنال خرید: {buys}")
            lines.append(f"🛑 رد ریسک: {risk}")
            lines.append(f"📈 میانگین نمره: {avg:.1f} / 100")
            lines.append("")

        if buy_signals:
            lines.append("🔥 **برترین سیگنال‌های خرید:**")
            lines.append("-" * 40)
            for s in buy_signals[:10]:
                lines.append(
                    f"• {s.get('symbol', '—')}: نمره {s.get('final_score', 0):.1f} | "
                    f"P/E {s.get('live_pe', 0):.1f} | "
                    f"قیمت {_fmt(s.get('current_price'), 0)} | "
                    f"حد ضرر {_fmt(s.get('stop_loss_price'), 0)}"
                )
        else:
            lines.append("در آخرین اجرا هیچ سیگنال خریدی صادر نشد.")

        if top_signals and not buy_signals:
            lines.append("")
            lines.append("📋 **بالاترین نمرات (بدون سیگنال خرید):**")
            lines.append("-" * 40)
            for s in top_signals[:10]:
                dec = _DECISION_LABELS.get(s.get("decision", ""), s.get("decision", ""))
                lines.append(f"• {s.get('symbol', '—')}: نمره {s.get('final_score', 0):.1f} — {dec}")

        lines.append("")
        lines.append("⚠️ این گزارش صرفاً مبتنی بر داده‌های موجود است و توصیه مالی نیست.")
        return "\n".join(lines)
