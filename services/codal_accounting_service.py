from __future__ import annotations

import os
import re
from typing import Any

from bs4 import BeautifulSoup

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)

CODAL_EXCEL_DIR = get_settings().codal_excel_dir

REPORT_TYPE_LABELS: dict[str, str] = {
    "ن-۱۰": "گزارش عملکرد ماهانه",
    "ن-۳۰": "صورت مالی میاندوره‌ای (۳ ماهه)",
    "ن-۳۱": "صورت مالی سالانه",
}


def _parse_filename(filename: str) -> dict[str, Any] | None:
    """Parse a Codal Excel filename into structured metadata."""
    name = filename.replace(".xlsx", "")
    parts = name.split("_")
    if len(parts) < 2:
        return None
    symbol = parts[0]
    report_type = parts[1] if len(parts) > 1 else ""
    date_str = parts[2] if len(parts) > 2 else ""
    return {
        "symbol": symbol,
        "report_type": report_type,
        "report_type_label": REPORT_TYPE_LABELS.get(report_type, report_type),
        "date": date_str,
        "filename": filename,
        "filepath": "",
    }


def _normalize_number(text: str) -> float:
    """Convert Persian number string to float. Handles commas, Persian digits, Arabic digits."""
    if not text:
        return 0.0
    text = text.strip()
    # Remove commas
    text = text.replace(",", "")
    # Handle Persian/Arabic digits
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    ascii_digits = "0123456789"
    trans_table = str.maketrans(persian_digits + arabic_digits, ascii_digits * 2)
    text = text.translate(trans_table)
    # Remove non-numeric except minus
    text = re.sub(r"[^\d\-]", "", text)
    try:
        return float(text) if text else 0.0
    except ValueError:
        return 0.0


def list_available_symbols() -> list[dict[str, Any]]:
    """List all symbols that have codal excel files."""
    if not os.path.isdir(CODAL_EXCEL_DIR):
        logger.warning("Codal excel directory not found: %s", CODAL_EXCEL_DIR)
        return []

    results: list[dict[str, Any]] = []
    for entry in os.listdir(CODAL_EXCEL_DIR):
        dir_path = os.path.join(CODAL_EXCEL_DIR, entry)
        if not os.path.isdir(dir_path):
            continue
        files = [f for f in os.listdir(dir_path) if f.endswith(".xlsx")]
        if not files:
            continue
        # Count by report type
        type_counts: dict[str, int] = {}
        latest: dict[str, str] = {}
        for f in files:
            parsed = _parse_filename(f)
            if parsed:
                rt = parsed["report_type"] or "سایر"
                type_counts[rt] = type_counts.get(rt, 0) + 1
                # Track latest per type
                if rt not in latest or parsed["date"] > latest[rt]:
                    latest[rt] = f
            else:
                type_counts["سایر"] = type_counts.get("سایر", 0) + 1
        results.append({
            "symbol": files[0].split("_")[0] if "_" in files[0] else entry,
            "dir_name": entry,
            "total_files": len(files),
            "report_types": type_counts,
            "latest_file": max(files),
        })

    results.sort(key=lambda x: x["total_files"], reverse=True)
    return results


def list_reports(symbol: str, report_type: str | None = None) -> list[dict[str, Any]]:
    """List available reports for a symbol, sorted newest first."""
    if not os.path.isdir(CODAL_EXCEL_DIR):
        return []

    # Find the matching directory
    target_dir = None
    for entry in os.listdir(CODAL_EXCEL_DIR):
        if not os.path.isdir(os.path.join(CODAL_EXCEL_DIR, entry)):
            continue
        dir_name = entry
        # Try exact match or prefix match
        if dir_name == symbol or dir_name.startswith(symbol) or symbol.startswith(dir_name):
            target_dir = dir_name
            break

    if not target_dir:
        return []

    dir_path = os.path.join(CODAL_EXCEL_DIR, target_dir)
    files = [f for f in os.listdir(dir_path) if f.endswith(".xlsx")]
    reports: list[dict[str, Any]] = []
    for f in files:
        parsed = _parse_filename(f)
        if parsed:
            parsed["filepath"] = os.path.join(dir_path, f)
            if report_type and parsed["report_type"] != report_type:
                continue
            reports.append(parsed)

    reports.sort(key=lambda x: x["date"], reverse=True)
    return reports


