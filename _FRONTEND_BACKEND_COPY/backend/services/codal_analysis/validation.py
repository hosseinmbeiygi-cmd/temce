from __future__ import annotations

from dataclasses import dataclass, field

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationError:
    field: str
    message: str
    severity: str = "error"


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)


class BalanceSheetValidator:
    def validate(self, data: dict[str, float]) -> ValidationResult:
        result = ValidationResult(is_valid=True)
        total_assets = data.get("total_assets") or data.get("TOTAL_ASSETS") or 0
        total_liabilities = data.get("total_liabilities") or data.get("TOTAL_LIABILITIES") or 0
        total_equity = (
            data.get("total_equity") or data.get("TOTAL_EQUITY") or data.get("equity") or data.get("EQUITY") or 0
        )

        if total_assets and (total_liabilities or total_equity):
            if total_liabilities and total_equity:
                expected = total_liabilities + total_equity
                diff = abs(total_assets - expected)
                if diff > 0:
                    ratio = diff / max(total_assets, 1)
                    if ratio > 0.01:
                        result.errors.append(
                            ValidationError(
                                field="balance_sheet",
                                message=f"ترازنامه ناهمتراز: دارایی({total_assets:,.0f}) != بدهی({total_liabilities:,.0f}) + حقوق({total_equity:,.0f})، مغایرت={diff:,.0f}",
                                severity="error",
                            )
                        )
                        result.is_valid = False
                    elif ratio > 0.001:
                        result.warnings.append(
                            ValidationError(
                                field="balance_sheet",
                                message=f"ترازنامه با مغایرت جزئی: مغایرت={diff:,.0f}",
                                severity="warning",
                            )
                        )
        return result


class CashFlowValidator:
    def validate(self, data: dict[str, float]) -> ValidationResult:
        result = ValidationResult(is_valid=True)
        cfo = data.get("OPERATING_CASH_FLOW") or data.get("operating_cash_flow") or 0
        net_profit = data.get("NET_PROFIT") or data.get("net_profit") or 0

        if cfo and net_profit:
            if net_profit > 0 and cfo < 0:
                result.warnings.append(
                    ValidationError(
                        field="cash_flow",
                        message=f"سود خالص مثبت({net_profit:,.0f}) اما جریان نقد عملیاتی منفی({cfo:,.0f}) - کیفیت سود پایین",
                        severity="warning",
                    )
                )
        return result


class DataValidationPipeline:
    def __init__(self):
        self.validators = [
            BalanceSheetValidator(),
            CashFlowValidator(),
        ]

    def validate(self, data: dict[str, float]) -> ValidationResult:
        combined = ValidationResult(is_valid=True)
        for validator in self.validators:
            result = validator.validate(data)
            combined.errors.extend(result.errors)
            combined.warnings.extend(result.warnings)
            if not result.is_valid:
                combined.is_valid = False
        return combined

    def reconcile(self, data: dict[str, float]) -> dict[str, float]:
        result = self.validate(data)
        reconciled = dict(data)

        total_assets = reconciled.get("total_assets") or reconciled.get("TOTAL_ASSETS") or 0
        total_liabilities = reconciled.get("total_liabilities") or reconciled.get("TOTAL_LIABILITIES") or 0
        total_equity = (
            reconciled.get("total_equity")
            or reconciled.get("TOTAL_EQUITY")
            or reconciled.get("equity")
            or reconciled.get("EQUITY")
            or 0
        )

        if total_assets and total_liabilities and total_equity:
            expected = total_liabilities + total_equity
            diff = round(total_assets - expected, 2)
            if abs(diff) > 0:
                key = "RECONCILIATION_SUSPENSE"
                reconciled[key] = diff

        if result.errors and result.is_valid is False:
            logger.warning("Data validation failed with %d errors", len(result.errors))
        if result.warnings:
            logger.warning("Data validation produced %d warnings", len(result.warnings))

        reconciled["_validation"] = {
            "is_valid": result.is_valid,
            "error_count": len(result.errors),
            "warning_count": len(result.warnings),
        }
        return reconciled
