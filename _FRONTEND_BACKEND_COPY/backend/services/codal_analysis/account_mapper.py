from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

CANONICAL_ACCOUNTS: dict[str, dict[str, Any]] = {
    "REVENUE": {"code": "REVENUE", "name": "فروش خالص", "category": "income", "statement": "pl"},
    "COST_OF_GOODS_SOLD": {
        "code": "COGS",
        "name": "بهای تمام شده کالای فروش رفته",
        "category": "expense",
        "statement": "pl",
    },
    "GROSS_PROFIT": {"code": "GROSS_PROFIT", "name": "سود ناخالص", "category": "income", "statement": "pl"},
    "OPERATING_EXPENSES": {"code": "OPEX", "name": "هزینه‌های عملیاتی", "category": "expense", "statement": "pl"},
    "OPERATING_PROFIT": {"code": "OP_PROFIT", "name": "سود عملیاتی", "category": "income", "statement": "pl"},
    "FINANCIAL_COST": {"code": "FIN_COST", "name": "هزینه مالی", "category": "expense", "statement": "pl"},
    "FINANCIAL_INCOME": {"code": "FIN_INCOME", "name": "درآمد مالی", "category": "income", "statement": "pl"},
    "NET_PROFIT": {"code": "NET_PROFIT", "name": "سود خالص", "category": "income", "statement": "pl"},
    "EPS": {"code": "EPS", "name": "سود هر سهم", "category": "per_share", "statement": "pl"},
    "CURRENT_ASSETS": {"code": "CUR_ASSETS", "name": "دارایی‌های جاری", "category": "asset", "statement": "bs"},
    "NON_CURRENT_ASSETS": {"code": "NCUR_ASSETS", "name": "دارایی‌های غیرجاری", "category": "asset", "statement": "bs"},
    "TOTAL_ASSETS": {"code": "TOT_ASSETS", "name": "جمع دارایی‌ها", "category": "asset", "statement": "bs"},
    "CURRENT_LIABILITIES": {"code": "CUR_LIAB", "name": "بدهی‌های جاری", "category": "liability", "statement": "bs"},
    "NON_CURRENT_LIABILITIES": {
        "code": "NCUR_LIAB",
        "name": "بدهی‌های غیرجاری",
        "category": "liability",
        "statement": "bs",
    },
    "TOTAL_LIABILITIES": {"code": "TOT_LIAB", "name": "جمع بدهی‌ها", "category": "liability", "statement": "bs"},
    "EQUITY": {"code": "EQUITY", "name": "حقوق صاحبان سهام", "category": "equity", "statement": "bs"},
    "INVENTORY": {"code": "INVENTORY", "name": "موجودی کالا", "category": "asset", "statement": "bs"},
    "CASH": {"code": "CASH", "name": "وجه نقد", "category": "asset", "statement": "bs"},
    "ACCOUNTS_RECEIVABLE": {"code": "AR", "name": "حساب‌های دریافتنی", "category": "asset", "statement": "bs"},
    "ACCOUNTS_PAYABLE": {"code": "AP", "name": "حساب‌های پرداختنی", "category": "liability", "statement": "bs"},
    "OPERATING_CASH_FLOW": {"code": "CFO", "name": "جریان نقد عملیاتی", "category": "cash_flow", "statement": "cf"},
    "INVESTING_CASH_FLOW": {"code": "CFI", "name": "جریان نقد سرمایه‌گذاری", "category": "cash_flow", "statement": "cf"},
    "FINANCING_CASH_FLOW": {"code": "CFF", "name": "جریان نقد تأمین مالی", "category": "cash_flow", "statement": "cf"},
    "CAPITAL": {"code": "CAPITAL", "name": "سرمایه ثبت شده", "category": "equity", "statement": "bs"},
    "RETAINED_EARNINGS": {"code": "RETAINED", "name": "سود انباشته", "category": "equity", "statement": "bs"},
    "DEPRECIATION": {"code": "DEPR", "name": "استهلاک", "category": "expense", "statement": "pl"},
    "NET_FIXED_ASSETS": {"code": "FIXED_ASSETS", "name": "دارایی‌های ثابت خالص", "category": "asset", "statement": "bs"},
    "TOTAL_EQUITY": {"code": "TOT_EQUITY", "name": "جمع حقوق صاحبان سهام", "category": "equity", "statement": "bs"},
    "TOTAL_CURRENT_ASSETS": {
        "code": "TOT_CUR_ASSETS",
        "name": "جمع دارایی‌های جاری",
        "category": "asset",
        "statement": "bs",
    },
    "TOTAL_CURRENT_LIABILITIES": {
        "code": "TOT_CUR_LIAB",
        "name": "جمع بدهی‌های جاری",
        "category": "liability",
        "statement": "bs",
    },
}


