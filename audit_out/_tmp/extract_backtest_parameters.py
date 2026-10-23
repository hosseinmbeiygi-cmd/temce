"""استخراج کامل پارامترهای مسیر بک‌تست طلا — از خودِ کد (نه از حافظه).

خروجی: فهرست امضاها، فیلدهای dataclass، و پارامترهای بی‌اثر (با شاهد کد).
هیچ چیزی تغییر نمی‌دهد؛ فقط می‌خواند و چاپ می‌کند.
"""

from __future__ import annotations

import dataclasses
import inspect
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from gold_desk import backtest, backtest_real, backtest_runner  # noqa: E402

MODULES = [
    ("src/gold_desk/backtest.py", backtest),
    ("src/gold_desk/backtest_real.py", backtest_real),
    ("src/gold_desk/backtest_runner.py", backtest_runner),
]


def line_of(obj) -> str:
    try:
        _, start = inspect.getsourcelines(obj)
        return str(start)
    except Exception:
        return "?"


def main() -> None:
    print("=" * 78)
    print("1) پارامترهای توابع عمومی/نیمه‌عمومی مسیر بک‌تست + مقدار پیش‌فرض + خط")
    print("=" * 78)
    for rel, mod in MODULES:
        print(f"\n--- {rel} ---")
        members = [
            (name, obj)
            for name, obj in vars(mod).items()
            if callable(obj)
            and getattr(obj, "__module__", None) == mod.__name__
            and not name.startswith("__")
        ]
        for name, fn in members:
            try:
                sig = inspect.signature(fn)
            except (TypeError, ValueError):
                continue
            parts = []
            for pname, p in sig.parameters.items():
                default = "" if p.default is p.empty else f"={p.default!r}"
                parts.append(f"{pname}{default}")
            print(f"  L{line_of(fn):>4}  {name}({', '.join(parts)})")

    print()
    print("=" * 78)
    print("2) فیلدهای dataclassهای ورودی/خروجی")
    print("=" * 78)
    for rel, mod in MODULES:
        for name, obj in vars(mod).items():
            if dataclasses.is_dataclass(obj) and getattr(obj, "__module__", None) == mod.__name__:
                fields = ", ".join(f.name for f in dataclasses.fields(obj))
                print(f"  {rel:<34} {name}: {fields}")

    print()
    print("=" * 78)
    print("3) پارامترهای بی‌اثر (استخراج از بدنهٔ تابع)")
    print("=" * 78)
    checks = [
        (backtest_real.strategy_rsi_oversold, "dates"),
        (backtest_real.strategy_ma_crossover, "dates"),
        (backtest_real.strategy_bubble_threshold, "dates"),
        (backtest_real._compute_metrics, "all_prices"),
    ]
    for fn, param in checks:
        src = inspect.getsource(fn)
        body = "\n".join(src.splitlines()[1:])  # بدون خط امضا
        uses = re.findall(rf"\b{re.escape(param)}\b", body)
        print(f"  {fn.__name__:<28} پارامتر {param!r}: {len(uses)} ارجاع در بدنه")

    print()
    print("=" * 78)
    print("4) اعداد جادویی داخل منطق بک‌تست (خط + متن)")
    print("=" * 78)
    pattern = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.]*['\"])")
    for rel, _mod in MODULES:
        print(f"\n--- {rel} ---")
        for i, line in enumerate((ROOT / rel).read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            if not pattern.search(line):
                continue
            if re.match(r"^(from|import|logger|@)", stripped):
                continue
            print(f"  L{i:>4}  {stripped[:110]}")

    print()
    print("=" * 78)
    print("5) ناسازگاری پیش‌فرض‌های هم‌نام بین سه ماژول")
    print("=" * 78)
    for fn_name in ("run_backtest", "run_real_backtest", "run_strategy_backtest"):
        for _rel, mod in MODULES:
            fn = getattr(mod, fn_name, None)
            if fn is None:
                continue
            sig = inspect.signature(fn)
            defaults = {k: v.default for k, v in sig.parameters.items() if v.default is not inspect._empty}
            print(f"  {fn.__name__:<24} {defaults}")


main()
