"""🧮 What kind of instrument a symbol is — decided only by stored facts.

The question bank is per-instrument now, so every sheet has to know whether it is judging a
share, a leveraged fund or a call option. Each rule below names the table (and usually the
column) it read; that string is stored on the sheet as ``instrument_basis`` and shown to the
user, so a wrong classification is auditable rather than silent.

Two things are deliberately **not** done here:

* **No name matching.** ``funds.fund_type`` types the gold ETFs (عیار، مثقال، طلا) as «بخشی»,
  so the only stored field separating a gold fund from an equity fund is the word «طلا» in
  its registered name. That is a guess about the instrument, so gold funds are only reported
  as such when ``brsapi_ime_funds`` — the IME commodity-board listing, which is data —
  contains the symbol. When it does not, the fund classifies as ``fund``/``etf`` and the user
  may override the sheet.
* **No empty tables.** ``gold_fund_nav`` and ``gold_snapshots`` exist and hold zero rows, so
  they evidence nothing and are not consulted.

A symbol no table recognises comes back ``unknown``, which is a refusal to open a sheet, not a
default to the stock bank.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from brsapi.models.ime import ImeCertificateModel, ImeFundModel, ImeFutureModel, ImeOptionModel
from core.logging import get_logger
from core.question_bank.registry import GAP_REASONS, MODULES
from core.question_bank.schema import INSTRUMENT_LABELS, INSTRUMENT_TYPES, InstrumentType
from models.fund import FundModel
from models.instrument import InstrumentModel
from models.market_data import (
    CommodityCertificateModel,
    CommodityFuturesModel,
    CommodityOptionModel,
    StockOptionModel,
    SymbolModel,
)

logger = get_logger(__name__)

#: ``funds.fund_type`` as it is actually stored. The domain was read from the database
#: (اهرمی / درآمد ثابت / سهامی / بخشی / مختلط); anything outside it is still a fund, but the
#: sub-class is unknown and the basis string says so instead of this module picking a side.
FUND_TYPE_MAP: dict[str, InstrumentType] = {
    "اهرمی": "leveraged_fund",
    "درآمد ثابت": "fixed_income",
    "سهامی": "fund",
    "مختلط": "fund",
    "بخشی": "fund",
    "اختصاصی": "fund",
}


class InstrumentUndetermined(ValueError):
    """No table recognises the symbol, so no question bank may be applied to it."""

    #: Every source :func:`classify` consults. Keep in step with its probes — this string is
    #: what tells the user where the platform looked before it refused.
    CHECKED = (
        "instruments", "symbols", "funds", "options", "commodity_options", "commodity_futures",
        "commodity_certificates", "brsapi_ime_options", "brsapi_ime_futures",
        "brsapi_ime_certificates", "brsapi_ime_funds",
    )

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        super().__init__(
            f"نوع ابزار «{symbol}» در هیچ‌یک از جداول برنامه "
            f"({', '.join(InstrumentUndetermined.CHECKED)}) یافت نشد. "
            "برای ساخت برگه، نوع ابزار را صریحاً انتخاب کنید."
        )


class UnknownInstrumentType(ValueError):
    """A caller asked for an instrument type this platform does not model."""

    def __init__(self, value: str) -> None:
        self.value = value
        super().__init__(
            f"«{value}» یک نوع ابزار شناخته‌شده نیست. مقادیر مجاز: {', '.join(INSTRUMENT_TYPES)}"
        )


def normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip()[:60]


def check_instrument_type(value: str | None) -> InstrumentType | None:
    """Validate a client-supplied type, or pass ``None`` through for auto-classification."""

    if value is None or value == "":
        return None
    if value not in INSTRUMENT_TYPES:
        raise UnknownInstrumentType(value)
    return value  # type: ignore[return-value]


def instrument_choices() -> list[dict[str, Any]]:
    """Every modelled type, with whether a bank exists for it yet.

    ``hasBank`` is the honest answer to «می‌توانم این را ارزیابی کنم؟»: a type can be
    recognised and still have no authored questions, and the UI must not offer it as a
    sheet — only as a declared gap, with ``missingBecause`` saying which data or which
    authoring step is absent.
    """

    return [
        {
            "key": key,
            "label": INSTRUMENT_LABELS[key],
            "hasBank": key in MODULES,
            "missingBecause": "" if key in MODULES else GAP_REASONS.get(key, ""),
        }
        for key in INSTRUMENT_TYPES
    ]


@dataclass(frozen=True)
class Classification:
    """The decided instrument class of one symbol, and how it was decided."""

    instrument_type: InstrumentType
    basis: str
    #: False when nothing recognised the symbol — the caller must refuse, not default.
    evidenced: bool = True

    @property
    def label(self) -> str:
        return INSTRUMENT_LABELS[self.instrument_type]

    @property
    def has_bank(self) -> bool:
        return self.instrument_type in MODULES

    def as_dict(self) -> dict[str, Any]:
        return {
            "instrument_type": self.instrument_type,
            "label": self.label,
            "basis": self.basis,
            "evidenced": self.evidenced,
            "hasBank": self.has_bank,
        }


async def _probe(session: AsyncSession, stmt: Select[Any], table: str) -> Any | None:
    """First column of the first matching row, or None.

    Each read runs in a SAVEPOINT on purpose: one failed statement aborts PostgreSQL's whole
    transaction, which would then break the sheet insert that follows. A table that cannot
    be read degrades to "no match" and is recorded in the basis as a checked-but-failed
    source rather than poisoning the request.
    """

    try:
        async with session.begin_nested():
            row = (await session.execute(stmt.limit(1))).first()
        return None if row is None else row[0]
    except Exception:  # pragma: no cover — only reachable with a missing/renamed table
        logger.debug("pre-buy instrument probe failed on %s", table, exc_info=True)
        return None


async def classify(session: AsyncSession, symbol: str) -> Classification:
    """Resolve one symbol to an instrument class.

    Order is by how wrong a mistake would be: derivative codes first (a contract judged with
    share questions is the most dangerous error and its symbols never appear in the equity
    tables), then a fund's own registered ``fund_type``, then the boards it is listed on,
    then plain equity.
    """

    name = normalize_symbol(symbol)
    if not name:
        return Classification("unknown", "نماد خالی داده شد.", evidenced=False)
    key = name.lower()

    # ── derivatives ────────────────────────────────────────────────────────────────────
    hit = await _probe(
        session,
        select(StockOptionModel.underlying_symbol).where(func.lower(StockOptionModel.symbol) == key),
        "options",
    )
    if hit is not None:
        return Classification("option", f"اختیار معاملهٔ سهام در `options` (پایه: {hit or '—'})")

    hit = await _probe(
        session,
        select(CommodityOptionModel.underlying).where(func.lower(CommodityOptionModel.symbol) == key),
        "commodity_options",
    )
    if hit is not None:
        return Classification("option", f"اختیار معاملهٔ کالایی در `commodity_options` (پایه: {hit or '—'})")

    hit = await _probe(
        session,
        select(ImeOptionModel.contract_category_commodity).where(
            or_(
                func.lower(ImeOptionModel.call_contract_code) == key,
                func.lower(ImeOptionModel.put_contract_code) == key,
            )
        ),
        "brsapi_ime_options",
    )
    if hit is not None:
        return Classification("option", f"اختیار معاملهٔ کالایی در `brsapi_ime_options` (پایه: {hit or '—'})")

    hit = await _probe(
        session,
        select(CommodityFuturesModel.name).where(func.lower(CommodityFuturesModel.symbol) == key),
        "commodity_futures",
    )
    if hit is not None:
        return Classification("future", f"قرارداد آتی در `commodity_futures` ({hit})")

    hit = await _probe(
        session,
        select(ImeFutureModel.contract_description).where(func.lower(ImeFutureModel.contract_code) == key),
        "brsapi_ime_futures",
    )
    if hit is not None:
        return Classification("future", f"قرارداد آتی در `brsapi_ime_futures` ({hit})")

    hit = await _probe(
        session,
        select(CommodityCertificateModel.name).where(func.lower(CommodityCertificateModel.symbol) == key),
        "commodity_certificates",
    )
    if hit is not None:
        return Classification("commodity_certificate", f"گواهی سپردهٔ کالایی در `commodity_certificates` ({hit})")

    hit = await _probe(
        session,
        select(ImeCertificateModel.commodity).where(func.lower(ImeCertificateModel.contract_code) == key),
        "brsapi_ime_certificates",
    )
    if hit is not None:
        return Classification("commodity_certificate", f"گواهی سپردهٔ کالایی در `brsapi_ime_certificates` ({hit})")

    # ── funds, by the type they are registered with ────────────────────────────────────
    fund_type = await _probe(
        session, select(FundModel.fund_type).where(func.lower(FundModel.symbol) == key), "funds"
    )
    ime_fund = await _probe(
        session, select(ImeFundModel.name).where(func.lower(ImeFundModel.symbol) == key), "brsapi_ime_funds"
    )
    if fund_type is not None or ime_fund is not None:
        mapped = FUND_TYPE_MAP.get(str(fund_type or ""))
        if ime_fund is not None and mapped in (None, "fund"):
            return Classification(
                "commodity_fund", f"صندوق کالایی/طلا در `brsapi_ime_funds` ({ime_fund})"
            )
        if mapped is not None and mapped != "fund":
            clash = f"؛ در `brsapi_ime_funds` هم فهرست شده ({ime_fund})" if ime_fund else ""
            return Classification(mapped, f"`funds.fund_type` = «{fund_type}»{clash}")
        return Classification("fund", f"صندوق در `funds` با نوع ثبت‌شده «{fund_type}»")

    # ── exchange listings ──────────────────────────────────────────────────────────────
    hit = await _probe(
        session,
        select(SymbolModel.name).where(
            func.lower(SymbolModel.symbol) == key, func.lower(func.coalesce(SymbolModel.market_type, "")) == "etf"
        ),
        "symbols",
    )
    if hit is not None:
        return Classification("etf", f"`symbols.market_type` = 'ETF' ({hit})")

    hit = await _probe(
        session,
        select(InstrumentModel.name).where(
            func.lower(InstrumentModel.symbol) == key,
            func.lower(func.coalesce(InstrumentModel.asset_class, "")) == "equity",
        ),
        "instruments",
    )
    if hit is not None:
        return Classification("equity", f"`instruments`: سهام ({hit})")

    hit = await _probe(
        session,
        select(SymbolModel.name).where(
            func.lower(SymbolModel.symbol) == key,
            func.lower(func.coalesce(SymbolModel.asset_class, "")) == "equity",
        ),
        "symbols",
    )
    if hit is not None:
        return Classification("equity", f"`symbols`: سهام ({hit})")

    return Classification("unknown", "هیچ جدولی این نماد را نمی‌شناسد.", evidenced=False)


__all__ = [
    "FUND_TYPE_MAP",
    "Classification",
    "InstrumentUndetermined",
    "UnknownInstrumentType",
    "check_instrument_type",
    "classify",
    "instrument_choices",
    "normalize_symbol",
]