RULE_BASED_MAPPINGS: dict[str, str] = {
    "فروش": "REVENUE",
    "درآمد": "REVENUE",
    "فروش خالص": "REVENUE",
    "درآمد عملیاتی": "REVENUE",
    "بهای تمام": "COST_OF_GOODS_SOLD",
    "بهای تمام شده": "COST_OF_GOODS_SOLD",
    "هزینه فروش": "COST_OF_GOODS_SOLD",
    "قیمت تمام شده": "COST_OF_GOODS_SOLD",
    "سود ناخالص": "GROSS_PROFIT",
    "ناخالص فروش": "GROSS_PROFIT",
    "سود ناویژه": "GROSS_PROFIT",
    "هزینه عمومی": "OPERATING_EXPENSES",
    "هزینه اداری": "OPERATING_EXPENSES",
    "هزینه پرسنل": "OPERATING_EXPENSES",
    "هزینه حقوق": "OPERATING_EXPENSES",
    "هزینه های عملیاتی": "OPERATING_EXPENSES",
    "سود عملیاتی": "OPERATING_PROFIT",
    "زیان عملیاتی": "OPERATING_PROFIT",
    "سود (زیان) عملیاتی": "OPERATING_PROFIT",
    "هزینه مالی": "FINANCIAL_COST",
    "هزینه بهره": "FINANCIAL_COST",
    "درآمد مالی": "FINANCIAL_INCOME",
    "سود سپرده": "FINANCIAL_INCOME",
    "سود خالص": "NET_PROFIT",
    "سود ویژه": "NET_PROFIT",
    "زیان خالص": "NET_PROFIT",
    "سود (زیان) خالص": "NET_PROFIT",
    "خالص سود": "NET_PROFIT",
    "سود (زیان) ویژه": "NET_PROFIT",
    "EPS": "EPS",
    "سود هر سهم": "EPS",
    "سود پایه": "EPS",
    "دارایی جاری": "CURRENT_ASSETS",
    "دارایی‌های جاری": "CURRENT_ASSETS",
    "جمع دارایی جاری": "TOTAL_CURRENT_ASSETS",
    "جمع دارایی‌های جاری": "TOTAL_CURRENT_ASSETS",
    "کل دارایی‌های جاری": "TOTAL_CURRENT_ASSETS",
    "دارایی غیرجاری": "NON_CURRENT_ASSETS",
    "دارایی غیر جاری": "NON_CURRENT_ASSETS",
    "دارایی ثابت": "NET_FIXED_ASSETS",
    "اموال و ماشین": "NET_FIXED_ASSETS",
    "اموال، ماشین": "NET_FIXED_ASSETS",
    "جمع دارایی": "TOTAL_ASSETS",
    "جمع دارایی‌ها": "TOTAL_ASSETS",
    "کل دارایی": "TOTAL_ASSETS",
    "کل دارایی‌ها": "TOTAL_ASSETS",
    "بدهی جاری": "CURRENT_LIABILITIES",
    "بدهی‌های جاری": "CURRENT_LIABILITIES",
    "جمع بدهی جاری": "TOTAL_CURRENT_LIABILITIES",
    "جمع بدهی‌های جاری": "TOTAL_CURRENT_LIABILITIES",
    "کل بدهی‌های جاری": "TOTAL_CURRENT_LIABILITIES",
    "بدهی غیرجاری": "NON_CURRENT_LIABILITIES",
    "بدهی غیر جاری": "NON_CURRENT_LIABILITIES",
    "بدهی بلندمدت": "NON_CURRENT_LIABILITIES",
    "تسهیلات بلندمدت": "NON_CURRENT_LIABILITIES",
    "جمع بدهی": "TOTAL_LIABILITIES",
    "کل بدهی": "TOTAL_LIABILITIES",
    "حقوق صاحبان سهام": "EQUITY",
    "حقوق مالکانه": "EQUITY",
    "جمع حقوق": "TOTAL_EQUITY",
    "کل حقوق صاحبان سهام": "TOTAL_EQUITY",
    "جمع حقوق صاحبان": "TOTAL_EQUITY",
    "سرمایه ثبت": "CAPITAL",
    "سرمایه اسمی": "CAPITAL",
    "سود انباشته": "RETAINED_EARNINGS",
    "سود (زیان) انباشته": "RETAINED_EARNINGS",
    "موجودی کالا": "INVENTORY",
    "موجودی مواد": "INVENTORY",
    "موجودی انبار": "INVENTORY",
    "وجه نقد": "CASH",
    "موجودی نقد": "CASH",
    "نقد و بانک": "CASH",
    "وجوه نقد": "CASH",
    "حساب های دریافتنی": "ACCOUNTS_RECEIVABLE",
    "حساب دریافتنی": "ACCOUNTS_RECEIVABLE",
    "اسناد دریافتنی": "ACCOUNTS_RECEIVABLE",
    "حساب های پرداختنی": "ACCOUNTS_PAYABLE",
    "حساب پرداختنی": "ACCOUNTS_PAYABLE",
    "اسناد پرداختنی": "ACCOUNTS_PAYABLE",
    "وجه نقد حاصل از عملیات": "OPERATING_CASH_FLOW",
    "خالص وجه نقد عملیات": "OPERATING_CASH_FLOW",
    "خالص جریان نقد عملیاتی": "OPERATING_CASH_FLOW",
    "وجه نقد حاصل از سرمایه": "INVESTING_CASH_FLOW",
    "خالص وجه نقد سرمایه": "INVESTING_CASH_FLOW",
    "خالص جریان نقد سرمایه": "INVESTING_CASH_FLOW",
    "وجه نقد حاصل از تأمین": "FINANCING_CASH_FLOW",
    "خالص وجه نقد تأمین": "FINANCING_CASH_FLOW",
    "خالص جریان نقد تأمین": "FINANCING_CASH_FLOW",
    "استهلاک": "DEPRECIATION",
    "هزینه استهلاک": "DEPRECIATION",
    "استهلاک انباشته": "DEPRECIATION",
}


