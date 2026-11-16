"""Lifecycle of a monitored instrument: activate → analyse (repeatedly) → remove.

State lives in the database, so a restart neither loses active monitors nor duplicates
work: the scheduler job simply picks up every ``status='active'`` row again.

Concurrency: an analysis locks its monitor row with ``FOR UPDATE SKIP LOCKED``. A second
worker (or an API call racing the job) skips the row instead of analysing it twice, and a
monitor removed mid-flight is no longer selectable. A partial unique index makes a second
active monitor for the same (user, symbol) impossible.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.ids import new_id
from core.logging import get_logger
from models.alert_engine import (
    AlertAnalysisModel,
    AlertEngineSettingsModel,
    AlertEquityStateModel,
    AlertLedgerEntryModel,
    AlertMonitorModel,
    AlertNotificationModel,
)
from services.alert_engine import (
    ENGINE_VERSION,
    MODE_PAPER,
    RULES_VERSION,
    analytics,
    data,
    decision,
    notifier,
    options_view,
    risk,
)
from services.alert_engine import regime as regime_mod
from services.alert_engine.settings import EngineSettings, SettingsError, loosens_risk, validate

logger = get_logger(__name__)

RISK_STATES = ("exit", "reduce", "exit_infeasible")


class EngineError(ValueError):
    """A request the engine refuses, with a user-presentable reason."""


def _default_market_open() -> bool:
    from jobs.market_hours import is_tehran_market_open

    return is_tehran_market_open()


def _kill_switch_on() -> bool:
    try:
        from services.kill_switch import KillSwitch

        return bool(KillSwitch().is_killed())
    except Exception:  # noqa: BLE001 — an unreadable switch must not crash analysis
        logger.warning("alert-engine: kill switch unreadable", exc_info=True)
        return False


def _dumps(doc: Any) -> str:
    return json.dumps(doc, ensure_ascii=False, default=str)


class AlertEngine:
    def __init__(self, session: AsyncSession, *, now_fn: Any = None, market_open_fn: Any = None) -> None:
        self.session = session
        self._now = now_fn or (lambda: datetime.now(UTC))
        self._market_open = market_open_fn or _default_market_open

    # ── settings (versioned) ────────────────────────────────────────────────────────

    async def get_settings(self, user_id: str) -> tuple[EngineSettings, int]:
        row = (await self.session.execute(
            select(AlertEngineSettingsModel).where(AlertEngineSettingsModel.user_id == user_id)
            .order_by(AlertEngineSettingsModel.version.desc()).limit(1))).scalar_one_or_none()
        if row is None:
            return EngineSettings(), 0
        return EngineSettings.from_dict(json.loads(row.settings)), row.version

    async def update_settings(self, user_id: str, patch: dict[str, Any], *, approved_by: str,
                              confirm_loosening: bool = False, note: str = "") -> dict[str, Any]:
        current, version = await self.get_settings(user_id)
        new = current.merged(patch)
        loosened = loosens_risk(current.risk, new.risk)
        if loosened and not confirm_loosening:
            raise SettingsError("این تغییر محدودیت‌های ریسک را شل‌تر می‌کند و تأیید صریح می‌خواهد: " + ", ".join(loosened))
        return await self._store_settings(user_id, new, version + 1, approved_by, note or ("loosened: " + ", ".join(loosened) if loosened else ""))

    async def rollback_settings(self, user_id: str, to_version: int, *, approved_by: str) -> dict[str, Any]:
        row = (await self.session.execute(select(AlertEngineSettingsModel).where(
            AlertEngineSettingsModel.user_id == user_id, AlertEngineSettingsModel.version == to_version))).scalar_one_or_none()
        if row is None:
            raise EngineError("نسخهٔ تنظیمات یافت نشد")
        _, version = await self.get_settings(user_id)
        restored = EngineSettings.from_dict(json.loads(row.settings))
        validate(restored)
        return await self._store_settings(user_id, restored, version + 1, approved_by, f"rollback to v{to_version}")

    async def _store_settings(self, user_id: str, new: EngineSettings, version: int, approved_by: str, note: str) -> dict[str, Any]:
        self.session.add(AlertEngineSettingsModel(user_id=user_id, version=version, settings=_dumps(new.to_dict()),
                                                  approved_by=approved_by, note=note))
        await self.session.flush()
        return {"version": version, "settings": new.to_dict(), "note": note}

    async def settings_history(self, user_id: str) -> list[dict[str, Any]]:
        rows = (await self.session.execute(select(AlertEngineSettingsModel).where(
            AlertEngineSettingsModel.user_id == user_id).order_by(AlertEngineSettingsModel.version.desc()).limit(50))).scalars().all()
        return [{"version": r.version, "approved_by": r.approved_by, "note": r.note, "created_at": r.created_at} for r in rows]

    # ── ledger / portfolio ──────────────────────────────────────────────────────────

    async def _ledger(self, user_id: str) -> list[dict[str, Any]]:
        rows = (await self.session.execute(select(AlertLedgerEntryModel).where(
            AlertLedgerEntryModel.user_id == user_id).order_by(AlertLedgerEntryModel.executed_at))).scalars().all()
        return [{"id": r.id, "entry_type": r.entry_type, "book": r.book, "symbol": r.symbol, "quantity": r.quantity,
                 "price_rial": r.price_rial, "fees_toman": r.fees_toman or 0.0, "amount_toman": r.amount_toman,
                 "executed_at": r.executed_at, "note": r.note, "analysis_id": r.analysis_id} for r in rows]

    async def add_ledger_entry(self, user_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        """Record a user-confirmed trade or cash flow. This is the only way a position exists."""
        settings, _ = await self.get_settings(user_id)
        entries = await self._ledger(user_id)
        entry = {**entry, "book": entry.get("book") or "actual", "executed_at": entry.get("executed_at") or self._now()}
        if entry["executed_at"].tzinfo is None:
            entry["executed_at"] = entry["executed_at"].replace(tzinfo=UTC)
        if entry["executed_at"] > self._now():
            raise risk.LedgerError("executed_at cannot be in the future")
        if entry.get("symbol"):
            entry["symbol"] = data.normalize_symbol(entry["symbol"])
        book = risk.build_book(entries, settings.risk.capital_toman, entry["book"])
        risk.validate_entry(entry, {s: p["quantity"] for s, p in book["positions"].items()})
        if entry["entry_type"] == "buy":
            cost = entry["quantity"] * entry["price_rial"] / 10 + (entry.get("fees_toman") or 0)
            if cost > book["cash_toman"] + 1e-6:
                raise risk.LedgerError("این خرید از نقدینگی ثبت‌شده بیشتر است؛ ابتدا واریز را ثبت کنید")
        if entry["entry_type"] == "withdrawal" and entry["amount_toman"] > book["cash_toman"] + 1e-6:
            raise risk.LedgerError("برداشت از نقدینگی موجود بیشتر است")
        row = AlertLedgerEntryModel(id=new_id("led"), user_id=user_id, entry_type=entry["entry_type"], book=entry["book"],
                                    symbol=entry.get("symbol"), quantity=entry.get("quantity"), price_rial=entry.get("price_rial"),
                                    fees_toman=entry.get("fees_toman") or 0.0, amount_toman=entry.get("amount_toman"),
                                    executed_at=entry["executed_at"], note=entry.get("note"), analysis_id=entry.get("analysis_id"))
        self.session.add(row)
        await self.session.flush()
        return {"id": row.id, **{k: entry.get(k) for k in ("entry_type", "book", "symbol", "quantity", "price_rial", "fees_toman", "amount_toman", "executed_at")}}

    async def portfolio(self, user_id: str, book: str = "actual", *, persist_hwm: bool = True) -> dict[str, Any]:
        settings, version = await self.get_settings(user_id)
        now, market_open = self._now(), self._market_open()
        entries = await self._ledger(user_id)
        held = sorted(risk.build_book(entries, settings.risk.capital_toman, book)["positions"])
        marks = await data.load_marks(self.session, held, settings.freshness, now, market_open)
        hwm = (await self.session.execute(select(AlertEquityStateModel).where(
            AlertEquityStateModel.user_id == user_id, AlertEquityStateModel.book == book))).scalar_one_or_none()
        import pytz

        today = now.astimezone(pytz.timezone("Asia/Tehran")).date()
        state = risk.portfolio_state(settings.risk, entries, marks, today=today, book=book,
                                     hwm_toman=hwm.hwm_toman if hwm else None,
                                     hwm_flows_toman=hwm.hwm_flows_toman if hwm else 0.0)
        if persist_hwm and state["equity_complete"]:
            dd = state["drawdown"]
            await self.session.execute(
                pg_insert(AlertEquityStateModel).values(
                    user_id=user_id, book=book, hwm_toman=dd["high_water_mark_toman"],
                    hwm_flows_toman=dd["high_water_mark_flows_toman"], last_equity_toman=state["equity_toman"], updated_at=now)
                .on_conflict_do_update(index_elements=["user_id", "book"], set_={
                    "hwm_toman": dd["high_water_mark_toman"], "hwm_flows_toman": dd["high_water_mark_flows_toman"],
                    "last_equity_toman": state["equity_toman"], "updated_at": now}))
        state["settings_version"] = version
        state["blocked_new_entries"] = risk.new_entries_blocked(settings.risk, state, _kill_switch_on())
        state["marks"] = marks
        state["as_of"] = now
        return state

    async def portfolio_overview(self, user_id: str) -> dict[str, Any]:
        """Portfolio state + how the latest recommendations compete for the same cash."""
        state = await self.portfolio(user_id)
        monitors = await self.list_monitors(user_id)
        entries = [m for m in monitors if m["state"] == "conditional_entry" and m.get("entry")]
        wanted = sum(m["entry"]["value_toman"] for m in entries)
        sectors: dict[str, float] = {}
        for p in state["positions"]:
            sector = next((m.get("sector") for m in monitors if m["symbol"] == p["symbol"]), None) or "نامشخص"
            sectors[sector] = sectors.get(sector, 0.0) + (p.get("weight_pct") or 0.0)
        state["recommendations"] = {
            "conditional_entries": [{"symbol": m["symbol"], "value_toman": m["entry"]["value_toman"], "valid_until": m["valid_until"]} for m in entries],
            "requested_toman": wanted,
            "relationship": ("none" if not entries else "executable_together" if wanted <= state["cash_toman"] else "competing_for_same_cash"),
            "note": "هر اندازهٔ پیشنهادی جداگانه با کل نقدینگی سنجیده شده است؛ نقدینگی یکسان دو بار شمرده نمی‌شود — در حالت «رقابتی» فقط بخشی قابل اجراست و رتبه‌بندی خودکار انجام نمی‌شود.",
        }
        state["concentration"] = {
            "by_sector_pct": sectors,
            "limitations": ["هم‌بستگی و هم‌پوشانی دارایی صندوق‌ها با سهام محاسبه نمی‌شود: ترکیب دارایی صندوق‌ها (fund_holdings) در دسترس نیست. چند ابزار لزوماً تنوع نمی‌سازد."],
        }
        state["monitors_active"] = len(monitors)
        return state

    # ── lifecycle ───────────────────────────────────────────────────────────────────

    async def activate(self, user_id: str, symbol: str) -> dict[str, Any]:
        """Add an instrument to monitoring: identity → coverage → baseline analysis. Idempotent."""
        now = self._now()
        identity = await data.resolve_identity(self.session, symbol, now)
        if not identity["identified"]:
            raise EngineError(f"نماد «{identity['requested_symbol']}» در هیچ منبع داده‌ای شناسایی نشد؛ پایش بدون هویتِ تأییدشده آغاز نمی‌شود.")
        inserted = (await self.session.execute(
            pg_insert(AlertMonitorModel).values(
                id=new_id("mon"), user_id=user_id, symbol=identity["symbol"], ins_id=identity["ins_id"], isin=identity["isin"],
                name=identity["name"], category=identity["category"], supported=identity["supported"], status="active",
                monitoring_state="pending", identity=_dumps(identity), created_at=now, updated_at=now)
            # literal predicate: a bound parameter stops matching the partial index once
            # PostgreSQL switches the prepared statement to a generic plan
            .on_conflict_do_nothing(index_elements=["user_id", "symbol"], index_where=text("status = 'active'"))
            .returning(AlertMonitorModel.id))).scalar_one_or_none()
        if inserted is None:
            existing = (await self.session.execute(select(AlertMonitorModel).where(
                AlertMonitorModel.user_id == user_id, AlertMonitorModel.symbol == identity["symbol"],
                AlertMonitorModel.status == "active"))).scalar_one()
            return {"created": False, "monitor": await self.get_monitor(user_id, existing.id)}
        await self.analyze(inserted)
        return {"created": True, "monitor": await self.get_monitor(user_id, inserted)}

    async def remove(self, user_id: str, monitor_id: str, *, acknowledge_position: bool = False) -> dict[str, Any]:
        """Stop monitoring. Removal is not a sale: a recorded position needs explicit acknowledgement."""
        monitor = (await self.session.execute(select(AlertMonitorModel).where(
            AlertMonitorModel.id == monitor_id, AlertMonitorModel.user_id == user_id,
            AlertMonitorModel.status == "active").with_for_update())).scalar_one_or_none()
        if monitor is None:
            raise EngineError("پایش فعالی با این شناسه یافت نشد")
        settings, _ = await self.get_settings(user_id)
        book = risk.build_book(await self._ledger(user_id), settings.risk.capital_toman, "actual")
        position = book["positions"].get(monitor.symbol)
        if position and not acknowledge_position:
            return {"removed": False, "requires_acknowledgement": True, "position_quantity": position["quantity"],
                    "warning": f"برای «{monitor.symbol}» موقعیت ثبت‌شده ({position['quantity']:,.0f} واحد) وجود دارد. حذف از هشدارها به معنی فروش یا بسته‌شدن موقعیت نیست و ریسک آن باقی می‌ماند؛ با حذف، پایش و هشدارهای ریسک این نماد متوقف می‌شود."}
        now = self._now()
        monitor.status, monitor.removed_at, monitor.updated_at, monitor.monitoring_state = "removed", now, now, "removed"
        dependents = await data.has_active_dependents(self.session, monitor.ins_id, monitor.id)
        await notifier.notify(self.session, user_id=user_id, severity="risk_warning" if position else "informational",
                              event_type="monitoring_stopped", symbol=monitor.symbol, monitor_id=monitor.id,
                              title=f"پایش «{monitor.symbol}» متوقف شد" + (" — موقعیت ثبت‌شده همچنان باز است" if position else ""),
                              body="حذف از هشدارها به معنی فروش نیست." if position else "", now=now,
                              dedupe_key=f"{monitor.id}:monitoring_stopped", prefs=settings.notifications)
        await self.session.flush()
        return {"removed": True, "position_still_recorded": bool(position), "other_active_monitors_on_instrument": dependents,
                "shared_data_note": "دادهٔ بازار مشترک است و توسط همگام‌سازی عمومی نگهداری می‌شود؛ حذف این پایش دادهٔ مورد نیاز دیگران را حذف نمی‌کند."}

    async def analyze(self, monitor_id: str, *, market: dict[str, Any] | None = None, force: bool = False) -> dict[str, Any] | None:
        """One analysis pass. Returns ``None`` when the monitor is locked elsewhere or no longer active."""
        monitor = (await self.session.execute(select(AlertMonitorModel).where(
            AlertMonitorModel.id == monitor_id, AlertMonitorModel.status == "active")
            .with_for_update(skip_locked=True))).scalar_one_or_none()
        if monitor is None:
            return None
        now, market_open = self._now(), self._market_open()
        settings, settings_version = await self.get_settings(monitor.user_id)
        try:
            async with self.session.begin_nested():
                return await self._analyze_locked(monitor, settings, settings_version, now, market_open, market, force)
        except Exception as exc:  # noqa: BLE001 — one failing instrument must not block the others
            logger.exception("alert-engine: analysis failed for %s", monitor.symbol)
            monitor.monitoring_state, monitor.last_error, monitor.updated_at = "error", f"{type(exc).__name__}: {exc}"[:500], now
            await notifier.notify(self.session, user_id=monitor.user_id, severity="critical", event_type="analysis_failure",
                                  symbol=monitor.symbol, monitor_id=monitor.id, title=f"تحلیل «{monitor.symbol}» ناموفق بود",
                                  body="آخرین تحلیل معتبر همچنان نمایش داده می‌شود؛ توصیهٔ جدید صادر نمی‌شود.", now=now,
                                  dedupe_key=f"{monitor.id}:analysis_failure:{now:%Y%m%d%H}", prefs=settings.notifications)
            await self.session.flush()
            return {"state": "error", "error": monitor.last_error}

    async def _analyze_locked(self, monitor: AlertMonitorModel, settings: EngineSettings, settings_version: int,
                              now: datetime, market_open: bool, market: dict[str, Any] | None, force: bool) -> dict[str, Any]:
        identity = await data.resolve_identity(self.session, monitor.symbol, now,
                                               cached=json.loads(monitor.identity) if monitor.identity else None)
        if monitor.ins_id and identity.get("ins_id") and identity["ins_id"] != monitor.ins_id:
            identity["limitations"].append("شناسهٔ پایدار این نماد نسبت به زمان افزودن تغییر کرده است؛ هویت را بازبینی کنید.")
        inputs = await data.collect(self.session, identity, settings.freshness, now, market_open)
        cov = inputs["coverage"]
        market = market or await data.load_market(self.session, settings.freshness, now, market_open)
        cov["market_breadth"] = market["coverage"]

        previous = None
        if monitor.last_analysis_id:
            previous = (await self.session.execute(select(AlertAnalysisModel).where(
                AlertAnalysisModel.id == monitor.last_analysis_id))).scalar_one_or_none()
        regime = regime_mod.classify(market["breadth"], data_state=market["data_state"],
                                     previous=previous.regime if previous else None,
                                     equal_weight_change_pct=market["equal_weight_change_pct"])

        portfolio = await self.portfolio(monitor.user_id)
        position = next((p for p in portfolio["positions"] if p["symbol"] == monitor.symbol), None)

        snap = inputs["snapshot"]
        metrics = None
        if snap is not None and cov["quote"]["status"] in decision.USABLE:
            metrics = analytics.market_metrics(snap, low_limit=snap.get("low_limit"), high_limit=snap.get("high_limit"),
                                               avg_daily_volume=identity.get("avg_daily_volume"), closes=inputs["closes"])
            if metrics["history_discontinuities"]:
                cov["history"]["detail"] += f" — {metrics['history_discontinuities']} discontinuity(ies): only the stretch after the last one is used"

        opt_state = {"valid": "available", "last_session": "available", "stale": "stale",
                     "unavailable": "unavailable"}.get(cov["related_options"]["status"], "none")
        options = options_view.summarize(inputs["options_rows"] if opt_state != "none" else [], spot=(metrics or {}).get("price_last"),
                                         rate=settings.risk.assumed_risk_free_rate, feed_state=opt_state, fetched_at=inputs["options_stamp"])

        nav_info = None
        if inputs["nav"]:
            nav = inputs["nav"]
            nav_info = {"official_nav_redemption": nav["nav_redemption"], "official_nav_issue": nav["nav_issue"],
                        "official_date": nav["date_jalali"], "official_time": nav["time"], "retrieved_at": nav["retrieved_at"],
                        "source": nav["source"], "unit": "IRR", "status": cov["official_nav"]["status"],
                        "estimated_nav": None, "estimated_nav_note": "برآورد NAV لحظه‌ای انجام نمی‌شود (ترکیب دارایی در دسترس نیست).",
                        "premium_pct": analytics.premium_discount_pct((metrics or {}).get("price_last"), nav["nav_redemption"])
                        if cov["official_nav"]["status"] == "valid" else None,
                        "premium_note": None if cov["official_nav"]["status"] == "valid" else "NAV رسمی کهنه است؛ حباب/تخفیف محاسبه نمی‌شود."}

        blocked = portfolio["blocked_new_entries"]
        sizing = None
        if metrics and not position and identity["supported"] and identity["category"] != "option" and identity.get("fee_market"):
            from domain.trading.iran_costs import buy_rate, sell_rate

            ask = metrics["spread"]["ask"]
            sizing = risk.size_position(
                settings.risk, state=portfolio, regime=regime["regime"], symbol=monitor.symbol,
                entry_price_rial=ask or metrics["price_last"], daily_vol_pct=metrics["daily_volatility_pct"],
                spread_pct=metrics["spread"]["pct"], price_yesterday_rial=metrics["price_yesterday"],
                low_limit_rial=metrics["low_limit"], ask_depth_volume=metrics["ask_depth"]["volume"],
                avg_daily_volume=identity.get("avg_daily_volume"),
                buy_fee=buy_rate(identity["fee_market"]), sell_fee=sell_rate(identity["fee_market"]))

        events = [{"type": "disclosure", **d} for d in (inputs["disclosures"] or [])[:3]]
        rec = decision.build({"identity": identity, "coverage": cov, "metrics": metrics, "regime": regime, "options": options,
                              "nav": nav_info, "position": position, "sizing": sizing, "portfolio": portfolio,
                              "blocked": blocked, "settings": settings.risk, "now": now, "market_open": market_open, "events": events})

        input_hash = hashlib.sha256(_dumps({
            "quote": cov["quote"].get("as_of"), "price": (metrics or {}).get("price_last"), "options": inputs["options_stamp"],
            "nav": (inputs["nav"] or {}).get("date_jalali"), "cov": {k: v["status"] for k, v in cov.items()},
            "regime": regime["regime"], "pos": [position["quantity"], position["avg_cost_toman"]] if position else None,
            "settings": settings_version, "open": market_open, "blocked": blocked, "state": rec["state"],
            "trading_state": identity.get("trading_state"), "rules": RULES_VERSION}).encode()).hexdigest()
        if (not force and previous is not None and monitor.last_input_hash == input_hash
                and previous.valid_until and previous.valid_until > now):
            monitor.last_analyzed_at = monitor.updated_at = now
            await self.session.flush()
            return {"state": previous.state, "analysis_id": previous.id, "unchanged": True}

        changes = self._changes(json.loads(previous.report) if previous else None, rec, metrics, cov)
        report = {
            "recommendation": rec, "identity": identity, "coverage": cov, "market": metrics, "regime": regime,
            "options": options, "nav": nav_info, "disclosures": inputs["disclosures"] or [],
            "portfolio_snapshot": {k: portfolio[k] for k in ("cash_toman", "equity_toman", "exposure_pct", "equity_complete")},
            "changes_since_previous": changes,
            "audit": {"engine_version": ENGINE_VERSION, "rules_version": RULES_VERSION, "settings_version": settings_version,
                      "risk_settings": settings.to_dict()["risk"], "mode": MODE_PAPER, "data_label": "operational market data (not synthetic, not replay)",
                      "decision_time": now, "market_open": market_open, "input_hash": input_hash,
                      "position_confirmation": "user-confirmed ledger entry" if position else "no confirmed position"},
        }
        analysis = AlertAnalysisModel(
            id=new_id("ana"), monitor_id=monitor.id, user_id=monitor.user_id, symbol=monitor.symbol, created_at=now,
            valid_until=datetime.fromisoformat(rec["valid_until"]), state=rec["state"], subject=rec["subject"],
            regime=regime["regime"], mode=MODE_PAPER, engine_version=ENGINE_VERSION, rules_version=RULES_VERSION,
            settings_version=settings_version, input_hash=input_hash, supersedes_id=previous.id if previous else None,
            report=_dumps(report))
        self.session.add(analysis)

        degraded = [k for k, v in cov.items() if v["status"] in ("stale", "missing", "invalid") and k not in ("fundamentals", "news")]
        monitor.monitoring_state = {"unsupported": "unsupported", "restricted": "restricted",
                                    "insufficient_data": "blocked"}.get(rec["state"], "degraded" if degraded else "ok")
        monitor.identity, monitor.category, monitor.supported = _dumps(identity), identity["category"], identity["supported"]
        monitor.ins_id, monitor.isin, monitor.name = monitor.ins_id or identity["ins_id"], identity["isin"] or monitor.isin, identity["name"] or monitor.name
        monitor.last_analysis_id, monitor.last_analyzed_at, monitor.last_input_hash = analysis.id, now, input_hash
        monitor.last_error, monitor.updated_at = None, now
        await self.session.flush()
        await self._emit(monitor, analysis, rec, previous, settings, now, bool(position))
        return {"state": rec["state"], "analysis_id": analysis.id, "unchanged": False}

    @staticmethod
    def _changes(prev_report: dict[str, Any] | None, rec: dict[str, Any], metrics: dict[str, Any] | None,
                 cov: dict[str, dict[str, Any]]) -> list[str]:
        if prev_report is None:
            return ["نخستین تحلیل (خط پایه)"]
        out: list[str] = []
        prev_rec, prev_m, prev_cov = prev_report["recommendation"], prev_report.get("market") or {}, prev_report.get("coverage") or {}
        if prev_rec["state"] != rec["state"]:
            out.append(f"نتیجه: {prev_rec.get('state_label', prev_rec['state'])} ← {rec['state_label']}")
        if prev_rec.get("regime") != rec["regime"]:
            out.append(f"رژیم بازار: {prev_rec.get('regime')} ← {rec['regime']}")
        if metrics:
            if prev_m.get("price_last") and metrics["price_last"] and prev_m["price_last"] != metrics["price_last"]:
                out.append(f"قیمت: {prev_m['price_last']:,.0f} ← {metrics['price_last']:,.0f} ریال")
            if (prev_m.get("queue") or {}).get("state") != metrics["queue"]["state"]:
                out.append(f"وضعیت صف: {(prev_m.get('queue') or {}).get('state')} ← {metrics['queue']['state']}")
        for key, item in cov.items():
            before = (prev_cov.get(key) or {}).get("status")
            if before and before != item["status"]:
                out.append(f"پوشش داده «{key}»: {before} ← {item['status']}")
        return out or ["تغییر مهمی نسبت به تحلیل قبل دیده نشد"]

    async def _emit(self, monitor: AlertMonitorModel, analysis: AlertAnalysisModel, rec: dict[str, Any],
                    previous: AlertAnalysisModel | None, settings: EngineSettings, now: datetime, has_position: bool) -> None:
        state, label = rec["state"], rec["state_label"]
        reason = (rec["reasons"] or [""])[0]
        invalidation = (rec.get("invalidation_conditions") or [""])[0]
        body = reason + (f"\nشرط ابطال: {invalidation}" if invalidation else "")
        common: dict[str, Any] = {"user_id": monitor.user_id, "monitor_id": monitor.id, "analysis_id": analysis.id,
                                  "symbol": monitor.symbol, "prefs": settings.notifications, "now": now,
                                  "valid_until": analysis.valid_until}
        if previous is None:
            await notifier.notify(self.session, severity="informational", event_type="monitoring_started",
                                  title=f"پایش «{monitor.symbol}» آغاز شد — {label}", body=body,
                                  dedupe_key=f"{monitor.id}:monitoring_started", **common)
            return
        if previous.state == state:
            return
        revises = None
        if previous.state == "conditional_entry":
            revises = (await self.session.execute(select(AlertNotificationModel.id).where(
                AlertNotificationModel.monitor_id == monitor.id, AlertNotificationModel.event_type == "conditional_opportunity")
                .order_by(AlertNotificationModel.created_at.desc()).limit(1))).scalar_one_or_none()
        if state == "conditional_entry":
            severity, event = "opportunity", "conditional_opportunity"
        elif state == "exit_infeasible":
            severity, event = "critical", "exit_infeasible"
        elif state in RISK_STATES:
            severity, event = "risk_warning", f"position_{state}"
        elif state == "insufficient_data":
            severity, event = ("critical" if has_position else "risk_warning"), "data_outage"
        elif previous.state == "conditional_entry":
            severity, event = "material_change", "recommendation_invalidated"
        else:
            severity, event = "material_change", "state_changed"
        bucket = f"{now:%Y%m%d%H}" if severity in ("risk_warning", "critical") else f"{now:%Y%m%d}:{previous.state}"
        await notifier.notify(self.session, severity=severity, event_type=event,
                              title=f"«{monitor.symbol}»: {label}" + (" (ابطال توصیهٔ قبلی)" if revises else ""),
                              body=body, revises_id=revises, dedupe_key=f"{monitor.id}:{event}:{state}:{bucket}", **common)

    # ── read models ─────────────────────────────────────────────────────────────────

    async def list_monitors(self, user_id: str) -> list[dict[str, Any]]:
        rows = (await self.session.execute(select(AlertMonitorModel).where(
            AlertMonitorModel.user_id == user_id, AlertMonitorModel.status == "active")
            .order_by(AlertMonitorModel.created_at.desc()))).scalars().all()
        ids = [m.last_analysis_id for m in rows if m.last_analysis_id]
        analyses = {}
        if ids:
            analyses = {a.id: a for a in (await self.session.execute(select(AlertAnalysisModel).where(
                AlertAnalysisModel.id.in_(ids)))).scalars().all()}
        now = self._now()
        out = []
        for m in rows:
            a = analyses.get(m.last_analysis_id or "")
            report = json.loads(a.report) if a else None
            rec = report["recommendation"] if report else None
            identity = json.loads(m.identity) if m.identity else {}
            out.append({
                "id": m.id, "symbol": m.symbol, "name": m.name, "ins_id": m.ins_id, "isin": m.isin, "category": m.category,
                "category_label": data.CATEGORY_LABELS.get(m.category, m.category), "sector": identity.get("sector"),
                "supported": m.supported, "monitoring_state": m.monitoring_state, "last_error": m.last_error,
                "last_analyzed_at": m.last_analyzed_at, "created_at": m.created_at,
                "state": rec["state"] if rec else "pending", "state_label": rec.get("state_label") if rec else "در انتظار تحلیل",
                "subject": rec["subject"] if rec else None, "reason": (rec["reasons"] or [None])[0] if rec else None,
                "valid_until": a.valid_until if a else None, "expired": bool(a and a.valid_until and a.valid_until < now),
                "entry": rec.get("entry") if rec else None, "regime": a.regime if a else None,
                "quote_status": (report["coverage"].get("quote") or {}).get("status") if report else None,
                "quote_as_of": (report["coverage"].get("quote") or {}).get("as_of") if report else None,
                "price_last": (report.get("market") or {}).get("price_last") if report else None,
            })
        return out

    async def get_monitor(self, user_id: str, monitor_id: str, history: int = 20) -> dict[str, Any]:
        m = (await self.session.execute(select(AlertMonitorModel).where(
            AlertMonitorModel.id == monitor_id, AlertMonitorModel.user_id == user_id))).scalar_one_or_none()
        if m is None:
            raise EngineError("پایش یافت نشد")
        rows = (await self.session.execute(select(AlertAnalysisModel).where(AlertAnalysisModel.monitor_id == m.id)
                                           .order_by(AlertAnalysisModel.created_at.desc()).limit(history))).scalars().all()
        latest = json.loads(rows[0].report) if rows else None
        return {
            "id": m.id, "symbol": m.symbol, "name": m.name, "status": m.status, "monitoring_state": m.monitoring_state,
            "category": m.category, "supported": m.supported, "last_analyzed_at": m.last_analyzed_at,
            "last_error": m.last_error, "created_at": m.created_at, "removed_at": m.removed_at,
            "analysis_id": rows[0].id if rows else None, "report": latest,
            "history": [{"id": r.id, "created_at": r.created_at, "valid_until": r.valid_until, "state": r.state,
                         "state_label": decision.STATE_LABELS.get(r.state, r.state), "subject": r.subject,
                         "regime": r.regime, "rules_version": r.rules_version, "settings_version": r.settings_version,
                         "supersedes_id": r.supersedes_id} for r in rows],
        }

    async def active_monitor_ids(self) -> list[tuple[str, bool]]:
        """(monitor id, has-confirmed-position) — positions first, so risk is checked before ideas."""
        rows = (await self.session.execute(select(AlertMonitorModel.id, AlertMonitorModel.user_id, AlertMonitorModel.symbol)
                                           .where(AlertMonitorModel.status == "active", AlertMonitorModel.supported.is_(True),
                                                  AlertMonitorModel.category != "option"))).all()
        held = {(r.user_id, r.symbol) for r in (await self.session.execute(
            select(AlertLedgerEntryModel.user_id, AlertLedgerEntryModel.symbol)
            .where(AlertLedgerEntryModel.book == "actual", AlertLedgerEntryModel.entry_type == "buy").distinct())).all()}
        out = [(r.id, (r.user_id, r.symbol) in held) for r in rows]
        return sorted(out, key=lambda x: not x[1])

    async def list_notifications(self, user_id: str, *, limit: int = 50, unacknowledged_only: bool = False,
                                 since: datetime | None = None) -> list[dict[str, Any]]:
        stmt = select(AlertNotificationModel).where(AlertNotificationModel.user_id == user_id)
        if unacknowledged_only:
            stmt = stmt.where(AlertNotificationModel.acknowledged_at.is_(None))
        if since is not None:
            stmt = stmt.where(AlertNotificationModel.created_at > since)
        rows = (await self.session.execute(stmt.order_by(AlertNotificationModel.created_at.desc()).limit(limit))).scalars().all()
        return [notifier.to_dict(n) for n in rows]

    async def acknowledge(self, user_id: str, notification_id: str | None = None) -> int:
        stmt = update(AlertNotificationModel).where(AlertNotificationModel.user_id == user_id,
                                                    AlertNotificationModel.acknowledged_at.is_(None))
        if notification_id:
            stmt = stmt.where(AlertNotificationModel.id == notification_id)
        result = await self.session.execute(stmt.values(acknowledged_at=self._now()))
        return int(result.rowcount or 0)

    async def health(self, user_id: str) -> dict[str, Any]:
        """Monitoring + notification + data-source health for the dashboard."""
        now, market_open = self._now(), self._market_open()
        settings, _ = await self.get_settings(user_id)
        market = await data.load_market(self.session, settings.freshness, now, market_open)
        counts = dict((await self.session.execute(select(AlertMonitorModel.monitoring_state, func.count())
                       .where(AlertMonitorModel.user_id == user_id, AlertMonitorModel.status == "active")
                       .group_by(AlertMonitorModel.monitoring_state))).all())
        tg = dict((await self.session.execute(select(AlertNotificationModel.telegram_state, func.count())
                   .where(AlertNotificationModel.user_id == user_id).group_by(AlertNotificationModel.telegram_state))).all())
        from core.config import settings as app_settings

        chat = await notifier._chat_id_for(self.session, user_id)
        return {"as_of": now, "market_open": market_open, "market_data": market["coverage"],
                "monitors_by_state": counts, "telegram_by_state": tg, "kill_switch": _kill_switch_on(),
                "telegram": {"enabled_in_settings": settings.notifications.telegram_enabled,
                             "bot_configured": bool(getattr(app_settings, "telegram_bot_token", "")),
                             "chat_linked": bool(chat)},
                "cadence": "analysis job every 2 minutes; data freshness is bounded by the BrsApi sync cadence, not by this job"}
