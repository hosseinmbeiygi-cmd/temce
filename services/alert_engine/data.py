"""Every database read of the alert engine, each value tagged with its provenance.

Reads only — the engine consumes what the existing BrsApi sync jobs already store and
never calls the provider itself, so it cannot spend API budget or bypass the governor.

Conventions:
* Market prices are **rials, unadjusted** (TSETMC via BrsApi). Tomans appear only in the
  strategy ledger; conversion lives in ``settings.rial_to_toman``.
* A coverage item is ``{"status", "source", "as_of", "age_seconds", "detail"}`` with
  status ∈ valid | last_session | stale | missing | invalid | not_applicable | unavailable.
  Zero, missing, stale and invalid are never collapsed into one another.
* Text from disclosures is untrusted content: it is carried as data and never interpreted.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from services.alert_engine import analytics
from services.alert_engine.settings import FreshnessPolicy

logger = get_logger(__name__)

READ_TIMEOUT_MS = 20_000

SRC_SNAPSHOT = "brsapi_symbol_snapshots ← BrsApi /Tsetmc/AllSymbols.php"
SRC_DETAILS = "brsapi_symbol_details ← BrsApi /Tsetmc/Symbol.php"
SRC_HISTORY = "brsapi_historical_daily ← BrsApi /Tsetmc/History.php"
SRC_OPTIONS = "brsapi_option_snapshots ← BrsApi /Tsetmc/Option.php"
SRC_NAV = "brsapi_nav_records ← BrsApi /Tsetmc/Nav.php"
SRC_CODAL = "brsapi_codal_announcements ← BrsApi /Codal/Announcement.php"
SRC_INDEX = "brsapi_index_values ← BrsApi /Tsetmc/Index.php"

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

CATEGORY_LABELS = {
    "equity": "سهام عادی", "equity_fund": "صندوق سهامی", "leveraged_fund": "صندوق اهرمی",
    "fixed_income_fund": "صندوق درآمد ثابت", "commodity_fund": "صندوق طلا/کالایی",
    "fund_other": "صندوق (زیرنوع نامشخص)", "option": "قرارداد اختیار معامله",
    "rights": "حق تقدم", "future": "قرارداد آتی", "commodity_certificate": "گواهی سپردهٔ کالایی",
    "unknown": "ناشناخته",
}

#: What the engine can honestly analyse per category *with the data that exists today*.
SUPPORT_MATRIX: dict[str, dict[str, Any]] = {
    "equity": {"supported": True, "modules": ["market", "liquidity", "disclosures", "related_options", "portfolio_risk"],
               "limitations": ["تحلیل بنیادی (صورت‌های مالی، سودآوری، ارزش‌گذاری) هنوز به این جریان وصل نشده است؛ تحلیل فعلی بازار، نقدشوندگی، افشاها، اختیارهای مرتبط و ریسک پرتفوی را پوشش می‌دهد."]},
    "equity_fund": {"supported": True, "modules": ["market", "liquidity", "official_nav", "disclosures", "related_options", "portfolio_risk"],
                    "limitations": ["NAV برآوردی از ترکیب دارایی‌ها ممکن نیست: جدول fund_holdings خالی است.", "تمرکز و هم‌پوشانی دارایی‌ها قابل محاسبه نیست."]},
    "leveraged_fund": {"supported": True, "modules": ["market", "liquidity", "official_nav", "disclosures", "related_options", "portfolio_risk"],
                       "limitations": ["ساختار واحدهای ممتاز/عادی و اهرم مؤثر قابل محاسبه نیست: جداول fund_unit_classes و fund_class_allocations خالی‌اند؛ اهرم برآورد نمی‌شود.",
                                       "NAV منتشرشده مشخص نمی‌کند متعلق به کدام طبقهٔ واحد است؛ مقایسهٔ قیمت با NAV فقط شاخصی تقریبی است.",
                                       "ریسک غیرخطی نزولی و وابستگی به مسیر مدل نشده است.", "NAV برآوردی از ترکیب دارایی‌ها ممکن نیست: fund_holdings خالی است."]},
    "fixed_income_fund": {"supported": True, "modules": ["market", "liquidity", "official_nav", "disclosures", "portfolio_risk"],
                          "limitations": ["ترکیب دارایی، کیفیت اعتباری، سررسید و دیرش در داده‌ها موجود نیست؛ فقط بازار و NAV رسمی پوشش داده می‌شود."]},
    "commodity_fund": {"supported": True, "modules": ["market", "liquidity", "official_nav", "disclosures", "portfolio_risk"],
                       "limitations": ["ارتباط با قیمت طلا/ارز و گواهی‌های پایه (basis) در این جریان محاسبه نمی‌شود."]},
    "fund_other": {"supported": True, "modules": ["market", "liquidity", "official_nav", "disclosures", "portfolio_risk"],
                   "limitations": ["زیرنوع صندوق از داده‌های ثبت‌شده مشخص نشد؛ فقط تحلیل بازار انجام می‌شود."]},
    "option": {"supported": True, "modules": ["contract_description"],
               "limitations": ["توصیهٔ خرید/فروش قرارداد اختیار خارج از دامنهٔ فعلی است و تأیید جداگانه می‌خواهد."]},
    "rights": {"supported": False, "modules": [],
               "limitations": ["تحلیل حق تقدم (مبلغ پذیره‌نویسی، مهلت، تبدیل، رقیق‌شدن) پیاده‌سازی نشده است."]},
    "future": {"supported": False, "modules": [], "limitations": ["قراردادهای آتی در دامنهٔ تأییدشده نیستند."]},
    "commodity_certificate": {"supported": False, "modules": [], "limitations": ["گواهی سپردهٔ کالایی در دامنهٔ فعلی پشتیبانی نمی‌شود."]},
    "unknown": {"supported": False, "modules": [], "limitations": ["هیچ منبع داده‌ای هویت این نماد را تأیید نکرد."]},
}

_CLASSIFY_MAP = {"equity": "equity", "fund": "equity_fund", "etf": "equity_fund", "leveraged_fund": "leveraged_fund",
                 "fixed_income": "fixed_income_fund", "commodity_fund": "commodity_fund", "option": "option",
                 "future": "future", "commodity_certificate": "commodity_certificate"}
#: ``brsapi_symbol_details.sub_sector`` — a registered field of the listing, not a name guess.
_SUB_SECTOR_MAP = {
    "صندوق های سرمایه گذاری اهرمی": "leveraged_fund",
    "صندوق سرمایه گذاری در اوراق با درآمدثابت": "fixed_income_fund",
    "صندوق کالایی مبتنی بر طلا": "commodity_fund",
    "صندوق سرمایه گذاری در سهام": "equity_fund",
}
_FEE_MARKET = {"equity_fund": "etf_equity", "leveraged_fund": "etf_equity", "fund_other": "etf_equity",
               "fixed_income_fund": "etf_fixed", "commodity_fund": "etf_commodity"}


def normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip()[:60]


def symbol_variants(symbol: str) -> list[str]:
    """The same ticker under Persian and Arabic code points (ی/ي، ک/ك)."""
    s = normalize_symbol(symbol)
    persian = s.replace("ي", "ی").replace("ك", "ک")
    arabic = s.replace("ی", "ي").replace("ک", "ك")
    return list(dict.fromkeys([s, persian, arabic]))


def _aware(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00").replace(" ", "T", 1))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            out = json.loads(value)
            return out if isinstance(out, dict) else {}
        except ValueError:
            return {}
    return {}


def jalali_to_date(value: Any) -> date | None:
    """'1405-08-20' / '۱۴۰۵/۰۸/۲۰' → Gregorian date; None when unparseable."""
    if not value:
        return None
    parts = str(value).translate(_PERSIAN_DIGITS).replace("/", "-").split("-")
    try:
        from persiantools.jdatetime import JalaliDate

        y, m, d = (int(p) for p in parts[:3])
        return JalaliDate(y, m, d).to_gregorian()
    except Exception:  # noqa: BLE001 — bad source date is reported as missing, not guessed
        return None


def coverage_item(status: str, source: str, as_of: datetime | date | None = None, detail: str = "",
                  now: datetime | None = None) -> dict[str, Any]:
    age = None
    if isinstance(as_of, datetime) and now is not None:
        age = max(0.0, (now - as_of).total_seconds())
    return {"status": status, "source": source, "as_of": as_of.isoformat() if as_of else None,
            "age_seconds": age, "detail": detail}


#: A timestamp this far in the future is a broken source clock, not live data —
#: negative age must never be accepted as fresh (audit F8, 2026-11-28).
FUTURE_TOLERANCE_SECONDS = 60.0


def freshness(as_of: datetime | None, *, now: datetime, market_open: bool, open_seconds: int,
              closed_hours: int) -> str:
    """valid (live, in session) | last_session (market closed, latest session's data)
    | stale | missing | invalid (a source clock running meaningfully ahead of us)."""
    if as_of is None:
        return "missing"
    age = (now - as_of).total_seconds()
    if age < -FUTURE_TOLERANCE_SECONDS:
        return "invalid"
    if market_open:
        return "valid" if age <= open_seconds else "stale"
    return "last_session" if age <= closed_hours * 3600 else "stale"


async def _rows(session: AsyncSession, sql: str, params: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Run one read inside a SAVEPOINT; a failed read is ``None`` (unavailable), not empty."""
    try:
        async with session.begin_nested():
            # bound every read: a slow source degrades to "unavailable" instead of hanging the pass
            await session.execute(text(f"SET LOCAL statement_timeout = {READ_TIMEOUT_MS}"))
            result = await session.execute(text(sql), params)
            return [dict(r) for r in result.mappings().all()]
    except Exception:  # noqa: BLE001
        logger.warning("alert-engine read failed: %s", sql.split("FROM")[-1][:60].strip(), exc_info=True)
        return None


async def _rows_by_symbol(session: AsyncSession, sql: str, symbol: str,
                          params: dict[str, Any] | None = None) -> list[dict[str, Any]] | None:
    """Run ``sql`` (which filters ``symbol = :sym``) once per spelling variant and concatenate.

    Plain equality keeps the planner on the ``(symbol, …)`` indexes; ``= ANY(array)`` with a
    prepared statement was observed falling back to a full backward scan for rare symbols.
    """
    out: list[dict[str, Any]] = []
    for variant in symbol_variants(symbol):
        rows = await _rows(session, sql, {**(params or {}), "sym": variant})
        if rows is None:
            return None
        out.extend(rows)
    return out


def _newest(rows: list[dict[str, Any]] | None, key: str = "fetched_at") -> dict[str, Any] | None:
    """The row with the latest ``key`` among per-variant results (None when there is none)."""
    if not rows:
        return None
    floor = datetime.min.replace(tzinfo=UTC)
    return max(rows, key=lambda r: _aware(r.get(key)) or floor)


# ── identity ───────────────────────────────────────────────────────────────────────────

CLASSIFICATION_TTL = timedelta(hours=24)


async def resolve_identity(session: AsyncSession, symbol: str, now: datetime | None = None,
                           cached: dict[str, Any] | None = None) -> dict[str, Any]:
    """Verify what a symbol is, from stored facts only. Never falls back to a default type.

    The instrument *class* is slow-changing and its probes are expensive, so a
    classification younger than ``CLASSIFICATION_TTL`` (passed as ``cached``) is reused;
    fast-changing identity fields (trading state, limits, volume) are always re-read.
    """
    now = now or datetime.now(UTC)
    reuse = None
    if cached and cached.get("identified") and cached.get("classified_at"):
        stamp = _aware(cached["classified_at"])
        if stamp and now - stamp <= CLASSIFICATION_TTL:
            reuse = cached
    sym = normalize_symbol(symbol)
    limitations: list[str] = []
    notes: list[str] = []  # classification-time findings, kept with a reused classification

    details = _newest(await _rows_by_symbol(session, """
        SELECT ins_id, symbol, name, isin, market, board, sector, sub_sector, state, fetched_at,
               price_lowest_allowed, price_highest_allowed, price_yesterday, trade_volume_avg_month
        FROM brsapi_symbol_details WHERE symbol = :sym ORDER BY fetched_at DESC NULLS LAST LIMIT 1
    """, sym))
    snap = _newest(await _rows_by_symbol(session, """
        SELECT ins_id, symbol, name, isin, sector, fetched_at FROM brsapi_symbol_snapshots
        WHERE symbol = :sym ORDER BY fetched_at DESC LIMIT 1
    """, sym))
    ids = await _rows_by_symbol(session, """
        SELECT DISTINCT ins_id FROM brsapi_symbol_details WHERE symbol = :sym AND ins_id IS NOT NULL
    """, sym)
    distinct_ids = {r["ins_id"] for r in ids or []}
    if len(distinct_ids) > 1:
        limitations.append(f"این نماد در منبع با {len(distinct_ids)} شناسهٔ متفاوت دیده شده است؛ جدیدترین شناسه استفاده شد.")

    base = details or snap or {}
    if not base and reuse and reuse.get("category") == "option":
        base = {k: reuse.get(k) for k in ("symbol", "name", "ins_id", "isin")}
    isin = (base.get("isin") or "").strip().upper() or None
    category, basis = "unknown", "هیچ جدولی این نماد را نمی‌شناسد."

    option_rows = None
    if reuse is None:
        option_rows = await _rows_by_symbol(session, """
            SELECT underlying_symbol, underlying_id, ins_id, isin, name, symbol FROM brsapi_option_snapshots
            WHERE symbol = :sym ORDER BY fetched_at DESC LIMIT 1
        """, sym)
    if reuse is not None:
        category, basis = reuse["category"], reuse["basis"]
        option_rows = [reuse["underlying"]] if reuse.get("underlying") else None
        limitations.extend(x for x in (reuse.get("classification_notes") or []))
    elif isin and isin.startswith("IRR"):
        category, basis = "rights", f"کد ISIN «{isin}» از ردهٔ حق تقدم (IRR) است."
    elif option_rows:
        category = "option"
        if not base:  # contract codes live only in the option feed
            base = {k: option_rows[0].get(k) for k in ("symbol", "name", "ins_id", "isin")}
            isin = (base.get("isin") or "").strip().upper() or None
        option_rows = [{k: option_rows[0][k] for k in ("underlying_symbol", "underlying_id")}]
        basis = f"در خوراک اختیار معامله (`brsapi_option_snapshots`) با دارایی پایهٔ «{option_rows[0]['underlying_symbol']}» فهرست شده است."
    else:
        try:
            from services.pre_buy_instrument import classify

            cls = await classify(session, sym)
        except Exception:  # noqa: BLE001
            logger.warning("alert-engine: classifier unavailable", exc_info=True)
            cls = None
        sub = _SUB_SECTOR_MAP.get((base.get("sub_sector") or "").strip())
        if cls is not None and cls.evidenced:
            category, basis = _CLASSIFY_MAP.get(cls.instrument_type, "unknown"), cls.basis
            if sub and sub != category and category in ("equity_fund", "equity"):
                notes.append(f"منابع طبقه‌بندی هم‌نظر نیستند: «{basis}» در برابر زیرگروه ثبت‌شده «{base.get('sub_sector')}». زیرگروه بورسی مبنا قرار گرفت.")
                category, basis = sub, f"`brsapi_symbol_details.sub_sector` = «{base.get('sub_sector')}»"
        elif sub:
            category, basis = sub, f"`brsapi_symbol_details.sub_sector` = «{base.get('sub_sector')}»"
        elif isin and isin[:3] == "IRT" and details:
            category, basis = "fund_other", f"کد ISIN «{isin}» از ردهٔ صندوق (IRT) است؛ زیرگروه ثبت‌شده شناخته نشد."
        elif isin and isin[:4] in ("IRO1", "IRO3", "IRO7") and details:
            category, basis = "equity", f"کد ISIN «{isin}» از ردهٔ سهام عادی و در `brsapi_symbol_details` فهرست شده است."

    limitations.extend(notes)
    support = SUPPORT_MATRIX[category]
    limitations.extend(support["limitations"])

    trading_state = None
    details_at = _aware(details.get("fetched_at")) if details else None
    if details and details_at and now - details_at <= timedelta(days=4):
        trading_state = (details.get("state") or "").strip() or None
    elif category != "unknown":
        limitations.append("وضعیت معاملاتی نماد (مجاز/متوقف) تازه نیست یا در دسترس نیست.")

    market = (base.get("market") or "").strip() if details else None
    if category == "equity":
        fee_market = "ifb_equity" if market and "فرابورس" in market else "tse_equity"
        if not market:
            limitations.append("بازار نماد نامشخص است؛ نرخ کارمزد بورس تهران فرض شد.")
    else:
        fee_market = _FEE_MARKET.get(category)

    return {
        "symbol": base.get("symbol") or sym, "requested_symbol": sym, "name": base.get("name"),
        "ins_id": str(base["ins_id"]) if base.get("ins_id") else None, "isin": isin,
        "market": market, "board": (details or {}).get("board"), "sector": base.get("sector"),
        "sub_sector": (details or {}).get("sub_sector"), "trading_state": trading_state,
        "category": category, "category_label": CATEGORY_LABELS[category], "basis": basis,
        "identified": category != "unknown", "supported": support["supported"],
        "support_note": support["limitations"][0] if not support["supported"] else None,
        "modules": support["modules"], "limitations": limitations, "fee_market": fee_market,
        "price_unit": "IRR", "price_adjustment": "unadjusted",
        "avg_daily_volume": (details or {}).get("trade_volume_avg_month"),
        "details_as_of": details_at.isoformat() if details_at else None,
        "sources": [SRC_DETAILS if details else None, SRC_SNAPSHOT if snap else None],
        "underlying": option_rows[0] if option_rows else None,
        "verified_at": now.isoformat(),
        "classified_at": reuse["classified_at"] if reuse else now.isoformat(),
        "classification_notes": (reuse.get("classification_notes") or []) if reuse else notes,
    }


# ── per-instrument inputs ──────────────────────────────────────────────────────────────

async def load_snapshot(session: AsyncSession, identity: dict[str, Any]) -> dict[str, Any] | None:
    key, param = ("ins_id = :k", identity["ins_id"]) if identity.get("ins_id") else ("symbol = :k", identity["symbol"])
    rows = await _rows(session, f"SELECT * FROM brsapi_symbol_snapshots WHERE {key} ORDER BY fetched_at DESC LIMIT 1",  # noqa: S608
                       {"k": param})
    if not rows:
        return None
    snap = rows[0]
    raw = _json(snap.pop("raw_json", None))
    snap["low_limit"] = analytics._num(raw.get("tmin")) or None
    snap["high_limit"] = analytics._num(raw.get("tmax")) or None
    snap["fetched_at"] = _aware(snap.get("fetched_at"))
    return snap


async def load_closes(session: AsyncSession, symbol: str, limit: int = 260) -> tuple[list[float], date | None]:
    """Daily closes oldest→newest, keyed by the *Jalali trade date* (``gregorian_date`` in
    this table is the load date, not the trade date, so it is not used)."""
    rows = await _rows_by_symbol(session, """
        SELECT date, max(price_close) AS price_close FROM brsapi_historical_daily
        WHERE symbol = :sym AND price_close > 0 AND date IS NOT NULL
        GROUP BY date ORDER BY date DESC LIMIT :n
    """, symbol, {"n": limit})
    if not rows:
        return [], None
    by_date: dict[str, float] = {}
    for r in rows:
        by_date[r["date"]] = max(by_date.get(r["date"], 0.0), float(r["price_close"]))
    days = sorted(by_date)[-limit:]
    return [by_date[d] for d in days], jalali_to_date(days[-1])


async def load_official_nav(session: AsyncSession, symbol: str) -> dict[str, Any] | None:
    rows = await _rows_by_symbol(session, """
        SELECT nav_issue, nav_redemption, date, time, fetched_at FROM brsapi_nav_records
        WHERE symbol = :sym ORDER BY date DESC, fetched_at DESC LIMIT 1
    """, symbol)
    if not rows:
        return None
    r = max(rows, key=lambda x: (str(x["date"] or ""), str(x["fetched_at"] or "")))
    return {"nav_redemption": analytics._num(r["nav_redemption"]), "nav_issue": analytics._num(r["nav_issue"]),
            "date_jalali": r["date"], "date": jalali_to_date(r["date"]), "time": r["time"],
            "retrieved_at": _aware(r["fetched_at"]), "source": SRC_NAV, "unit": "IRR"}


async def load_related_options(session: AsyncSession, ins_id: str | None) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Latest row per contract whose ``underlying_id`` equals the instrument's identifier.

    The link is the identifier, never a name resemblance. ``(None, None)`` ⇒ feed unreadable.
    """
    if not ins_id:
        return [], None
    latest = await _rows(session, "SELECT max(fetched_at) AS m FROM brsapi_option_snapshots WHERE underlying_id = :i", {"i": ins_id})
    if latest is None:
        return None, None
    stamp = latest[0]["m"]
    if not stamp:
        return [], None
    rows = await _rows(session, """
        SELECT DISTINCT ON (symbol) symbol, option_type, strike_price, date_end, days_remaining, contract_size,
               open_interest, price_last, trade_volume, bid_price_1, ask_price_1, bid_volume_1, ask_volume_1,
               underlying_price_last, time, fetched_at
        FROM brsapi_option_snapshots WHERE underlying_id = :i AND fetched_at >= :day
        ORDER BY symbol, fetched_at DESC
    """, {"i": ins_id, "day": str(stamp)[:10]})
    return rows, stamp


async def load_disclosures(session: AsyncSession, symbol: str, limit: int = 5) -> list[dict[str, Any]] | None:
    rows = await _rows_by_symbol(session, """
        SELECT title, date_publish, time_publish, link, code FROM brsapi_codal_announcements
        WHERE symbol = :sym ORDER BY date_publish DESC, time_publish DESC LIMIT :n
    """, symbol, {"n": limit})
    if rows is None:
        return None
    rows = sorted(rows, key=lambda x: (str(x["date_publish"] or ""), str(x["time_publish"] or "")), reverse=True)[:limit]
    return [{"title": str(r["title"] or "")[:300], "published_jalali": r["date_publish"], "time": r["time_publish"],
             "link": r["link"], "source": SRC_CODAL, "content_trust": "untrusted external text — shown as data"} for r in rows]


async def has_active_dependents(session: AsyncSession, ins_id: str | None, exclude_monitor_id: str) -> int:
    """How many *other* active monitors rely on this instrument's shared market data."""
    if not ins_id:
        return 0
    rows = await _rows(session, "SELECT count(*) AS n FROM alert_monitors WHERE ins_id = :i AND status = 'active' AND id <> :m",
                       {"i": ins_id, "m": exclude_monitor_id})
    return int(rows[0]["n"]) if rows else 0


# ── market-wide (shared by every monitor in one pass) ──────────────────────────────────

async def load_market(session: AsyncSession, policy: FreshnessPolicy, now: datetime, market_open: bool) -> dict[str, Any]:
    from services.alert_engine import regime as regime_mod

    latest = await _rows(session, "SELECT max(fetched_at) AS m FROM brsapi_symbol_snapshots", {})
    stamp = _aware(latest[0]["m"]) if latest else None
    state = freshness(stamp, now=now, market_open=market_open, open_seconds=policy.quote_open_seconds,
                      closed_hours=policy.quote_closed_hours)
    breadth = None
    if stamp is not None and state in ("valid", "last_session"):
        rows = await _rows(session, """
            SELECT DISTINCT ON (symbol) price_last_change_pct AS c FROM brsapi_symbol_snapshots
            WHERE fetched_at >= :cut AND trade_volume > 0 AND price_last > 0 AND price_last_change_pct IS NOT NULL
            ORDER BY symbol, fetched_at DESC
        """, {"cut": stamp - timedelta(hours=8)})
        if rows:
            breadth = regime_mod.breadth_from_changes([float(r["c"]) for r in rows])
    ew = None
    idx = await _rows(session, """
        SELECT index_equal_weight AS v, index_equal_weight_change AS ch, fetched_at FROM brsapi_index_values
        WHERE index_equal_weight > 0 ORDER BY fetched_at DESC LIMIT 1
    """, {})
    if idx:
        at = _aware(idx[0]["fetched_at"])
        if freshness(at, now=now, market_open=market_open, open_seconds=policy.index_open_seconds,
                     closed_hours=policy.index_closed_hours) in ("valid", "last_session"):
            v, ch = float(idx[0]["v"]), float(idx[0]["ch"] or 0)
            if v - ch > 0:
                ew = ch / (v - ch) * 100
    return {"breadth": breadth, "data_state": state, "as_of": stamp, "equal_weight_change_pct": ew,
            "coverage": coverage_item(state if breadth else ("missing" if state in ("valid", "last_session") else state),
                                      SRC_SNAPSHOT + " (market breadth)", stamp, now=now)}


async def load_marks(session: AsyncSession, symbols: list[str], policy: FreshnessPolicy, now: datetime,
                     market_open: bool) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        row = _newest(await _rows_by_symbol(session, """
            SELECT price_last, price_yesterday, fetched_at FROM brsapi_symbol_snapshots
            WHERE symbol = :sym ORDER BY fetched_at DESC LIMIT 1
        """, symbol))
        if not row:
            out[symbol] = {"quality": "missing"}
            continue
        at = _aware(row["fetched_at"])
        out[symbol] = {"price_rial": analytics._num(row["price_last"]),
                       "price_yesterday_rial": analytics._num(row["price_yesterday"]),
                       "as_of": at.isoformat() if at else None,
                       "quality": freshness(at, now=now, market_open=market_open,
                                            open_seconds=policy.quote_open_seconds, closed_hours=policy.quote_closed_hours)}
    return out


# ── assembled view for one instrument ──────────────────────────────────────────────────

async def collect(session: AsyncSession, identity: dict[str, Any], policy: FreshnessPolicy, now: datetime,
                  market_open: bool) -> dict[str, Any]:
    """All inputs for one instrument + the coverage matrix describing their quality."""
    cov: dict[str, dict[str, Any]] = {}
    out: dict[str, Any] = {"coverage": cov, "snapshot": None, "closes": [], "nav": None, "options_rows": None,
                           "options_stamp": None, "disclosures": None}

    snap = await load_snapshot(session, identity)
    if snap is None:
        cov["quote"] = coverage_item("missing", SRC_SNAPSHOT, detail="no snapshot stored for this instrument")
    else:
        status = freshness(snap["fetched_at"], now=now, market_open=market_open,
                           open_seconds=policy.quote_open_seconds, closed_hours=policy.quote_closed_hours)
        problems = analytics.validate_quote(snap)
        if problems:
            status = "invalid"
        cov["quote"] = coverage_item(status, SRC_SNAPSHOT, snap["fetched_at"], "; ".join(problems), now)
        cov["quote"]["exchange_time"] = snap.get("time")
        cov["quote"]["unit"] = "IRR (unadjusted)"
        out["snapshot"] = snap
        has_limits = bool(snap.get("low_limit") and snap.get("high_limit"))
        cov["price_limits"] = coverage_item(status if has_limits else "missing", SRC_SNAPSHOT + " (tmin/tmax)",
                                            snap["fetched_at"], "" if has_limits else "tmin/tmax absent in payload", now)

    closes, last_day = await load_closes(session, identity["symbol"])
    # the daily-history feed lags the live session: add the latest session's close when it is newer
    if closes and last_day and snap is not None and cov["quote"]["status"] in ("valid", "last_session"):
        import pytz

        session_day = snap["fetched_at"].astimezone(pytz.timezone("Asia/Tehran")).date()
        close = analytics._num(snap.get("price_close"))
        if session_day > last_day and close and close > 0:
            closes = [*closes, close]
            last_day = session_day
            out["history_note"] = "latest session close appended from the live snapshot"
    out["closes"] = closes
    if not closes:
        cov["history"] = coverage_item("missing", SRC_HISTORY)
    else:
        age_days = (now.date() - last_day).days if last_day else None
        ok = age_days is not None and age_days <= policy.history_days and len(closes) >= 21
        detail = f"{len(closes)} sessions, last trade date {last_day}"
        cov["history"] = coverage_item("valid" if ok else "stale" if len(closes) >= 21 else "invalid",
                                       SRC_HISTORY, last_day, detail if ok else detail + " — too old or too short")

    if "official_nav" in identity["modules"]:
        nav = await load_official_nav(session, identity["symbol"])
        if nav is None or not nav.get("nav_redemption") or not nav.get("date"):
            cov["official_nav"] = coverage_item("missing", SRC_NAV, detail="no published NAV stored for this fund")
        else:
            age = (now.date() - nav["date"]).days
            cov["official_nav"] = coverage_item("valid" if age <= policy.nav_official_days else "stale", SRC_NAV,
                                                nav["date"], f"NAV date {nav['date_jalali']} ({age} days old)")
            out["nav"] = nav
        cov["estimated_nav"] = coverage_item("unavailable", "fund_holdings (empty)",
                                             detail="portfolio holdings are not ingested — no estimated NAV is produced")
    else:
        cov["official_nav"] = coverage_item("not_applicable", SRC_NAV)

    if "related_options" in identity["modules"]:
        rows, stamp = await load_related_options(session, identity.get("ins_id"))
        out["options_rows"], out["options_stamp"] = rows, stamp
        if rows is None:
            cov["related_options"] = coverage_item("unavailable", SRC_OPTIONS, detail="options feed could not be read")
        elif not rows:
            cov["related_options"] = coverage_item("not_applicable", SRC_OPTIONS, detail="no contract lists this instrument as underlying")
        else:
            at = _aware(stamp)
            cov["related_options"] = coverage_item(
                freshness(at, now=now, market_open=market_open, open_seconds=policy.options_open_seconds,
                          closed_hours=policy.options_closed_hours), SRC_OPTIONS, at, f"{len(rows)} contracts", now)
    else:
        cov["related_options"] = coverage_item("not_applicable", SRC_OPTIONS)

    disclosures = await load_disclosures(session, identity["symbol"])
    out["disclosures"] = disclosures
    cov["disclosures"] = coverage_item(
        "unavailable" if disclosures is None else "valid" if disclosures else "missing", SRC_CODAL,
        detail="" if disclosures else "no announcement stored for this symbol")
    cov["fundamentals"] = coverage_item("unavailable", "codal financial statements",
                                        detail="not integrated into the alert workflow yet")
    cov["news"] = coverage_item("unavailable", "news_articles", detail="instrument-level news relevance is not integrated yet")
    return out
