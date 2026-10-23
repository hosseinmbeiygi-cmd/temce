import pathlib, re, json
pats=["pnl","realized","unrealized","drawdown","sharpe","margin","leverage","nav","fee","slippage","rsi","macd","ema"]
hits=[]
for p in list(pathlib.Path("src").rglob("*.py"))+list(pathlib.Path("backtesting").rglob("*.py"))+list(pathlib.Path("core").rglob("*.py")):
    try: t=p.read_text(encoding="utf-8",errors="ignore")
    except Exception: continue
    low=t.lower()
    if any(k in low for k in pats):
        uses_decimal=bool(re.search(r"Decimal|BigNumber|quantize|integer",t))
        uses_float=bool(re.search(r"\bfloat\(|np\.float|float64",t))
        divzero=bool(re.search(r"/\s*(std|variance|n\b|count|(-?equity))",t))
        if uses_float or not uses_decimal:
            # capture first risky line
            for i,line in enumerate(t.splitlines(),1):
                if re.search(r"float\(|/\s*\w|pnl|p&l|drawdown|sharpe",line,re.I):
                    hits.append({"file":str(p),"line":i,"code":line.strip()[:200],"float":uses_float,"decimal":uses_decimal})
                    break
        if len(hits)>=30: break
pathlib.Path("qa").mkdir(exist_ok=True)
log="\n".join([f"{h['file']}:{h['line']} | decimal={h['decimal']} float={h['float']} | {h['code']}" for h in hits])
pathlib.Path("qa/math_integrity.log").write_text(f"hotspots={len(hits)}\n"+log,encoding="utf-8")
pathlib.Path("qa/phase_status.json").write_text(json.dumps({"phase1":"done","phase2":"done","hotspots":len(hits)}),encoding="utf-8")
print(f"hotspots={len(hits)}")