def parse_report(filepath: str) -> dict[str, Any]:
    """Parse a Codal HTML Excel file and extract financial tables."""
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(filepath, encoding="cp1256") as f:
                content = f.read()
        except Exception:
            logger.exception("Failed to read file: %s", filepath)
            return {"error": "Failed to read file"}

    soup = BeautifulSoup(content, "html.parser")
    rows = soup.find_all("tr")

    # Extract title from first td with class or from <title> tag
    title_tag = soup.find("title")
    parsed_title = title_tag.get_text(strip=True) if title_tag else ""

    tables_data: list[list[list[str]]] = []
    current_table: list[list[str]] = []
    for row in rows:
        cells = row.find_all(["td", "th"])
        row_data = [cell.get_text(strip=True) for cell in cells]
        # Skip empty rows
        if not any(c for c in row_data if c.strip()):
            if current_table:
                tables_data.append(current_table)
                current_table = []
            continue
        current_table.append(row_data)
    if current_table:
        tables_data.append(current_table)

    # Build structured result
    result: dict[str, Any] = {
        "title": parsed_title,
        "tables": [],
        "raw_rows_count": len(rows),
        "table_count": len(tables_data),
    }

    for table_idx, table_rows in enumerate(tables_data):
        if not table_rows:
            continue
        headers = table_rows[0] if table_rows else []
        data_rows = table_rows[1:] if len(table_rows) > 1 else []

        # Detect if first column contains financial statement items
        items: list[dict[str, Any]] = []
        summary: dict[str, float] = {}
        for row in data_rows:
            if not row or not row[0]:
                continue
            label = row[0]
            values: dict[str, float] = {}
            for col_idx in range(1, len(row)):
                val = _normalize_number(row[col_idx])
                col_name = headers[col_idx] if col_idx < len(headers) else f"col_{col_idx}"
                values[col_name] = val
                # Update summary with the last numeric column
                if val != 0:
                    summary[label] = val
            items.append({"label": label, "values": values})

        result["tables"].append({
            "table_index": table_idx,
            "headers": headers,
            "row_count": len(data_rows),
            "items": items,
        })

    return result


# ── Persian Financial Keyword Classification ───────────────────────

FINANCIAL_KEYWORDS: dict[str, list[str]] = {
    "revenue": [
        "فروش", "درآمد", "درامد",
        "فروش خالص", "درآمد عملیاتی",
        "جمع درآمد", "جمع فروش",
    ],
    "cost_of_goods_sold": [
        "بهای تمام", "هزینه فروش", "بهای تمام‌شده",
        "بهای تمام شده", "قیمت تمام شده",
        "هزینه مستقیم", "هزینه تولید",
    ],
    "gross_profit": [
        "سود ناخالص", "ناخالص فروش", "سود ناویژه",
    ],
    "operating_expenses": [
        "هزینه عمومی", "هزینه اداری", "هزینه فروش",
        "هزینه سربار", "هزینه پرسنل", "هزینه حقوق",
        "هزینه تشکیلاتی", "هزینه توزیع",
        "جمع هزینه های", "هزینه های عملیاتی",
    ],
    "operating_profit": [
        "سود عملیاتی", "زیان عملیاتی",
        "سود (زیان) عملیاتی",
    ],
    "financial_cost": [
        "هزینه مالی", "هزینه بهره", "کارمزد",
        "هزینه تأمین مالی",
    ],
    "financial_income": [
        "درآمد مالی", "درامد مالی",
        "سود سپرده", "سود بانکی",
    ],
    "net_profit": [
        "سود خالص", "سود ویژه", "زیان خالص",
        "سود (زیان) خالص", "خالص سود",
        "سود (زیان) ویژه",
    ],
    "eps": [
        "eps", "EPS", "سود هر سهم", "سود پایه",
        "سود (زیان) به ازای هر سهم",
    ],
    "current_assets": [
        "دارایی جاری", "دارایی‌های جاری",
    ],
    "total_current_assets": [
        "جمع دارایی جاری", "جمع دارایی‌های جاری",
        "کل دارایی‌های جاری",
    ],
    "non_current_assets": [
        "دارایی غیرجاری", "دارایی غیر جاری", "دارایی ثابت",
        "دارایی بلندمدت", "دارایی‌های غیرجاری",
        "اموال و ماشین", "اموال، ماشین",
        "سرمایه‌گذاری بلندمدت",
    ],
    "total_assets": [
        "جمع دارایی", "جمع دارایی‌ها",
        "کل دارایی", "کل دارایی‌ها",
    ],
    "current_liabilities": [
        "بدهی جاری", "بدهی‌های جاری",
    ],
    "total_current_liabilities": [
        "جمع بدهی جاری", "جمع بدهی‌های جاری",
        "کل بدهی‌های جاری",
    ],
    "non_current_liabilities": [
        "بدهی غیرجاری", "بدهی غیر جاری", "بدهی بلندمدت",
        "بدهی‌های غیرجاری", "بدهی بلند مدت",
        "تسهیلات بلندمدت", "تسهیلات مالی بلندمدت",
    ],
    "total_liabilities": [
        "جمع بدهی", "جمع بدهی‌ها", "جمع بدهی‌های",
        "کل بدهی", "کل بدهی‌ها",
    ],
    "equity": [
        "حقوق صاحبان سهام", "حقوق مالکانه",
        "سرمایه", "جمع حقوق",
        "خالص سرمایه",
    ],
    "total_equity": [
        "جمع حقوق صاحبان", "جمع حقوق مالکانه",
        "کل حقوق صاحبان سهام",
        "جمع حقوق و اندوخته",
    ],
    "inventory": [
        "موجودی کالا", "موجودی مواد",
        "موجودی نهایی", "موجودی انبار",
    ],
    "cash": [
        "وجه نقد", "موجودی نقد",
        "نقد و بانک", "وجوه نقد",
    ],
    "operating_cash_flow": [
        "وجه نقد حاصل از عملیات", "خالص وجه نقد عملیات",
        "خالص جریان نقد عملیاتی",
    ],
    "investing_cash_flow": [
        "وجه نقد حاصل از سرمایه", "خالص وجه نقد سرمایه",
        "خالص جریان نقد سرمایه‌گذاری",
    ],
    "financing_cash_flow": [
        "وجه نقد حاصل از تأمین", "خالص وجه نقد تأمین",
        "خالص جریان نقد تأمین مالی",
    ],
    "capital": [
        "سرمایه ثبت", "سرمایه اسمی",
        "سرمایه ثبت شده", "سرمایه مجاز",
    ],
    "retained_earnings": [
        "سود انباشته", "سود (زیان) انباشته",
    ],
    "accounts_receivable": [
        "حساب‌های دریافتنی", "حساب دریافتنی",
        "اسناد دریافتنی",
    ],
    "accounts_payable": [
        "حساب‌های پرداختنی", "حساب پرداختنی",
        "اسناد پرداختنی",
    ],
    "depreciation": [
        "استهلاک", "هزینه استهلاک",
        "استهلاک انباشته",
    ],
}

