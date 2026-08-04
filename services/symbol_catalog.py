"""Static symbol catalog — DB-free symbol search for the frontend.

The main API (``/instruments``, ``/watchlist``) searches the PostgreSQL-backed
``instruments`` / ``brsapi_symbol_snapshots`` tables. This module provides a
lightweight fallback catalog built from the curated symbol lists already in the
codebase (stocks, funds, ETFs) plus ``scripts/selected_symbols.json`` when
present, so ``GET /api/v1/symbols/search`` keeps working even when PostgreSQL
is unreachable or still seeding data.

The catalog is built once at import time and is intentionally simple: symbol,
name and sector only. Live prices are NOT provided here — use the market
endpoints for enriched data.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from core.logging import get_logger

logger = get_logger(__name__)

# Max results returned by ``search()`` when no explicit limit is given.
DEFAULT_LIMIT = 25

# ── Cross-market curated symbol lists (BrsApi / Tabdeal sources) ──
# Each tuple is ``(symbol, Persian name)``. ``sector`` is assigned per group
# so the frontend can display and filter by market type.

# Gold & coins — BrsApi ``Gold_Currency_Pro`` section=gold (symbols from
# ``brsapi/services/history_fetch_service.GOLD_SYMBOLS``).
GOLD_COIN_SYMBOLS: list[tuple[str, str]] = [
    ("IR_GOLD_18K", "طلای ۱۸ عیار"),
    ("IR_GOLD_24K", "طلای ۲۴ عیار"),
    ("IR_GOLD_MELTED", "طلای آب‌شده"),
    ("IR_COIN_1G", "سکه یک گرمی"),
    ("IR_COIN_BAHAR", "سکه بهار آزادی"),
    ("IR_COIN_EMAMI", "سکه امامی"),
    ("IR_COIN_HALF", "نیم سکه"),
    ("IR_COIN_QUARTER", "ربع سکه"),
    ("IR_PCOIN_100MG", "سکه پارسیان ۱۰۰ میلی‌گرمی"),
    ("IR_PCOIN_200MG", "سکه پارسیان ۲۰۰ میلی‌گرمی"),
    ("IR_PCOIN_300MG", "سکه پارسیان ۳۰۰ میلی‌گرمی"),
    ("IR_PCOIN_400MG", "سکه پارسیان ۴۰۰ میلی‌گرمی"),
    ("IR_PCOIN_500MG", "سکه پارسیان ۵۰۰ میلی‌گرمی"),
    ("IR_PCOIN_1G", "سکه پارسیان ۱ گرمی"),
    ("IR_PCOIN_1-1G", "سکه پارسیان ۱.۱ گرمی"),
    ("IR_PCOIN_1-2G", "سکه پارسیان ۱.۲ گرمی"),
    ("IR_PCOIN_1-3G", "سکه پارسیان ۱.۳ گرمی"),
    ("IR_PCOIN_1-4G", "سکه پارسیان ۱.۴ گرمی"),
    ("IR_PCOIN_1-5G", "سکه پارسیان ۱.۵ گرمی"),
]

# Currencies — BrsApi ``Gold_Currency_Pro`` section=currency (IRR-priced FX).
CURRENCY_SYMBOLS: list[tuple[str, str]] = [
    ("USD", "دلار آمریکا"),
    ("EUR", "یورو"),
    ("GBP", "پوند انگلیس"),
    ("AED", "درهم امارات"),
    ("TRY", "لیر ترکیه"),
    ("CNY", "یوآن چین"),
    ("RUB", "روبل روسیه"),
    ("SEK", "کرون سوئد"),
    ("JPY", "ین ژاپن"),
    ("CHF", "فرانک سوئیس"),
    ("AZN", "منات آذربایجان"),
    ("OMR", "ریال عمان"),
    ("KWD", "دینار کویت"),
    ("SAR", "ریال سعودی"),
    ("IQD", "دینار عراق"),
]

# Cryptocurrencies — BrsApi ``Cryptocurrency.php`` / Tabdeal (popular coins).
CRYPTO_SYMBOLS: list[tuple[str, str]] = [
    ("BTC", "بیت‌کوین"),
    ("ETH", "اتریوم"),
    ("USDT", "تتر"),
    ("BNB", "بایننس کوین"),
    ("SOL", "سولانا"),
    ("XRP", "ریپل"),
    ("DOGE", "دوج‌کوین"),
    ("ADA", "کاردانو"),
    ("TRX", "ترون"),
    ("DOT", "پولکادات"),
    ("LTC", "لایت‌کوین"),
    ("LINK", "چین‌لینک"),
    ("AVAX", "آوالانچ"),
    ("MATIC", "پالیگان"),
    ("SHIB", "شیبا اینو"),
    ("UNI", "یونی‌سواپ"),
    ("ATOM", "کازموس"),
    ("XLM", "استلار"),
    ("NEAR", "نیر پروتکل"),
    ("APT", "آپتوس"),
    ("TON", "تون کوین"),
    ("FIL", "فایل‌کوین"),
    ("ARB", "آربیتروم"),
]

# Global commodities — ``brsapi/parsers/commodity.py`` sets (symbol → name).
COMMODITY_SYMBOLS: list[tuple[str, str]] = [
    ("XAUUSD", "طلا (اونس جهانی)"),
    ("XAGUSD", "نقره (اونس جهانی)"),
    ("XPTUSD", "پلاتین (اونس جهانی)"),
    ("XPDUSD", "پالادیوم (اونس جهانی)"),
    ("COPPER", "مس"),
    ("ALUMINUM", "آلومینیوم"),
    ("ZINC", "روی"),
    ("LEAD", "سرب"),
    ("NICKEL", "نیکل"),
    ("BRENT", "نفت برنت"),
    ("WTI", "نفت وست تگزاس"),
    ("NGAS", "گاز طبیعی"),
    ("GASOLINE", "بنزین"),
    ("GASOIL", "گازوئیل"),
]

# IME (Iran Mercantile Exchange / بورس کالای ایران) — futures, options,
# certificates (گواهی سپرده), commodity funds, and physical trades.
# Contract codes are from ``brsapi/parsers/ime.py`` and ``brsapi/config.py``.
# ``sector`` is assigned as "بورس کالا" so the frontend can filter by it.
# IME (Iran Mercantile Exchange / بورس کالای ایران) — futures, options,
# certificates (گواهی سپرده), commodity funds, and physical trades.
# Contract codes use ``IME_`` prefix to avoid collisions with stock symbols
# (e.g., ``فولاد`` is a TSE stock, ``IME_FUTURE_FOLAD`` is the IME futures contract).
# ``sector`` is assigned as ``بورس کالا`` so the frontend can filter by it.
IME_SYMBOLS: list[tuple[str, str]] = [
    # ── Futures contracts (قراردادهای آتی) ──
    ("IME_FUTURE_ZAFARAN", "قرارداد آتی زعفران"),
    ("IME_FUTURE_PISTACHIO", "قرارداد آتی پسته"),
    ("IME_FUTURE_CUMIN", "قرارداد آتی زیره"),
    ("IME_FUTURE_SUGAR", "قرارداد آتی قند"),
    ("IME_FUTURE_RICE", "قرارداد آتی برنج"),
    ("IME_FUTURE_DATE", "قرارداد آتی خرما"),
    ("IME_FUTURE_CEMENT", "قرارداد آتی سیمان"),
    ("IME_FUTURE_STEEL", "قرارداد آتی فولاد"),
    ("IME_FUTURE_COPPER", "قرارداد آتی مس"),
    ("IME_FUTURE_ALUMINUM", "قرارداد آتی آلومینیوم"),
    ("IME_FUTURE_ZINC", "قرارداد آتی روی"),
    ("IME_FUTURE_LEAD", "قرارداد آتی سرب"),
    ("IME_FUTURE_NICKEL", "قرارداد آتی نیکل"),
    ("IME_FUTURE_GOLD_BULLION", "قرارداد آتی شمش طلا"),
    ("IME_FUTURE_FUEL_OIL", "قرارداد آتی نفت کوره"),
    ("IME_FUTURE_BITUMEN", "قرارداد آتی قیر"),
    # ── Certificates / Depository Receipts (گواهی سپرده کالایی) ──
    ("IME_CERT_ZAFARAN", "گواهی سپرده زعفران"),
    ("IME_CERT_PISTACHIO", "گواهی سپرده پسته"),
    ("IME_CERT_RICE", "گواهی سپرده برنج"),
    ("IME_CERT_DATE", "گواهی سپرده خرما"),
    ("IME_CERT_CEMENT", "گواهی سپرده سیمان"),
    ("IME_CERT_STEEL", "گواهی سپرده فولاد"),
    ("IME_CERT_COPPER", "گواهی سپرده مس"),
    ("IME_CERT_GOLD_BULLION", "گواهی سپرده شمش طلا"),
    ("IME_CERT_ZAFARAN_NEGIN", "گواهی سپرده زعفران نگین"),
    ("IME_CERT_CUMIN", "گواهی سپرده زیره"),
    # ── Commodity funds (صندوق‌های کالایی) ──
    ("IME_FUND_GOLD", "صندوق سرمایه‌گذاری طلا"),
    ("IME_FUND_ZAFARAN", "صندوق سرمایه‌گذاری زعفران"),
    ("IME_FUND_PISTACHIO", "صندوق سرمایه‌گذاری پسته"),
    ("IME_FUND_STEEL", "صندوق سرمایه‌گذاری فولاد"),
    ("IME_FUND_OIL", "صندوق سرمایه‌گذاری نفت"),
    # ── IME Option contracts (اختیار معامله بورس کالا) ──
    ("IME_OPTION_ZAFARAN", "اختیار معامله زعفران"),
    ("IME_OPTION_PISTACHIO", "اختیار معامله پسته"),
    ("IME_OPTION_STEEL", "اختیار معامله فولاد"),
    ("IME_OPTION_COPPER", "اختیار معامله مس"),
    ("IME_OPTION_GOLD_BULLION", "اختیار معامله شمش طلا"),
]

# Tabdeal — Iranian cryptocurrency exchange (صرافی تَب‌دیل).
# Spot pairs: base asset + quote asset (IRT = تومان, USDT = تتر).
# ``sector`` is assigned as ``رمزارز`` so the frontend can filter alongside
# other crypto symbols from the BrsApi catalog.
TABDEAL_SYMBOLS: list[tuple[str, str]] = [
    # ── IRT pairs (تومان) — most traded on Tabdeal ──
    ("BTCIRT", "بیت‌کوین-تومان"),
    ("ETHIRT", "اتریوم-تومان"),
    ("USDTIRT", "تتر-تومان"),
    ("BNBIRT", "بایننس کوین-تومان"),
    ("SOLIRT", "سولانا-تومان"),
    ("XRPIRT", "ریپل-تومان"),
    ("DOGEIRT", "دوج‌کوین-تومان"),
    ("ADAIRT", "کاردانو-تومان"),
    ("TRXIRT", "ترون-تومان"),
    ("DOTIRT", "پولکادات-تومان"),
    ("LTCIRT", "لایت‌کوین-تومان"),
    ("LINKIRT", "چین‌لینک-تومان"),
    ("AVAXIRT", "آوالانچ-تومان"),
    ("MATICIRT", "پالیگان-تومان"),
    ("SHIBIRT", "شیبا اینو-تومان"),
    ("UNIIRT", "یونی‌سواپ-تومان"),
    ("ATOMIRT", "کازموس-تومان"),
    ("XLMIRT", "استلار-تومان"),
    ("NEARIRT", "نیر پروتکل-تومان"),
    ("APTIRT", "آپتوس-تومان"),
    ("TONIRT", "تون کوین-تومان"),
    ("FILIRT", "فایل‌کوین-تومان"),
    ("ARBIRT", "آربیتروم-تومان"),
    ("PEPEIRT", "پپه-تومان"),
    ("INJIRT", "اینجکتیو-تومان"),
    ("AAVEIRT", "آوه-تومان"),
    ("FTMIRT", "فانتوم-تومان"),
    ("THETAIRT", "تتا-تومان"),
    ("EGLDIRT", "الروند-تومان"),
    ("SANDIRT", "سندباکس-تومان"),
    ("MANAIRT", "دیسنترالند-تومان"),
    ("AXSIRT", "اکسی اینفینیتی-تومان"),
    ("CHZIRT", "چیلیز-تومان"),
    ("ENJIRT", "انجین-تومان"),
    ("DYDXIRT", "دی‌وای‌دی‌ایکس-تومان"),
    # ── USDT pairs (تتر) — major altcoins ──
    ("BTCUSDT", "بیت‌کوین-تتر"),
    ("ETHUSDT", "اتریوم-تتر"),
    ("SOLUSDT", "سولانا-تتر"),
    ("XRPUSDT", "ریپل-تتر"),
    ("DOGEUSDT", "دوج‌کوین-تتر"),
    ("ADAUSDT", "کاردانو-تتر"),
    ("TRXUSDT", "ترون-تتر"),
    ("DOTUSDT", "پولکادات-تتر"),
    ("LTCUSDT", "لایت‌کوین-تتر"),
    ("LINKUSDT", "چین‌لینک-تتر"),
    ("AVAXUSDT", "آوالانچ-تتر"),
    ("MATICUSDT", "پالیگان-تتر"),
    ("BCHUSDT", "بیت‌کوین کش-تتر"),
    ("ATOMUSDT", "کازموس-تتر"),
    ("XLMUSDT", "استلار-تتر"),
]


def _load_selected_symbols() -> list[dict[str, str]]:
    """Best-effort load of ``scripts/selected_symbols.json`` (symbol/name/sector)."""
    path = Path(__file__).resolve().parents[1] / "scripts" / "selected_symbols.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return [
            {
                "symbol": str(item.get("symbol", "")).strip(),
                "name": str(item.get("name", "") or ""),
                "sector": str(item.get("sector", "") or ""),
            }
            for item in data
            if isinstance(item, dict) and str(item.get("symbol", "")).strip()
        ]
    except Exception:  # noqa: BLE001 - catalog must never crash on a bad file
        logger.warning("Could not parse selected_symbols.json — using curated lists only", exc_info=True)
        return []


def _build_catalog() -> list[dict[str, str]]:
    """Merge every curated symbol list into a de-duplicated static catalog."""
    seen: dict[str, dict[str, str]] = {}

    def _add(symbol: str, name: str = "", sector: str = "") -> None:
        sym = (symbol or "").strip()
        if not sym:
            return
        entry = seen.setdefault(sym, {"symbol": sym, "name": name, "sector": sector})
        if name and not entry["name"]:
            entry["name"] = name
        if sector and not entry["sector"]:
            entry["sector"] = sector

    # Popular stocks (watchlist defaults)
    try:
        from services.watchlist_service import DEFAULT_SYMBOLS

        for sym in DEFAULT_SYMBOLS:
            _add(sym)
    except Exception:  # noqa: BLE001
        logger.debug("watchlist DEFAULT_SYMBOLS unavailable", exc_info=True)

    # Known fund symbols (sector: صندوق)
    try:
        from services.fund_sync_service import KNOWN_FUND_SYMBOLS

        for sym in KNOWN_FUND_SYMBOLS:
            _add(sym, sector="صندوق")
    except Exception:  # noqa: BLE001
        logger.debug("fund KNOWN_FUND_SYMBOLS unavailable", exc_info=True)

    # ETF symbols (BrsApi) (sector: صندوق)
    try:
        from brsapi.constants import BRSAPI_ETF_SYMBOLS

        for sym in BRSAPI_ETF_SYMBOLS:
            _add(sym, sector="صندوق")
    except Exception:  # noqa: BLE001
        logger.debug("BRSAPI_ETF_SYMBOLS unavailable", exc_info=True)

    # Gold & coins (sector: طلا و سکه)
    for sym, name in GOLD_COIN_SYMBOLS:
        _add(sym, name, sector="طلا و سکه")

    # Currencies (sector: ارز)
    for sym, name in CURRENCY_SYMBOLS:
        _add(sym, name, sector="ارز")

    # Cryptocurrencies (sector: رمزارز)
    for sym, name in CRYPTO_SYMBOLS:
        _add(sym, name, sector="رمزارز")

    # Global commodities (sector: کامودیتی)
    for sym, name in COMMODITY_SYMBOLS:
        _add(sym, name, sector="کامودیتی")

    # IME — Iran Mercantile Exchange / بورس کالا (sector: بورس کالا)
    for sym, name in IME_SYMBOLS:
        _add(sym, name, sector="بورس کالا")

    # Tabdeal — Iranian crypto exchange (جفت‌ارزهای تومانی/تتری صرافی تَب‌دیل)
    for sym, name in TABDEAL_SYMBOLS:
        _add(sym, name, sector="رمزارز")

    # Enriched entries (symbol + name + sector) from selected_symbols.json
    for item in _load_selected_symbols():
        _add(item["symbol"], item.get("name", ""), item.get("sector", ""))

    return sorted(seen.values(), key=lambda s: s["symbol"])


# ── Finglish transliteration (Persian → Latin) ─────────────────
# Lets the search find a symbol by its Latin spelling, e.g. ``folad``
# matches ``فولاد`` and ``zafaran`` matches ``زعفران``.
#
# Each Persian letter maps to its possible Finglish renderings. The first
# entry is the most common one; all are tried so common variations work
# (``و`` as o/u/v/w, ``ی`` as y/i, ``ع`` as silent a/e/gh, ...).
_FA_CANDIDATES: dict[str, tuple[str, ...]] = {
    "آ": ("a",),
    "ا": ("a",),
    "أ": ("a",),
    "إ": ("a",),
    "ب": ("b",),
    "پ": ("p",),
    "ت": ("t",),
    "ث": ("s", "th"),
    "ج": ("j",),
    "چ": ("ch", "c", "j"),
    "ح": ("h",),
    "خ": ("kh", "x", "h"),
    "د": ("d",),
    "ذ": ("z",),
    "ر": ("r",),
    "ز": ("z",),
    "ژ": ("zh", "j", "z"),
    "س": ("s",),
    "ش": ("sh", "s", "ch"),
    "ص": ("s",),
    "ض": ("z", "d"),
    "ط": ("t",),
    "ظ": ("z",),
    "ع": ("a", "e", "gh"),  # short vowels already injected by _SHORT_VOWEL
    "غ": ("gh", "g"),
    "ف": ("f",),
    "ق": ("gh", "g", "q"),
    "ک": ("k", "c"),
    "ك": ("k", "c"),
    "گ": ("g", "gh"),
    "ل": ("l",),
    "م": ("m",),
    "ن": ("n",),
    "و": ("o", "u", "v", "w"),
    "ه": ("h",),
    "ی": ("y", "i"),
    "ي": ("y", "i"),
    "ئ": ("y", "i", "e"),
    "ة": ("h", "t"),
    "۰": ("0",),
    "۱": ("1",),
    "۲": ("2",),
    "۳": ("3",),
    "۴": ("4",),
    "۵": ("5",),
    "۶": ("6",),
    "۷": ("7",),
    "۸": ("8",),
    "۹": ("9",),
}

# Short vowels are not written in Persian (فتحه/کسره/ضمه), so Finglish
# queries may insert them — ``tala`` for طلا, ``foolad`` for فولاد. This
# fragment is allowed (up to two) between every pair of transliterated
# letters to tolerate those insertions.
_SHORT_VOWEL = r"(?:[aeiouy]{0,2})"


# Collapse repeated letters (``foolad`` → ``folad``) so double-vowel
# misspellings still match.
_REPEAT_RE = re.compile(r"(.)\1+")


def _collapse_repeats(text: str) -> str:
    return _REPEAT_RE.sub(r"\1", text)


def _word_regex(word: str) -> str | None:
    """Build a regex matching any prefix of the word's Finglish spelling.

    Each Persian letter becomes an alternation of its possible Latin
    renderings; short vowels are allowed between letters and every group
    after the first is optional, so ``tala`` matches ``طلای`` and
    ``folad``/``foolad`` both match ``فولاد``. Returns ``None`` for empty
    words.
    """
    groups: list[str] = []
    for ch in word:
        if ch == "\u200c":  # ZWNJ (نیم‌فاصله) — invisible, skip
            continue
        candidates = _FA_CANDIDATES.get(ch)
        if candidates is not None:
            groups.append("(?:" + "|".join(re.escape(c) for c in candidates) + ")")
        elif ch.isascii():
            groups.append(re.escape(ch.lower()))
        else:
            groups.append(re.escape(ch))
    if not groups:
        return None
    # Chain the groups from the end so every group after the first is
    # optional — the query may be any prefix of the transliteration.
    pattern = groups[-1]
    for group in reversed(groups[:-1]):
        pattern = group + _SHORT_VOWEL + "(?:" + pattern + ")?"
    return pattern


def _build_translit_regexes(catalog: list[dict[str, str]]) -> list[list[str]]:
    """Precompute a Finglish regex per Persian word of every catalog entry.

    Pure-ASCII words are skipped: the direct substring match already covers
    Latin symbols/names and avoids loose regex matches for them.
    """
    out: list[list[str]] = []
    for item in catalog:
        patterns: list[str] = []
        for text in (item.get("symbol", ""), item.get("name", "")):
            for word in text.split():
                if word.isascii():
                    continue  # pure ASCII → handled by direct match
                pattern = _word_regex(word)
                if pattern:
                    patterns.append(pattern)
        out.append(patterns)
    return out


# Built once at import time.
_CATALOG: list[dict[str, str]] = _build_catalog()

# Parallel list of Finglish regexes for each catalog entry.
_TRANSLIT_REGEXES: list[list[str]] = _build_translit_regexes(_CATALOG)


def all_symbols() -> list[dict[str, str]]:
    """Return the full static catalog (symbol/name/sector)."""
    return _CATALOG


# The market-type sectors the catalog is aggregated by. Any other sector
# value (e.g. granular industry sectors from ``selected_symbols.json`` such
# as ``محصولات شیمیایی``) is folded into ``سهام``.
MARKET_SECTORS: frozenset[str] = frozenset(
    {"سهام", "طلا و سکه", "ارز", "رمزارز", "کامودیتی", "بورس کالا", "صندوق"}
)


def sector_summary() -> list[dict[str, str | int]]:
    """Aggregate the catalog by market sector.

    Returns exactly one ``{sector, count}`` row per market type
    (سهام، طلا و سکه، ارز، رمزارز، کامودیتی، بورس کالا، صندوق) — ordered by
    count descending — with the number of symbols in each. Entries whose
    sector is empty or a granular industry value (from ``selected_symbols.json``)
    are grouped under ``سهام``.
    """
    counts: dict[str, int] = {}
    for item in _CATALOG:
        sector = item.get("sector") or ""
        if sector not in MARKET_SECTORS:
            sector = "سهام"
        counts[sector] = counts.get(sector, 0) + 1
    return [
        {"sector": sector, "count": count}
        for sector, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def search(query: str, limit: int = DEFAULT_LIMIT) -> list[dict[str, str]]:
    """Case-insensitive substring search over symbol and name.

    Persian names/symbols are also matched by their Finglish (Latin)
    transliteration — e.g. ``folad`` finds ``فولاد`` and ``zafaran`` finds
    ``زعفران``. Repeated-letter misspellings (``foolad``) are tolerated.

    Args:
        query: Search text (Persian or Latin characters).
        limit: Maximum number of results (default 25, clamped to 1..200).

    Returns:
        A list of ``{symbol, name, sector}`` dicts ordered by symbol.
    """
    q = (query or "").strip().lower()
    if not q:
        return []
    limit = max(1, min(int(limit), 200))

    # Finglish matching only makes sense for Latin queries; Persian input is
    # already covered by the direct substring checks above.
    q_collapsed = _collapse_repeats(q) if q.isascii() else ""

    matches: list[dict[str, str]] = []
    for idx, item in enumerate(_CATALOG):
        if (
            q in item["symbol"].lower()
            or q in item["name"].lower()
            or (
                q_collapsed
                # ``re.match`` anchors at the start of the query → the Latin
                # query must be a prefix of a transliteration (autocomplete
                # semantics). ``re.search`` would match a stray middle letter.
                and any(re.match(pattern, q_collapsed) for pattern in _TRANSLIT_REGEXES[idx])
            )
        ):
            matches.append(item)
            if len(matches) >= limit:
                break
    return matches


def finglish_symbol_candidates(query: str, limit: int = 50) -> list[str]:
    """Return Persian symbols whose Finglish spelling matches a Latin query.

    Used by DB-backed search endpoints (``instruments/search``,
    ``watchlist/search``) so a query like ``folad`` can also find the Persian
    symbol ``فولاد`` that lives in PostgreSQL. Only non-ASCII (Persian)
    symbols are returned — Latin symbols already match via ``ILIKE``.

    Returns an empty list for empty or Persian queries, so callers can keep
    their plain substring behaviour unchanged in that case.
    """
    q = (query or "").strip()
    if not q or not q.isascii():
        return []
    # Scan the whole catalog first, then filter — otherwise Latin symbols
    # filling the limit would silently drop valid Persian candidates.
    results = search(q, limit=200)
    persian = [item["symbol"] for item in results if not item["symbol"].isascii()]
    return persian[: max(1, min(int(limit), 200))]
