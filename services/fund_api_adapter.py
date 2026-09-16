"""🏦 Fund Commercial API Adapter — Anti-Corruption Layer (ACL) + Data Quality Gate.

بخش ۳ از معماری Enterprise صندوق‌ها:
  - نام فیلدهای پرووایدر هرگز به Domain Model نشت نمی‌کند؛ همه‌چیز از طریق
    ``map_*`` به مدل داخلی (dict استاندارد) تبدیل می‌شود.
  - اعتبارسنجی ساختاری (Data Quality Rules) قبل از ورود به دیتابیس:
      * جمع وزن دارایی‌ها انحراف فاحش از ۱۰۰٪ ممنوع (تلورانس ۳٪ برای بدهی/تعهدات).
      * قیمت/NAV/تعداد واحد منفی یا صفرِ نامتعارف ممنوع.
      * تاریخ شمسی/میلادی باید ساخت‌یافته و معتبر باشد.
  - رکوردهای نامعتبر → جدول ``fund_ingestion_quarantine`` (بدون بلاک بقیه داده‌ها).
  - پرووایدر واقعی: کلاینت موجود ``brsapi.client.BrsApiClient`` (Token-Bucket +
    Backoff + Circuit Breaker + Budget Governor از قبل در آن پیاده‌سازی شده).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import jdatetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.time import utc_now_naive

logger = get_logger(__name__)

# ── Data Quality thresholds ──────────────────────────────────────────────────

WEIGHT_SUM_TOLERANCE_PCT = 3.0   # جمع وزن دارایی‌ها ۹۷..۱۰۳ (تلورانس بدهی)
MIN_POSITIVE_PRICE = 1.0         # ریال — زیر این = داده خراب
MAX_SANE_NAV = 500_000_000.0     # سقف منطقی NAV (ریال)
MAX_SANE_UNITS = 10**15          # سقف منطقی تعداد واحد

_JALALI_RE = re.compile(r"^(1[34]\d{2})[/\-.](\d{1,2})[/\-.](\d{1,2})$")
_GREG_RE = re.compile(r"^((?:19|20)\d{2})[/\-.](\d{1,2})[/\-.](\d{1,2})$")


# ── Validation result ────────────────────────────────────────────────────────


@dataclass
class RecordVerdict:
    """نتیجه اعتبارسنجی یک رکورد خام."""

    ok: bool
    reason: str = ""
    rule: str = ""


@dataclass
class QuarantineSink:
    """سینک قرنطینه — رکورد خراب را ثبت می‌کند ولی exception پرتاب نمی‌کند."""

    session: AsyncSession | None = None

    async def quarantine(
        self,
        *,
        source_endpoint: str,
        record: dict[str, Any],
        reason: str,
        rule: str,
        fund_id: str | None = None,
        isin: str | None = None,
    ) -> None:
        """Insert into ``fund_ingestion_quarantine`` — never raises.

        جدول قرنطینه باید همیشه قابل نوشتن باشد حتی اگر بقیه تراکنش rollback
        شود؛ بنابراین از یک session مستقل استفاده می‌کنیم (در صورت فراهم بودن
        factory) وگرنه فقط لاگ می‌کنیم.
        """
        fingerprint = _fingerprint(record)
        payload = json.dumps(record, ensure_ascii=False, default=str)[:8000]
        try:
            from core.database import async_session_factory

            if async_session_factory is not None:
                async with async_session_factory() as qs:
                    await qs.execute(
                        text(
                            """
                            INSERT INTO fund_ingestion_quarantine
                                (source_endpoint, fund_id, isin, record_fingerprint,
                                 payload_json, reject_reason, reject_rule, reviewed)
                            VALUES (:ep, :fid, :isin, :fp, :payload, :reason, :rule, FALSE)
                            """
                        ),
                        {
                            "ep": source_endpoint[:100],
                            "fid": fund_id,
                            "isin": isin,
                            "fp": fingerprint,
                            "payload": payload,
                            "reason": reason[:500],
                            "rule": rule[:100],
                        },
                    )
                    await qs.commit()
            else:
                logger.warning("QUARANTINE(no-db) %s %s: %s", source_endpoint, rule, reason)
        except Exception:
            # قرنطینه هرگز نباید جریان اصلی را بشکند.
            logger.exception("Failed to write quarantine record (rule=%s)", rule)

        # session درخواستی فقط برای log — commit جداگانه انجام نمی‌دهیم.
        _ = self.session


def _fingerprint(record: dict[str, Any]) -> str:
    raw = json.dumps(record, ensure_ascii=False, sort_keys=True, default=str)
    import hashlib

    return hashlib.sha1(raw.encode("utf-8"), usedforsecurity=False).hexdigest()[:40]


# ── Date helpers (شمسی ↔ میلادی، ساخت‌یافته) ────────────────────────────────


def parse_jalali(raw: Any) -> date | None:
    """تبدیل رشته تاریخ شمسی (۱۴۰۳/۰۵/۱۲ یا 1403-05-12 یا ارقام فارسی) به ``date`` میلادی.

    خروجی None یعنی تاریخ نامعتبر → رکورد باید قرنطینه شود.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    # Persian/Arabic digits → ASCII
    table = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    s = s.translate(table)
    m = _JALALI_RE.match(s)
    if not m:
        return None
    try:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            return None
        return jdatetime.date(y, mo, d).togregorian()
    except (ValueError, OverflowError):
        return None