RATIO_DEFINITIONS: dict[str, dict[str, Any]] = {
    "current_ratio": {
        "label": "نسبت جاری",
        "formula": "دارایی‌های جاری / بدهی‌های جاری",
        "description": "نشان‌دهنده توانایی شرکت در پرداخت بدهی‌های کوتاه‌مدت",
        "good_range": "۱.۵ - ۳",
        "inputs": ["total_current_assets", "total_current_liabilities"],
        "fallback_inputs": ["current_assets", "current_liabilities"],
    },
    "debt_to_equity": {
        "label": "نسبت بدهی به حقوق صاحبان سهام (D/E)",
        "formula": "جمع بدهی‌ها / حقوق صاحبان سهام",
        "description": "میزان اهرم مالی شرکت را نشان می‌دهد",
        "good_range": "< ۱",
        "inputs": ["total_liabilities", "total_equity"],
        "fallback_inputs": ["total_liabilities", "equity"],
    },
    "roe": {
        "label": "بازده حقوق صاحبان سهام (ROE)",
        "formula": "سود خالص / حقوق صاحبان سهام",
        "description": "میزان بازدهی سرمایه صاحبان سهام",
        "good_range": "> ۲۰%",
        "inputs": ["net_profit", "total_equity"],
        "fallback_inputs": ["net_profit", "equity"],
    },
    "roa": {
        "label": "بازده دارایی‌ها (ROA)",
        "formula": "سود خالص / جمع دارایی‌ها",
        "description": "میزان کارایی شرکت در استفاده از دارایی‌ها",
        "good_range": "> ۱۰%",
        "inputs": ["net_profit", "total_assets"],
    },
    "gross_margin": {
        "label": "حاشیه سود ناخالص",
        "formula": "سود ناخالص / فروش",
        "description": "درصد سود پس از کسر بهای تمام شده",
        "good_range": "متغیر بر اساس صنعت",
        "inputs": ["gross_profit", "revenue"],
    },
    "net_margin": {
        "label": "حاشیه سود خالص",
        "formula": "سود خالص / فروش",
        "description": "درصد سود خالص از فروش",
        "good_range": "> ۱۰%",
        "inputs": ["net_profit", "revenue"],
    },
    "operating_margin": {
        "label": "حاشیه سود عملیاتی",
        "formula": "سود عملیاتی / فروش",
        "description": "درصد سود عملیاتی از فروش",
        "good_range": "> ۱۵%",
        "inputs": ["operating_profit", "revenue"],
    },
}


