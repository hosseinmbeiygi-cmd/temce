"""استخراج کامل پارامترهای مسیر بک‌تست — کل مخزن، از خودِ کد.

برخلاف نسخهٔ قبلی (`extract_backtest_parameters.py`) که فقط سه ماژول gold_desk را
import می‌کرد، این نسخه با AST تمام فایل‌های مسیر بک‌تست را می‌خواند:

  * src/gold_desk/backtest*.py      (بک‌تست طلا/سکه)
  * services/backtest*.py, signal_backtest_engine.py, walk_forward_validator.py
  * domain/backtest/**              (قواعد دامنه)
  * backtesting/**                  (موتور کامل بک‌تست)

هیچ چیزی تغییر نمی‌دهد؛ فقط می‌خواند و چاپ می‌کند.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def is_backtest_path(p: Path) -> bool:
    rel = p.relative_to(ROOT).as_posix()
    if rel.startswith("backtesting/"):
        return True
    if rel.startswith("domain/backtest/"):
        return True
    if rel.startswith("src/gold_desk/"):
        return p.name.startswith("backtest")
    if rel.startswith("services/"):
        name = p.name
        return (
            name.startswith("backtest")
            or name in {"signal_backtest_engine.py", "walk_forward_validator.py"}
        )
    return False


def collect_files() -> list[Path]:
    out: list[Path] = []
    for pat in ("backtesting/**/*.py", "domain/backtest/**/*.py", "src/gold_desk/*.py", "services/*.py"):
        for p in sorted(ROOT.glob(pat)):
            if "__pycache__" in p.parts:
                continue
            if is_backtest_path(p):
                out.append(p)
    return out


def annotation_str(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover
        return "?"


def signature_of(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    a = fn.args
    parts: list[str] = []
    posonly = getattr(a, "posonlyargs", [])
    positional = list(posonly) + list(a.args)
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(a.defaults)) + list(a.defaults)
    for arg, default in zip(positional, defaults, strict=False):
        piece = arg.arg
        ann = annotation_str(arg.annotation)
        if ann:
            piece += f": {ann}"
        if default is not None:
            try:
                piece += f" = {ast.unparse(default)}"
            except Exception:  # pragma: no cover
                piece += " = ?"
        parts.append(piece)
    if a.vararg:
        parts.append("*" + a.vararg.arg)
    for arg, default in zip(a.kwonlyargs, a.kw_defaults, strict=False):
        piece = arg.arg
        if default is not None:
            try:
                piece += f" = {ast.unparse(default)}"
            except Exception:  # pragma: no cover
                piece += " = ?"
        parts.append(piece)
    if a.kwarg:
        parts.append("**" + a.kwarg.arg)
    kind = "async def" if isinstance(fn, ast.AsyncFunctionDef) else "def"
    ret = annotation_str(fn.returns)
    return f"{kind} {fn.name}({', '.join(parts)})" + (f" -> {ret}" if ret else "")


def defaults_of(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, str]:
    a = fn.args
    positional = list(getattr(a, "posonlyargs", [])) + list(a.args)
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(a.defaults)) + list(a.defaults)
    out: dict[str, str] = {}
    for arg, default in zip(positional, defaults, strict=False):
        if default is not None:
            try:
                out[arg.arg] = ast.unparse(default)
            except Exception:  # pragma: no cover
                out[arg.arg] = "?"
    for arg, default in zip(a.kwonlyargs, a.kw_defaults, strict=False):
        if default is not None:
            try:
                out[arg.arg] = ast.unparse(default)
            except Exception:  # pragma: no cover
                out[arg.arg] = "?"
    return out


def is_dataclass(node: ast.ClassDef) -> bool:
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Name) and target.id == "dataclass":
            return True
        if isinstance(target, ast.Attribute) and target.attr == "dataclass":
            return True
    return False


def dataclass_fields(node: ast.ClassDef) -> list[str]:
    out: list[str] = []
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            out.append(stmt.target.id)
        elif isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name):
                    out.append(t.id)
    return out


def main() -> None:  # noqa: C901
    files = collect_files()
    functions: list[dict] = []
    dclasses: list[dict] = []
    constants: list[dict] = []
    unparsed: list[str] = []

    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as exc:
            unparsed.append(f"{rel}: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(
                    {
                        "file": rel,
                        "line": node.lineno,
                        "name": node.name,
                        "signature": signature_of(node),
                        "defaults": defaults_of(node),
                    }
                )
            elif isinstance(node, ast.ClassDef) and is_dataclass(node):
                dclasses.append({"file": rel, "line": node.lineno, "name": node.name, "fields": dataclass_fields(node)})
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, (int, float)) and not isinstance(node.value.value, bool):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            constants.append(
                                {"file": rel, "line": node.lineno, "name": t.id, "value": node.value.value}
                            )

    print("=" * 78)
    print("0) دامنهٔ اسکن: فایل‌های مسیر بک‌تست")
    print("=" * 78)
    groups: dict[str, int] = {}
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        key = rel.split("/")[0] if rel.startswith(("backtesting", "domain")) else "/".join(rel.split("/")[:2])
        groups[key] = groups.get(key, 0) + 1
    for key, n in sorted(groups.items()):
        print(f"  {key:<28} {n:>4} فایل")
    print(f"  {'جمع':<28} {len(files):>4} فایل")
    print(f"  توابع: {len(functions)}   dataclass: {len(dclasses)}   ثابت‌های عددی: {len(constants)}")

    print()
    print("=" * 78)
    print("1) توابعی که پارامتر با مقدار پیش‌فرض دارند (پارامترهای قابل‌تنظیم بک‌تست)")
    print("=" * 78)
    with_defaults = [f for f in functions if f["defaults"]]
    print(f"  تعداد: {len(with_defaults)} تابع از {len(functions)}")
    for f in sorted(with_defaults, key=lambda x: (x["file"], x["line"])):
        pretty = ", ".join(f"{k}={v}" for k, v in f["defaults"].items())
        print(f"  {f['file']}:{f['line']}  {f['name']}({pretty})")

    print()
    print("=" * 78)
    print("2) dataclassهای ورودی/خروجی بک‌تست")
    print("=" * 78)
    for d in sorted(dclasses, key=lambda x: (x["file"], x["line"])):
        print(f"  {d['file']}:{d['line']}  {d['name']}: {', '.join(d['fields'])}")

    print()
    print("=" * 78)
    print("3) ناسازگاری پیش‌فرض‌های هم‌نام (توابع هم‌نام با پارامتر مشترک و پیش‌فرض متفاوت)")
    print("=" * 78)
    by_name: dict[str, list[dict]] = {}
    for f in functions:
        by_name.setdefault(f["name"], []).append(f)
    found = 0
    for name, entries in sorted(by_name.items()):
        if len(entries) < 2:
            continue
        keys = {k for e in entries for k in e["defaults"]}
        for key in sorted(keys):
            values = {e["defaults"][key] for e in entries if key in e["defaults"]}
            if len(values) > 1:
                found += 1
                locs = ", ".join(f"{e['file']}:{e['line']}({e['defaults'].get(key)})" for e in entries if key in e["defaults"])
                print(f"  {name}.{key}: {locs}")
    print(f"  تعداد ناسازگاری: {found}")

    print()
    print("=" * 78)
    print("4) ثابت‌های عددی سطح ماژول در مسیر بک‌تست (نام‌دار = قابل‌ردیابی)")
    print("=" * 78)
    for c in sorted(constants, key=lambda x: (x["file"], x["line"])):
        print(f"  {c['file']}:{c['line']}  {c['name']} = {c['value']}")

    if unparsed:
        print()
        print("=" * 78)
        print("5) فایل‌های پارس‌نشده")
        print("=" * 78)
        for u in unparsed:
            print(f"  {u}")

    out = ROOT / "audit_out" / "_logs" / "backtest_parameters_full.json"
    out.write_text(
        json.dumps(
            {"files": [p.relative_to(ROOT).as_posix() for p in files], "functions": functions, "dataclasses": dclasses, "constants": constants, "unparsed": unparsed},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print()
    print(f"[json] {out.relative_to(ROOT).as_posix()}")


main()
