"""Build audit_out/REPORT_FULL.md — یک فایل واحد و خودبسنده از کل ممیزی.

Sources (read-only):
  audit_out/MISSING_ITEMS_REPORT.md   (ادغام بخش‌های A..J)
  audit_out/findings_new.csv          (۴۹ یافته)
Output: audit_out/REPORT_FULL.md
"""
from __future__ import annotations

import csv
import os
import re

BASE = "audit_out"
MERGED = os.path.join(BASE, "MISSING_ITEMS_REPORT.md")
CSV = os.path.join(BASE, "findings_new.csv")
OUT = os.path.join(BASE, "REPORT_FULL.md")

SEV_FA = {
    "critical": "بحرانی",
    "high": "بالا",
    "medium": "متوسط",
    "low": "پایین",
    "info": "اطلاعاتی",
}
ORDER = ["critical", "high", "medium", "low", "info"]

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(n) -> str:
    """اعداد لاتین را به رقم فارسی تبدیل می‌کند (هم‌خوان با بقیهٔ گزارش)."""
    return str(n).translate(_FA_DIGITS)


def esc(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


with open(MERGED, encoding="utf-8") as fh:
    merged = fh.read().strip()

with open(CSV, encoding="utf-8", newline="") as fh:
    rows = list(csv.DictReader(fh))

counts = {sev: sum(1 for r in rows if r["severity"] == sev) for sev in ORDER}
total = len(rows)

# ---- بخش‌های اصلی گزارش (برای فهرست) ----
headers = re.findall(r"^# (.+)$", merged, flags=re.MULTILINE)

out: list[str] = []
out.append("# گزارش کامل ممیزی قابلیت‌اتکا — تک‌فایل (A تا J)")
out.append("")
out.append(
    "> **حکم نهایی: غیرقابل‌اتکا** — اعتبار اندازه‌گیری خراب است، مسیر ML عملاً صفر است، "
    "و یکپارچگی داده/کنترل‌ها معیوب است."
)
out.append(">")
out.append(
    f"> این فایل همهٔ ممیزی را در **یک فایل** جمع می‌کند: ۱۰ بخش (`part_A.md` … `part_J.md`)، "
    f"جدول کامل **{fa(total)} یافته**، شواهد خام و بندهای انجام‌نشده."
)
out.append(">")
out.append(
    f"> توزیع یافته‌ها: {fa(counts['critical'])} بحرانی، {fa(counts['high'])} بالا، "
    f"{fa(counts['medium'])} متوسط، {fa(counts['low'])} پایین، {fa(counts['info'])} اطلاعاتی."
)
out.append(">")
out.append(
    "> قواعد: هیچ عدد/نام فایل/شماره خطی ساخته نشده؛ هر ادعا با عین سطر/عین خروجی پشتیبانی شده؛ "
    "هیچ فایل موجود پروژه تغییر/حذف نشده؛ هیچ نوشتنی روی DB زنده انجام نشده (فقط SELECT)."
)
out.append("")

# ---- فهرست مطالب ----
out.append("## فهرست مطالب")
out.append("")
part_no = 0
for h in headers:
    if h.startswith("بخش ") and "—" in h:
        part_no += 1
        out.append(f"{fa(part_no)}. {h}")
out.append(f"{fa(part_no + 1)}. پیوست الف — جدول کامل یافته‌ها")
out.append(f"{fa(part_no + 2)}. پیوست ب — شواهد خام و بازتولید")
out.append("")

out.append("---")
out.append("")

# ---- متن اصلی (A..J) ----
out.append(merged)
out.append("")
out.append("---")
out.append("")

# ---- پیوست الف: جدول کامل یافته‌ها ----
out.append("# پیوست الف — جدول کامل یافته‌ها")
out.append("")
out.append(
    f"منبع: `audit_out/findings_new.csv` — ستون‌ها: "
    "`id,severity,area,file,line,description,confidence,suggested_action` — "
    f"**{fa(total)} یافته** ({fa(counts['critical'])} بحرانی، {fa(counts['high'])} بالا، "
    f"{fa(counts['medium'])} متوسط، {fa(counts['low'])} پایین، {fa(counts['info'])} اطلاعاتی)."
)
out.append("")
for sev in ORDER:
    sub = [r for r in rows if r["severity"] == sev]
    if not sub:
        continue
    out.append(f"## یافته‌های {SEV_FA[sev]} ({fa(len(sub))})")
    out.append("")
    out.append("| id | دامنه | فایل | خط | شرح | اطمینان | اقدام پیشنهادی |")
    out.append("|---|---|---|---|---|---|---|")
    for r in sub:
        out.append(
            "| {id} | {area} | `{file}` | {line} | {desc} | {conf} | {act} |".format(
                id=esc(r["id"]),
                area=esc(r["area"]),
                file=esc(r["file"]),
                line=esc(r["line"]),
                desc=esc(r["description"]),
                conf=esc(r["confidence"]),
                act=esc(r["suggested_action"]),
            )
        )
    out.append("")

# ---- پیوست ب: شواهد خام ----
out.append("---")
out.append("")
out.append("# پیوست ب — شواهد خام و بازتولید")
out.append("")
out.append("| مسیر | توضیح |")
out.append("|---|---|")
for path, desc in [
    ("audit_out/part_A.md … part_J.md", "۱۰ بخش ممیزی (منبع همین فایل)"),
    ("audit_out/findings_new.csv", f"جدول {fa(total)} یافته (۸ ستون)"),
    ("audit_out/progress.md", "وضعیت هر بخش + بندهای انجام‌نشده"),
    ("audit_out/equity_A.csv … equity_D.csv", "منحنی سرمایهٔ چهار اجرای بازتولیدشده (۲۴۰ سطر هرکدام)"),
    ("audit_out/fills_B.csv", "ریز پرکردن سفارش‌ها در آزمون B (۹۴ سطر)"),
    ("audit_out/_logs/pytest_full.log", "خروجی خام pytest (شکست‌ها با متن خطا)"),
    ("audit_out/_logs/partB.log", "خروجی خام آزمون‌های B"),
    ("audit_out/_logs/validity_harness.out", "خروجی هارنس اعتبارسنجی"),
    ("audit_out/_tmp/*.py / *.json", "اسکریپت‌ها و JSONهای خام (partA..partG، step1..step2)"),
    ("audit_out/_proposed_tests/test_vectorized_signal_origin.py", "تست پیشنهادی گارد منشأ سیگنال"),
    ("audit_out/MISSING_ITEMS_REPORT.md", "ادغام بخش‌های A..J"),
    ("audit_out/RELIABILITY_REPORT.md", "حکم پیشین (قبل از این ممیزی)"),
]:
    out.append(f"| `{path}` | {desc} |")
out.append("")

text = "\n".join(out).rstrip() + "\n"

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(text)
    fh.flush()
    os.fsync(fh.fileno())

print(f"wrote {OUT}")
print(f"bytes={os.path.getsize(OUT)} lines={text.count(chr(10))}")
print(f"findings={total} critical={counts['critical']} high={counts['high']} "
      f"medium={counts['medium']} low={counts['low']} info={counts['info']}")