def _classify_item(label: str) -> str | None:
    """Match a Persian label against known financial statement keywords."""
    label_clean = label.strip().replace("\u200c", "")
    for category, keywords in FINANCIAL_KEYWORDS.items():
        for kw in keywords:
            kw_clean = kw.replace("\u200c", "")
            if kw_clean in label_clean:
                return category
    return None


def _extract_last_value(item: dict[str, Any]) -> float:
    """Get the last non-zero numeric value from an item's values dict."""
    vals = list(item["values"].values())
    for v in reversed(vals):
        if v != 0:
            return v
    return 0.0


def calculate_ratios(symbol: str) -> dict[str, Any]:
    """Calculate accounting ratios from latest reports for a symbol."""
    reports = list_reports(symbol)
    if not reports:
        return {"symbol": symbol, "error": "No reports found"}

    # Collect all classified items from latest report of each type
    classified: dict[str, float] = {}
    seen_labels: set[str] = set()

    for rt in {r["report_type"] for r in reports if r["report_type"]}:
        type_reports = [r for r in reports if r["report_type"] == rt]
        if not type_reports:
            continue
        parsed = parse_report(type_reports[0]["filepath"])
        if not parsed or "error" in parsed:
            continue

        for table in parsed.get("tables", []):
            for item in table.get("items", []):
                label = item["label"]
                if label in seen_labels:
                    continue
                category = _classify_item(label)
                if category:
                    seen_labels.add(label)
                    value = _extract_last_value(item)
                    if value != 0:
                        # Keep the largest value for this category (main total)
                        if category not in classified or abs(value) > abs(classified[category]):
                            classified[category] = value

    # Calculate ratios
    ratios: list[dict[str, Any]] = []
    dict(classified)

    for key, defn in RATIO_DEFINITIONS.items():
        # Try primary inputs, then fallback
        numerator = None
        denominator = None
        for inputs in [defn["inputs"], defn.get("fallback_inputs", [])]:
            if len(inputs) >= 2:
                a = classified.get(inputs[0])
                b = classified.get(inputs[1])
                if a is not None and b is not None and b != 0:
                    numerator = a
                    denominator = b
                    break

        if numerator is not None and denominator is not None:
            ratio_value = numerator / denominator
            ratio_pct = ratio_value * 100

            ratios.append({
                "key": key,
                "label": defn["label"],
                "formula": defn["formula"],
                "description": defn["description"],
                "good_range": defn["good_range"],
                "value": round(ratio_value, 4),
                "value_pct": round(ratio_pct, 2),
                "numerator": round(numerator, 2),
                "denominator": round(denominator, 2),
                "numerator_label": defn["inputs"][0] if len(defn["inputs"]) >= 1 else "",
                "denominator_label": defn["inputs"][1] if len(defn["inputs"]) >= 2 else "",
            })

    return {
        "symbol": symbol,
        "total_reports": len(reports),
        "classified_items": {k: round(v, 2) for k, v in sorted(classified.items(), key=lambda x: abs(x[1]), reverse=True)},
        "ratios": ratios,
        "ratio_count": len(ratios),
    }


def get_financial_summary(symbol: str) -> dict[str, Any]:
    """Get a structured financial summary for a symbol from latest reports."""
    reports = list_reports(symbol)
    if not reports:
        return {"symbol": symbol, "error": "No reports found"}

    result: dict[str, Any] = {
        "symbol": symbol,
        "total_reports": len(reports),
        "latest_reports": {},
        "summary": {},
    }

    # Get the latest of each report type
    for rt in {r["report_type"] for r in reports if r["report_type"]}:
        type_reports = [r for r in reports if r["report_type"] == rt]
        if type_reports:
            latest = type_reports[0]
            parsed = parse_report(latest["filepath"])
            if parsed and "error" not in parsed:
                table_summaries: dict[str, Any] = {}
                for table in parsed.get("tables", []):
                    # Extract financial items from the table
                    for item in table.get("items", []):
                        label = item["label"]
                        if label in ("جمع", "مجموع"):
                            continue
                        if item["values"]:
                            # Get the last numeric value (most recent period)
                            vals = list(item["values"].values())
                            numeric_vals = [v for v in vals if v != 0]
                            if numeric_vals:
                                table_summaries[label] = numeric_vals[-1]

                result["latest_reports"][rt] = {
                    "date": latest["date"],
                    "filename": latest["filename"],
                    "label": REPORT_TYPE_LABELS.get(rt, rt),
                    "items": table_summaries,
                }

    return result
