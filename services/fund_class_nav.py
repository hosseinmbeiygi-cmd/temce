"""🏷 Fund Class NAV — تخصیص NAV بین طبقات واحد (فاز ۴ معماری).

انواع تخصیص:
  - SIMPLE     : تقسیم نسبی بر اساس تعداد واحد هر طبقه.
  - LEVERAGED  : کف/سقف بازده روزشمار برای طبقه عادی؛ انتقال ریالی بین عادی/ممتاز.
  - GUARANTEED : تضمین اصل مبلغ طبقه عادی؛ مابه‌التفاوت از طبقه ممتاز.
  - FOF        : NAV از NAV زیرصندوق‌ها (اینجا فقط جمع و تقسیم؛ Look-through در تحلیل).

هیچ فرمول عمومی جایگزین سند صندوق نمی‌شود؛ پارامترها از پیکربندی نسخه‌دار می‌آیند.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from core.time import now_tehran
from services.fund_nav_engine import FundNavEngine
from services.fund_read_through import StaleResult

logger = get_logger(__name__)

CLASS_ENGINE_VERSION = "class-nav-1.0.0"
ALLOCATION_TYPES = ("SIMPLE", "LEVERAGED", "GUARANTEED", "FOF")


def percentile(values: list[float], p: float) -> float | None:
    """صدک با درون‌یابی خطی — برای کالیبراسیون آستانه."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * (p / 100.0)
    lower = int(k)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = k - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def allocate_simple(
    total_net_assets: float, units_by_class: dict[str, int]
) -> dict[str, dict[str, float]]:
    total_units = sum(units_by_class.values())
    if total_units <= 0:
        raise ValueError("تعداد واحد طبقات نامعتبر است")
    out: dict[str, dict[str, float]] = {}
    for code, units in units_by_class.items():
        share = units / total_units
        assets = total_net_assets * share
        out[code] = {
            "net_assets": assets,
            "units": float(units),
            "nav_per_unit": assets / units if units else 0.0,
            "transfer_amount": 0.0,
        }
    return out


def allocate_leveraged(
    total_net_assets: float,
    ordinary_units: int,
    preferred_units: int,
    floor_rate: float,
    ceiling_rate: float,
    days: int = 365,
    par_value: float = 1000.0,
) -> dict[str, Any]:
    """الگوریتم روزشمار کف/سقف صندوق اهرمی (انتقال ریالی بین دو طبقه)."""
    if ordinary_units <= 0 or preferred_units <= 0:
        raise ValueError("هر دو طبقه عادی و ممتاز باید واحد داشته باشند")
    if floor_rate > ceiling_rate:
        raise ValueError("کف بازده نمی‌تواند از سقف بیشتر باشد")
    base_ordinary = ordinary_units * par_value
    base_total = base_ordinary + preferred_units * par_value
    total_rate = (total_net_assets / base_total) - 1.0
    pro_rata_ordinary = base_ordinary * (1.0 + total_rate)
    floor_target = base_ordinary * (1.0 + floor_rate * days / 365.0)
    ceiling_target = base_ordinary * (1.0 + ceiling_rate * days / 365.0)

    warnings: list[str] = []
    if pro_rata_ordinary < floor_target:
        ordinary_assets = floor_target
    elif pro_rata_ordinary > ceiling_target:
        ordinary_assets = ceiling_target
    else:
        ordinary_assets = pro_rata_ordinary
    preferred_assets = total_net_assets - ordinary_assets
    if preferred_assets < 0:
        warnings.append("preferred_class_impaired")
        preferred_assets = 0.0
        ordinary_assets = total_net_assets
    transfer = ordinary_assets - pro_rata_ordinary

    return {
        "allocation_type": "LEVERAGED",
        "classes": {
            "ORDINARY": {
                "net_assets": ordinary_assets,
                "units": float(ordinary_units),
                "nav_per_unit": ordinary_assets / ordinary_units,
                "transfer_amount": transfer,
            },
            "PREFERRED": {
                "net_assets": preferred_assets,
                "units": float(preferred_units),
                "nav_per_unit": preferred_assets / preferred_units,
                "transfer_amount": -transfer,
            },
        },
        "total_rate": total_rate,
        "ordinary_rate": (ordinary_assets / base_ordinary) - 1.0,
        "preferred_rate": (
            (preferred_assets / (preferred_units * par_value)) - 1.0
            if preferred_units and par_value
            else None
        ),
        "warnings": warnings,
    }


