import json
import pathlib
import re

roots=["src","core","backtesting","api","services","ml","app","domain"]
files=[]
for r in roots:
    p=pathlib.Path(r)
    if p.exists():
        files+=list(p.rglob("*.py"))
rows=[]
for f in files:
    try:
        lines=f.read_text(encoding="utf-8",errors="ignore").splitlines()
    except Exception:
        continue
    for i,ln in enumerate(lines,1):
        s=ln.strip()
        if not s or s.startswith("#"):
            continue
        risk=None
        if re.search(r"\bfloat\s*\(",ln):
            risk="float-cast-money-risk"
        elif re.search(r"(pnl|profit|loss|balance|price\s*\*|amount\s*\*|nav|fee|commission|slippage)",ln,re.I) and re.search(r"[\+\-\*/]",ln) and not re.search(r"Decimal",ln):
            risk="money-math-no-decimal"
        elif re.search(r"/\s*(std|variance|vol|count|n\b)",ln,re.I):
            risk="div-by-zero-risk"
        elif re.search(r"(sharpe|drawdown|max_dd)",ln,re.I):
            risk="perf-metric-risk"
        elif re.search(r"(iloc\s*\[\s*:\s*-|\.shift\s*\(\s*-|future|lookahead)",ln,re.I):
            risk="lookahead-risk"
        if risk:
            rows.append({"file":str(f),"line":i,"risk":risk,"code":s[:220]})
        if len(rows)>=120:
            break
    if len(rows)>=120:
        break
top=rows[:30]
md=["# TOP 30 Static Code Vulnerabilities\n"]
for k,h in enumerate(top,1):
    md.append(f"## {k}. {h['file']}:{h['line']} [{h['risk']}]")
    md.append(f"```python\n{h['code']}\n```")
    md.append(f"Impact: {h['risk']} may corrupt P&L/NAV/fees or metrics.")
    md.append("Patch: use Decimal for money; guard zero-division; ensure backtest slicing uses only past bars.\n")
pathlib.Path("reports").mkdir(exist_ok=True)
pathlib.Path("reports/TOP30_STATIC_FINDINGS.md").write_text("\n".join(md),encoding="utf-8")
pathlib.Path("qa/top30.json").write_text(json.dumps(top,ensure_ascii=False,indent=1),encoding="utf-8")
st=json.loads(pathlib.Path("qa/phase_status.json").read_text(encoding="utf-8"))
st["static_top30"]="done"
pathlib.Path("qa/phase_status.json").write_text(json.dumps(st),encoding="utf-8")
print(f"scanned_files={len(files)} findings={len(rows)} top30={len(top)}")