def parse_gregorian(raw: Any) -> date | None:
    """تبدیل رشته تاریخ میلادی به ``date`` — None یعنی نامعتبر."""
    if raw is None:
        return None
    s = str(raw).strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    m = _GREG_RE.match(s)
    if not m:
        return None
    try:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return date(y, mo, d)
    except ValueError:
        return None


def normalize_date(raw: Any) -> date | None:
    """هوشمند: شمسی یا میلادی را تشخیص می‌دهد و ``date`` میلادی برمی‌گرداند."""
    if raw is None:
        return None
    s = str(raw).strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    if _JALALI_RE.match(s):
        return parse_jalali(s)
    if _GREG_RE.match(s):
        return parse_gregorian(s)
    return None


# ── Validators ───────────────────────────────────────────────────────────────


def validate_nav_record(rec: dict[str, Any]) -> RecordVerdict:
    """NAV صدور/ابطال باید مثبت و در محدوده منطقی باشد."""
    for key in ("nav_issue", "nav_redemption"):
        v = rec.get(key)
        if v is None:
            continue
        if v <= 0:
            return RecordVerdict(False, f"{key} must be positive, got {v}", "nav_non_positive")
        if v > MAX_SANE_NAV:
            return RecordVerdict(False, f"{key} exceeds sane maximum: {v}", "nav_out_of_range")
    if rec.get("nav_date") is None:
        return RecordVerdict(False, "nav_date missing or unparseable", "nav_date_invalid")
    return RecordVerdict(True)


def validate_holding(rec: dict[str, Any]) -> RecordVerdict:
    """وزن بین ۰..۱۰۰، مقادیر مثبت، نماد الزامی برای سهام."""
    w = rec.get("weight_pct")
    if w is not None and (w < 0 or w > 100):
        return RecordVerdict(False, f"weight_pct out of range: {w}", "holding_weight_range")
    for key in ("market_value", "book_value", "quantity"):
        v = rec.get(key)
        if v is not None and v < 0:
            return RecordVerdict(False, f"{key} is negative: {v}", "holding_negative_value")
    if rec.get("holding_type") == "equity" and not rec.get("instrument_symbol"):
        return RecordVerdict(False, "equity holding without instrument_symbol", "holding_symbol_missing")
    return RecordVerdict(True)


def validate_portfolio_weights(holdings: list[dict[str, Any]]) -> RecordVerdict:
    """جمع وزن دارایی‌ها نباید انحراف فاحش از ۱۰۰ داشته باشد."""
    total = sum(float(h.get("weight_pct") or 0) for h in holdings if h.get("weight_pct") is not None)
    if holdings and total > 0 and abs(total - 100.0) > WEIGHT_SUM_TOLERANCE_PCT:
        return RecordVerdict(
            False,
            f"weights sum to {total:.1f}% (tolerance ±{WEIGHT_SUM_TOLERANCE_PCT}%)",
            "portfolio_weight_sum",
        )
    return RecordVerdict(True)


def validate_quote(rec: dict[str, Any]) -> RecordVerdict:
    price = rec.get("last_price") or rec.get("close_price")
    if price is not None and price < MIN_POSITIVE_PRICE:
        return RecordVerdict(False, f"price {price} below minimum", "quote_price_invalid")
    units = rec.get("trade_volume")
    if units is not None and units < 0:
        return RecordVerdict(False, "negative trade_volume", "quote_volume_invalid")
    return RecordVerdict(True)