def allocate_guaranteed(
    total_net_assets: float,
    ordinary_units: int,
    preferred_units: int,
    guarantee_par: float = 1000.0,
) -> dict[str, Any]:
    """تضمین اصل مبلغ طبقه عادی؛ مابه‌التفاوت از طبقه ممتاز تأمین می‌شود."""
    if ordinary_units <= 0:
        raise ValueError("طبقه عادی واحد ندارد")
    guaranteed_ordinary = ordinary_units * guarantee_par
    warnings: list[str] = []
    if total_net_assets <= guaranteed_ordinary:
        ordinary_assets = total_net_assets
        preferred_assets = 0.0
        warnings.append("guarantee_not_fully_covered")
    else:
        ordinary_assets = guaranteed_ordinary
        preferred_assets = total_net_assets - ordinary_assets
    return {
        "allocation_type": "GUARANTEED",
        "classes": {
            "ORDINARY": {
                "net_assets": ordinary_assets,
                "units": float(ordinary_units),
                "nav_per_unit": ordinary_assets / ordinary_units,
                "transfer_amount": 0.0,
            },
            "PREFERRED": {
                "net_assets": preferred_assets,
                "units": float(preferred_units),
                "nav_per_unit": (preferred_assets / preferred_units) if preferred_units else 0.0,
                "transfer_amount": 0.0,
            },
        },
        "warnings": warnings,
    }