@dataclass
class MappingResult:
    canonical_code: str | None
    canonical_name: str | None
    confidence: float
    method: str
    source_label: str


class AccountMapper:
    def __init__(self, confidence_threshold: float = 0.85):
        self.confidence_threshold = confidence_threshold
        self._compiled_rules: list[tuple[re.Pattern, str]] = [
            (re.compile(re.escape(kw), re.IGNORECASE), code) for kw, code in RULE_BASED_MAPPINGS.items()
        ]

    def map(self, label: str, industry: str | None = None) -> MappingResult:
        label_clean = label.strip().replace("\u200c", "")

        exact_match = RULE_BASED_MAPPINGS.get(label_clean)
        if exact_match:
            acct = CANONICAL_ACCOUNTS.get(exact_match)
            return MappingResult(
                canonical_code=exact_match,
                canonical_name=acct["name"] if acct else None,
                confidence=1.0,
                method="exact_rule",
                source_label=label,
            )

        for pattern, code in self._compiled_rules:
            if pattern.search(label_clean):
                acct = CANONICAL_ACCOUNTS.get(code)
                return MappingResult(
                    canonical_code=code,
                    canonical_name=acct["name"] if acct else None,
                    confidence=0.95,
                    method="fuzzy_rule",
                    source_label=label,
                )

        if "سود" in label_clean and "ناخالص" in label_clean:
            return self._result("GROSS_PROFIT", 0.85, "heuristic", label)
        if "سود" in label_clean and ("عملیات" in label_clean or "عملیاتی" in label_clean):
            return self._result("OPERATING_PROFIT", 0.85, "heuristic", label)
        if "سود" in label_clean and ("خالص" in label_clean or "ویژه" in label_clean):
            return self._result("NET_PROFIT", 0.85, "heuristic", label)
        if "دارایی" in label_clean and ("جمع" in label_clean or "کل" in label_clean):
            return self._result("TOTAL_ASSETS", 0.8, "heuristic", label)
        if "بدهی" in label_clean and ("جمع" in label_clean or "کل" in label_clean):
            return self._result("TOTAL_LIABILITIES", 0.8, "heuristic", label)
        if "حقوق" in label_clean:
            return self._result("EQUITY", 0.75, "heuristic", label)
        if "جریان نقد" in label_clean or "وجه نقد" in label_clean:
            return self._result("OPERATING_CASH_FLOW", 0.7, "heuristic", label)

        return MappingResult(
            canonical_code=None,
            canonical_name=None,
            confidence=0.0,
            method="unmapped",
            source_label=label,
        )

    def _result(self, code: str, confidence: float, method: str, label: str) -> MappingResult:
        acct = CANONICAL_ACCOUNTS.get(code)
        return MappingResult(
            canonical_code=code,
            canonical_name=acct["name"] if acct else None,
            confidence=confidence,
            method=method,
            source_label=label,
        )

    def batch_map(self, labels: list[str], industry: str | None = None) -> list[MappingResult]:
        return [self.map(lbl, industry) for lbl in labels]

    def get_unmapped(self, labels: list[str], industry: str | None = None) -> list[str]:
        return [
            lbl
            for lbl, res in zip(labels, self.batch_map(labels, industry), strict=False)
            if res.canonical_code is None
        ]
