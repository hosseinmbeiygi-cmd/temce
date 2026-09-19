"""💰 Fund Tax — محاسبات مالیاتی صندوق (فاز ۹).

قواعد نسخه‌دار (مقادیر پیش‌فرض از قوانین جاری؛ قابل به‌روزرسانی از منبع رسمی):
  - TRANSFER_05      : مالیات مقطوع ۰.۵٪ نقل‌وانتقال سهام و حق تقدم.
  - CGT              : معافیت انتقال اوراق/کالا در بورس (تبصره ۷).
  - DEPOSIT_INTEREST : معافیت سود سپرده (تبصره ۱ ماده ۱۴۳ مکرر).
  - VAT              : معافیت ارزش افزوده درآمدهای صندوق.
  - FUND_INCOME      : معافیت کل درآمد صندوق.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger

logger = get_logger(__name__)

TAX_ENGINE_VERSION = "tax-1.0.0"
TRANSFER_TAX_RATE = 0.005

TAX_RULES: dict[str, dict[str, Any]] = {
    "TRANSFER_05": {"rate": TRANSFER_TAX_RATE, "exempt": False, "ref": "ARTICLE-143-MOKARRAR"},
    "CGT": {"rate": 0.0, "exempt": True, "ref": "CGT-TABASERE-7-EXCHANGE"},
    "DEPOSIT_INTEREST": {"rate": 0.0, "exempt": True, "ref": "ARTICLE-143-MOKARRAR-1"},
    "VAT": {"rate": 0.0, "exempt": True, "ref": "ARTICLE-143-MOKARRAR-1"},
    "FUND_INCOME": {"rate": 0.0, "exempt": True, "ref": "ARTICLE-143-MOKARRAR-1"},
}

TAX_TYPES = tuple(TAX_RULES)


def transfer_tax(sale_value: float, rate: float = TRANSFER_TAX_RATE) -> float:
    """مالیات مقطوع فروش سهام/حق تقدم = ارزش فروش × نرخ."""
    if sale_value < 0:
        raise ValueError("ارزش فروش نمی‌تواند منفی باشد")
    return float(sale_value) * float(rate)


def transfer_tax_from_trades(
    trades: list[dict[str, Any]], rate: float = TRANSFER_TAX_RATE
) -> dict[str, Any]:
    """محاسبه مالیات مقطوع از جریان معاملات (فقط سمت فروش).

    هر معامله: {side: BUY|SELL, value? | quantity, price}
    """
    sell_values: list[float] = []
    for trade in trades:
        if str(trade.get("side") or "").upper() != "SELL":
            continue
        value = trade.get("value")
        if value is None:
            value = float(trade.get("quantity") or 0) * float(trade.get("price") or 0)
        value = float(value or 0)
        if value < 0:
            raise ValueError("ارزش فروش نمی‌تواند منفی باشد")
        sell_values.append(value)
    base = sum(sell_values)
    return {
        "base_amount": base,
        "tax_amount": base * float(rate),
        "trade_count": len(sell_values),
        "rate": float(rate),
    }


def compute_tax(tax_type: str, base_amount: float) -> dict[str, Any]:
    """محاسبه مالیات بر اساس نوع و قاعده نسخه‌دار."""
    rule = TAX_RULES.get(tax_type)
    if rule is None:
        raise ValueError(f"نوع مالیات نامعتبر: {tax_type}")
    if base_amount < 0:
        raise ValueError("مبلغ پایه نمی‌تواند منفی باشد")
    rate = float(rule["rate"])
    exempt = bool(rule["exempt"])
    tax_amount = 0.0 if exempt else float(base_amount) * rate
    return {
        "tax_type": tax_type,
        "base_amount": float(base_amount),
        "rate": rate,
        "tax_amount": tax_amount,
        "exempt": exempt,
        "exemption_ref": rule["ref"],
    }


class FundTaxService:
    """محاسبه و ثبت مالیات صندوق (idempotent بر اساس دوره و نوع)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def calculate(
        self,
        fund_id: str,
        tax_type: str,
        base_amount: float,
        period_label: str,
    ) -> dict[str, Any]:
        result = compute_tax(tax_type, base_amount)
        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_tax_calculations
                        (fund_id, period_label, tax_type, base_amount, rate, tax_amount,
                         exempt, exemption_ref, details_json)
                    VALUES (:fid, :period, :tt, :base, :rate, :tax, :exempt, :ref, :details)
                    RETURNING id
                    """
                ),
                {
                    "fid": fund_id,
                    "period": period_label,
                    "tt": tax_type,
                    "base": result["base_amount"],
                    "rate": result["rate"],
                    "tax": result["tax_amount"],
                    "exempt": result["exempt"],
                    "ref": result["exemption_ref"],
                    "details": json.dumps({"engine": TAX_ENGINE_VERSION}, ensure_ascii=False),
                },
            )
        ).first()
        await self.session.commit()
        return {
            "tax_id": int(row[0]) if row else None,
            "fund_id": fund_id,
            "period_label": period_label,
            **result,
        }

    async def calculate_from_trades(
        self,
        fund_id: str,
        trades: list[dict[str, Any]],
        period_label: str,
    ) -> dict[str, Any]:
        """محاسبه مالیات مقطوع از جریان معاملات و ثبت آن."""
        result = transfer_tax_from_trades(trades)
        rule = TAX_RULES["TRANSFER_05"]
        row = (
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_tax_calculations
                        (fund_id, period_label, tax_type, base_amount, rate, tax_amount,
                         exempt, exemption_ref, details_json)
                    VALUES (:fid, :period, 'TRANSFER_05', :base, :rate, :tax,
                            FALSE, :ref, :details)
                    RETURNING id
                    """
                ),
                {
                    "fid": fund_id,
                    "period": period_label,
                    "base": result["base_amount"],
                    "rate": result["rate"],
                    "tax": result["tax_amount"],
                    "ref": rule["ref"],
                    "details": json.dumps(
                        {"engine": TAX_ENGINE_VERSION, "trade_count": result["trade_count"]},
                        ensure_ascii=False,
                    ),
                },
            )
        ).first()
        await self.session.commit()
        return {
            "tax_id": int(row[0]) if row else None,
            "fund_id": fund_id,
            "period_label": period_label,
            "tax_type": "TRANSFER_05",
            "exempt": False,
            **result,
        }

    async def summary(self, fund_id: str, limit: int = 100) -> dict[str, Any]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT id, period_label, tax_type, base_amount, rate, tax_amount,
                           exempt, exemption_ref, created_at
                    FROM fund_tax_calculations
                    WHERE fund_id = :fid
                    ORDER BY created_at DESC LIMIT :lim
                    """
                ),
                {"fid": fund_id, "lim": limit},
            )
        ).fetchall()
        items = [
            {
                "tax_id": int(r[0]),
                "period_label": r[1],
                "tax_type": r[2],
                "base_amount": r[3],
                "rate": r[4],
                "tax_amount": r[5],
                "exempt": r[6],
                "exemption_ref": r[7],
                "created_at": str(r[8]) if r[8] else None,
            }
            for r in rows
        ]
        return {
            "fund_id": fund_id,
            "items": items,
            "total_tax": sum(float(i["tax_amount"] or 0) for i in items),
        }

    async def list_rules(self) -> list[dict[str, Any]]:
        return [
            {"tax_type": k, **v, "engine_version": TAX_ENGINE_VERSION}
            for k, v in TAX_RULES.items()
        ]


__all__ = [
    "TAX_ENGINE_VERSION",
    "TAX_RULES",
    "TAX_TYPES",
    "TRANSFER_TAX_RATE",
    "FundTaxService",
    "compute_tax",
    "transfer_tax",
    "transfer_tax_from_trades",
]