# ── Adapter ──────────────────────────────────────────────────────────────────


@dataclass
class FundApiAdapter:
    """لایه ایزولاسیون پرووایدر — ورودی خام، خروجی مدل داخلی + قرنطینه.

    تمام متدهای ``fetch_*`` خروجی استاندارد برمی‌گردانند؛ هیچ کلید خام
    پرووایدر (مثل ``psubtran`` یا ``Buy_I_Volume``) از این کلاس خارج نمی‌شود.
    """

    client: Any = None            # brsapi.client.BrsApiClient
    sync_service: Any = None      # brsapi.services.sync_service.BrsApiSyncService
    db_session: Any = None        # AsyncSession اختیاری برای منابع DB-محور
    quarantine: QuarantineSink = field(default_factory=QuarantineSink)

    # ── پایین‌دستی: کلاینت مشترک با rate-limit و resilience خودش ──

    async def _raw_fetch(self, endpoint: Any, params: dict[str, str]) -> Any | None:
        """Fetch با استفاده از کلاینت موجود — بدون لاگ کردن API key."""
        logger.debug("Provider fetch endpoint=%s params_keys=%s", endpoint.path, list(params))
        if self.client is None:
            from brsapi.client import get_client

            self.client = await get_client()
        try:
            result = await self.client.fetch(endpoint, params=params)
        except Exception as exc:  # noqa: BLE001 — پرووایدر نباید API را بشکند
            logger.warning("FundApiAdapter raw fetch failed: %s", type(exc).__name__)
            return None
        if result is None or not getattr(result, "success", False):
            err = getattr(result, "error", "unknown")
            # لاگ امن: فقط نوع خطا، بدون body/key
            logger.info("Provider fetch not successful: %s", str(err)[:120])
            return None
        # Result[T] wrapper: payload واقعی در ``value`` است و خود آن هم
        # BrsApiResponse (با فیلد data) است.
        inner = getattr(result, "value", None)
        if inner is None:
            return None
        if not getattr(inner, "success", True):
            logger.info("Provider response flagged failed: %s", str(getattr(inner, "error", ""))[:120])
            return None
        return getattr(inner, "data", None)

    # ── ۱. Universe — کشف کل صندوق‌های بازار ──

    async def fetch_universe(self) -> list[dict[str, Any]]:
        """کشف خودکار صندوق‌ها از snapshot های TSE + صندوق‌های IME.

        خروجی: لیست مدل داخلی:
          {fund_id, symbol, name, isin, ins_id, market, sector, fund_type_hint}
        """
        from sqlalchemy import select

        from brsapi.config import BrsApiEndpoints
        from brsapi.models.tsetmc import SymbolSnapshotModel
        from brsapi.services.sync_service import (
            _normalize_persian,
            fund_sector_sql_condition,
        )

        universe: dict[str, dict[str, Any]] = {}
        session = None
        if self.db_session is not None:
            session = self.db_session
        elif self.sync_service is not None and getattr(self.sync_service, "_session", None) is not None:
            session = self.sync_service._session

        # TSE ETFs — از آخرین snapshot هر نماد با sector صندوق
        if session is not None:
            try:
                # کوئری سبک: آخرین snapshot هر نمادِ دارای sector صندوق
                stmt = (
                    select(SymbolSnapshotModel)
                    .where(fund_sector_sql_condition(SymbolSnapshotModel.sector))
                    .order_by(SymbolSnapshotModel.id.desc())
                    .limit(3000)
                )
                rows = (await session.execute(stmt)).scalars().all()
                seen: set[str] = set()
                for r in rows:
                    sym = _normalize_persian(r.symbol or "")
                    if not sym or sym in seen:
                        continue
                    seen.add(sym)
                    universe[f"tse:{sym}"] = {
                        "fund_id": f"tse:{sym}",
                        "symbol": sym,
                        "name": r.name or sym,
                        "isin": r.isin or "",
                        "ins_id": r.ins_id or "",
                        "market": "tse",
                        "sector": r.sector or "",
                        "fund_type_hint": _hint_type(r.name or ""),
                    }
            except Exception:
                logger.exception("Universe discovery (TSE) failed")

        # IME funds — از API (یک call، 6/min محدودیت)
        raw = await self._raw_fetch(BrsApiEndpoints.IME_FUND, {})
        for item in _ensure_list(raw) if not isinstance(raw, list) else raw:
            mapped = self.map_ime_fund(item)
            if mapped is not None:
                universe.setdefault(mapped["fund_id"], mapped)

        return list(universe.values())

    # ── ۲. NAV ──

    async def fetch_nav(self, symbol: str, ins_id: str | None = None) -> dict[str, Any] | None:
        """NAV لحظه‌ای یک صندوق → مدل داخلی استاندارد یا None."""
        from brsapi.config import BrsApiEndpoints
        from brsapi.parsers.tsetmc import TsetmcParser

        raw = await self._raw_fetch(BrsApiEndpoints.NAV, {"l18": symbol})
        if raw is None:
            return None
        parsed = TsetmcParser.parse_nav(raw)
        if parsed is None:
            await self.quarantine.quarantine(
                source_endpoint="Tsetmc/Nav.php",
                record=raw if isinstance(raw, dict) else {"raw": str(raw)[:500]},
                reason="NAV payload is not a dict",
                rule="nav_payload_shape",
                isin=None,
            )
            return None
        nav_date = normalize_date(parsed.get("date"))
        rec = {
            "symbol": symbol,
            "ins_id": ins_id or "",
            "nav_issue": _safe_float(parsed.get("nav_issue")),
            "nav_redemption": _safe_float(parsed.get("nav_redemption")),
            "nav_date": nav_date,
            "source": "brsapi_nav",
        }
        verdict = validate_nav_record(rec)
        if not verdict.ok:
            await self.quarantine.quarantine(
                source_endpoint="Tsetmc/Nav.php",
                record=rec,
                reason=verdict.reason,
                rule=verdict.rule,
                isin=None,
            )
            return None
        return rec

    # ── ۳. گزارش پرتفوی کدال (ماهانه) ──

    async def fetch_portfolio_report(self, isin: str, period_end: date) -> list[dict[str, Any]] | None:
        """صورت وضعیت پرتفوی ماهانه از کدال → لیست holdings داخلی.

        پرووایدر کدال را فقط از طریق CODAL_ANNOUNCEMENT می‌خوانیم؛ پارس موفق
        holdings استانداردسازی می‌شود و رکوردهای خراب قرنطینه می‌شوند.
        """
        from brsapi.config import BrsApiEndpoints

        jy, jm, jd = jdatetime.date.fromgregorian(date=period_end).tuples()[:3]
        raw = await self._raw_fetch(
            BrsApiEndpoints.CODAL_ANNOUNCEMENT,
            {"category": "portfolio", "date_end": f"{jy:04d}/{jm:02d}/{jd:02d}"},
        )
        if raw is None:
            return None
        holdings = self.map_codal_holdings(raw, isin=isin, period_end=period_end)
        if holdings is None:
            return None
        verdict = validate_portfolio_weights(holdings)
        if not verdict.ok:
            await self.quarantine.quarantine(
                source_endpoint="Codal/Announcement.php",
                record={"fund_isin": isin, "period_end": str(period_end), "n": len(holdings)},
                reason=verdict.reason,
                rule=verdict.rule,
                isin=isin,
            )
            # وزن‌های مخرب را نمی‌نویسیم ولی ساختار را نگه می‌داریم → None
            return None
        return holdings

    # ── ۴. قیمت لحظه‌ای بازار صندوق ──

    async def fetch_market_quote(self, symbol: str, ins_id: str | None = None) -> dict[str, Any] | None:
        from brsapi.config import BrsApiEndpoints
        from brsapi.parsers.tsetmc import TsetmcParser

        raw = await self._raw_fetch(BrsApiEndpoints.SYMBOL_DETAIL, {"l18": symbol})
        if raw is None:
            return None
        parsed = TsetmcParser.parse_symbol_detail(raw) or {}
        rec = {
            "symbol": symbol,
            "ins_id": ins_id or "",
            "last_price": _safe_float(parsed.get("price_last")),
            "close_price": _safe_float(parsed.get("price_close")),
            "yesterday_price": _safe_float(parsed.get("price_yesterday")),
            "bid_price": _safe_float(parsed.get("bid_price_1")),
            "ask_price": _safe_float(parsed.get("ask_price_1")),
            "bid_volume": _safe_int(parsed.get("bid_volume_1")),
            "ask_volume": _safe_int(parsed.get("ask_volume_1")),
            "trade_volume": _safe_int(parsed.get("trade_volume")),
            "trade_value": _safe_float(parsed.get("trade_value")),
            "market_value": _safe_float(parsed.get("market_value")),
            "price_change_pct": _safe_float(parsed.get("price_close_change_pct")),
            "quoted_at": utc_now_naive(),
        }
        verdict = validate_quote(rec)
        if not verdict.ok:
            await self.quarantine.quarantine(
                source_endpoint="Tsetmc/Symbol.php",
                record=rec,
                reason=verdict.reason,
                rule=verdict.rule,
            )
            return None
        return rec

    # ── Mapperها (ACL core) ──

    def map_ime_fund(self, item: Any) -> dict[str, Any] | None:
        """یک آیتم خام IME Fund → مدل داخلی universe."""
        from brsapi.services.sync_service import _normalize_persian

        if not isinstance(item, dict):
            return None
        sym = _normalize_persian(str(item.get("l18") or item.get("symbol") or ""))
        if not sym:
            return None
        return {
            "fund_id": f"ime:{sym}",
            "symbol": sym,
            "name": str(item.get("l30") or item.get("name") or sym),
            "isin": str(item.get("isin") or ""),
            "ins_id": str(item.get("id") or item.get("ins_id") or ""),
            "market": "ime",
            "sector": "بورس کالا",
            "fund_type_hint": _hint_type(str(item.get("l30") or "")),
        }

    def map_codal_holdings(
        self, raw: Any, *, isin: str, period_end: date
    ) -> list[dict[str, Any]] | None:
        """پارس صورت پرتفوی کدال → لیست holdings داخلی استاندارد.

        فرمت مورد انتظار: لیست آیتم‌هایی با فیلدهای نماد/نام/تعداد/ارزش/وزن.
        هر آیتم نامعتبر قرنطینه می‌شود ولی بقیه ادامه می‌یابند.
        """
        items = raw if isinstance(raw, list) else (raw or {}).get("holdings") or []
        if not isinstance(items, list):
            return None
        out: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            htype = _map_holding_type(str(item.get("type") or item.get("group") or ""))
            rec = {
                "fund_isin": isin,
                "period_end_date": period_end,
                "holding_type": htype,
                "instrument_symbol": str(item.get("symbol") or item.get("l18") or "") or None,
                "instrument_name": str(item.get("name") or item.get("l30") or "") or None,
                "instrument_isin": str(item.get("isin") or "") or None,
                "quantity": _safe_float(item.get("quantity") or item.get("count")),
                "book_value": _safe_float(item.get("book_value")),
                "market_value": _safe_float(item.get("market_value") or item.get("value")),
                "weight_pct": _safe_float(item.get("weight") or item.get("weight_pct")),
                "source": "brsapi_codal",
            }
            verdict = validate_holding(rec)
            if not verdict.ok:
                # قرنطینه رکورد خراب — ادامه با بقیه holdings
                import asyncio

                asyncio.get_event_loop().create_task(
                    self.quarantine.quarantine(
                        source_endpoint="Codal/Announcement.php",
                        record=rec,
                        reason=verdict.reason,
                        rule=verdict.rule,
                        isin=isin,
                    )
                )
                continue
            out.append(rec)
        return out or None