@dataclass
class _ClassConfig:
    class_code: str
    class_type: str
    allocation_type: str
    units: int
    par_value: float
    floor_rate: float | None
    ceiling_rate: float | None
    guarantee_par: float | None
    version: str
    source_document_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class FundClassNavService:
    """محاسبه و ذخیره NAV طبقاتی بر پایه پیکربندی نسخه‌دار."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.engine = FundNavEngine(session)

    async def set_class_config(
        self,
        fund_id: str,
        classes: list[dict[str, Any]],
        version: str,
        source_document_id: str | None = None,
    ) -> list[dict[str, Any]]:
        saved: list[dict[str, Any]] = []
        for cls in classes:
            allocation_type = str(cls.get("allocation_type") or "SIMPLE").upper()
            if allocation_type not in ALLOCATION_TYPES:
                raise ValueError(f"allocation_type نامعتبر: {allocation_type}")
            row = (
                await self.session.execute(
                    text(
                        """
                        INSERT INTO fund_unit_classes
                            (fund_id, class_code, class_type, allocation_type,
                             units_outstanding, par_value, floor_rate, ceiling_rate,
                             guarantee_par, max_ratio, version, source_document_id)
                        VALUES
                            (:fid, :code, :ctype, :atype, :units, :par, :floor, :ceil,
                             :guar, :ratio, :ver, :src)
                        ON CONFLICT (fund_id, class_code, version) DO UPDATE SET
                            class_type = EXCLUDED.class_type,
                            allocation_type = EXCLUDED.allocation_type,
                            units_outstanding = EXCLUDED.units_outstanding,
                            par_value = EXCLUDED.par_value,
                            floor_rate = EXCLUDED.floor_rate,
                            ceiling_rate = EXCLUDED.ceiling_rate,
                            guarantee_par = EXCLUDED.guarantee_par,
                            max_ratio = EXCLUDED.max_ratio,
                            source_document_id = EXCLUDED.source_document_id
                        RETURNING id
                        """
                    ),
                    {
                        "fid": fund_id,
                        "code": str(cls.get("class_code") or "").upper(),
                        "ctype": str(cls.get("class_type") or "ORDINARY").upper(),
                        "atype": allocation_type,
                        "units": cls.get("units_outstanding"),
                        "par": cls.get("par_value", 1000),
                        "floor": cls.get("floor_rate"),
                        "ceil": cls.get("ceiling_rate"),
                        "guar": cls.get("guarantee_par"),
                        "ratio": cls.get("max_ratio"),
                        "ver": version,
                        "src": source_document_id,
                    },
                )
            ).first()
            saved.append({"class_code": cls.get("class_code"), "version": version, "id": row[0] if row else None})
        await self.session.commit()
        return saved

    async def get_class_config(self, fund_id: str) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT DISTINCT ON (class_code)
                        class_code, class_type, allocation_type, units_outstanding,
                        par_value, floor_rate, ceiling_rate, guarantee_par, max_ratio,
                        version, source_document_id
                    FROM fund_unit_classes
                    WHERE fund_id = :fid
                    ORDER BY class_code, effective_from DESC
                    """
                ),
                {"fid": fund_id},
            )
        ).fetchall()
        return [
            {
                "class_code": r[0],
                "class_type": r[1],
                "allocation_type": r[2],
                "units_outstanding": r[3],
                "par_value": r[4],
                "floor_rate": r[5],
                "ceiling_rate": r[6],
                "guarantee_par": r[7],
                "max_ratio": r[8],
                "version": r[9],
                "source_document_id": r[10],
            }
            for r in rows
        ]

    async def calculate(
        self, fund_id: str, valuation_date: date | None = None
    ) -> StaleResult:
        valuation_date = valuation_date or now_tehran().date()
        latest_run = await self.engine.get_latest(fund_id)
        if latest_run is None:
            await self.engine.calculate(fund_id)
            latest_run = await self.engine.get_latest(fund_id)
        net_assets = float((latest_run or {}).get("net_assets") or 0.0)
        if net_assets <= 0:
            raise ValueError("خالص دارایی معتبر برای تخصیص طبقاتی موجود نیست")

        configs = await self.get_class_config(fund_id)
        if not configs:
            raise ValueError("پیکربندی طبقات ثبت نشده است")

        units_by_class = {c["class_code"]: int(c["units_outstanding"] or 0) for c in configs}
        allocation_type = configs[0]["allocation_type"]
        details: dict[str, Any]
        if allocation_type == "LEVERAGED":
            ordinary = next((c for c in configs if c["class_code"] == "ORDINARY"), None)
            preferred = next((c for c in configs if c["class_code"] == "PREFERRED"), None)
            if ordinary is None or preferred is None:
                raise ValueError("صندوق اهرمی به دو طبقه ORDINARY و PREFERRED نیاز دارد")
            result = allocate_leveraged(
                net_assets,
                int(ordinary["units_outstanding"] or 0),
                int(preferred["units_outstanding"] or 0),
                float(ordinary.get("floor_rate") or 0.0),
                float(ordinary.get("ceiling_rate") or 0.0),
                par_value=float(ordinary.get("par_value") or 1000),
            )
            details = result
        elif allocation_type == "GUARANTEED":
            ordinary = next((c for c in configs if c["class_code"] == "ORDINARY"), None)
            preferred = next((c for c in configs if c["class_code"] == "PREFERRED"), None)
            result = allocate_guaranteed(
                net_assets,
                int((ordinary or {}).get("units_outstanding") or 0),
                int((preferred or {}).get("units_outstanding") or 0),
                guarantee_par=float((ordinary or {}).get("guarantee_par") or 1000),
            )
            details = result
        else:
            result = {
                "allocation_type": allocation_type,
                "classes": allocate_simple(net_assets, units_by_class),
                "warnings": [],
            }
            details = result

        # ذخیره idempotent برای همان روز
        await self.session.execute(
            text(
                """
                DELETE FROM fund_class_allocations
                WHERE fund_id = :fid AND valuation_date = :vd
                """
            ),
            {"fid": fund_id, "vd": valuation_date},
        )
        for code, alloc in result["classes"].items():
            await self.session.execute(
                text(
                    """
                    INSERT INTO fund_class_allocations
                        (fund_id, run_id, valuation_date, class_code, allocation_type,
                         net_assets, units, nav_per_unit, transfer_amount, quality, details_json)
                    VALUES
                        (:fid, :rid, :vd, :code, :atype, :na, :units, :navpu, :tr,
                         :quality, :details)
                    """
                ),
                {
                    "fid": fund_id,
                    "rid": (latest_run or {}).get("run_id"),
                    "vd": valuation_date,
                    "code": code,
                    "atype": result["allocation_type"],
                    "na": alloc["net_assets"],
                    "units": int(alloc["units"]),
                    "navpu": alloc["nav_per_unit"],
                    "tr": alloc.get("transfer_amount") or 0.0,
                    "quality": (latest_run or {}).get("quality_status") or "ESTIMATED",
                    "details": json.dumps(details, ensure_ascii=False, default=str),
                },
            )
        await self.session.commit()

        return StaleResult(
            data={
                "fund_id": fund_id,
                "valuation_date": str(valuation_date),
                "allocation_type": result["allocation_type"],
                "net_assets": net_assets,
                "classes": result["classes"],
                "warnings": result.get("warnings", []),
                "source_run_id": (latest_run or {}).get("run_id"),
                "engine_version": CLASS_ENGINE_VERSION,
            },
            freshness="estimated",
            fetched_from="db",
        )

    async def get_latest(self, fund_id: str) -> dict[str, Any] | None:
        rows = (
            await self.session.execute(
                text(
                    """
                    SELECT valuation_date, class_code, allocation_type, net_assets,
                           units, nav_per_unit, transfer_amount, quality, details_json
                    FROM fund_class_allocations
                    WHERE fund_id = :fid
                      AND valuation_date = (
                          SELECT MAX(valuation_date) FROM fund_class_allocations WHERE fund_id = :fid
                      )
                    ORDER BY class_code
                    """
                ),
                {"fid": fund_id},
            )
        ).fetchall()
        if not rows:
            return None
        classes = [
            {
                "class_code": r[1],
                "allocation_type": r[2],
                "net_assets": r[3],
                "units": r[4],
                "nav_per_unit": r[5],
                "transfer_amount": r[6],
                "quality": r[7],
            }
            for r in rows
        ]
        details = json.loads(rows[0][8]) if rows[0][8] else {}
        return {
            "fund_id": fund_id,
            "valuation_date": str(rows[0][0]),
            "allocation_type": rows[0][2],
            "classes": classes,
            "details": details,
        }


__all__ = [
    "ALLOCATION_TYPES",
    "CLASS_ENGINE_VERSION",
    "FundClassNavService",
    "allocate_guaranteed",
    "allocate_leveraged",
    "allocate_simple",
    "percentile",
]