# ── helpers ──────────────────────────────────────────────────────────────────


def _ensure_list(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("funds", "data", "items"):
            if isinstance(raw.get(key), list):
                return raw[key]
    return []


def _safe_float(v: Any) -> float | None:
    try:
        if v is None or v == "":
            return None
        f = float(str(v).replace(",", "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
        return f if f == f else None  # NaN guard
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> int | None:
    f = _safe_float(v)
    return int(f) if f is not None else None


def _hint_type(name: str) -> str:
    n = (name or "").lower()
    if "اهرم" in n:
        return "اهرمی"
    if "طلا" in n or "سکه" in n or "کالا" in n:
        return "بخشی"
    if "درآمد" in n or "ثابت" in n:
        return "درآمد ثابت"
    if "مختلط" in n:
        return "مختلط"
    return "سهامی"


def _map_holding_type(raw_type: str) -> str:
    t = (raw_type or "").lower()
    mapping = {
        "سهام": "equity",
        "اوراق": "fixed_income",
        "سپرده": "deposit",
        "طلا": "gold",
        "مشتقه": "derivative",
        "نقد": "cash",
        "equity": "equity",
        "bond": "fixed_income",
        "deposit": "deposit",
        "gold": "gold",
    }
    for key, value in mapping.items():
        if key in t:
            return value
    return "other"
