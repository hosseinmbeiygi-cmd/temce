import re, pathlib

ROOTS = ["src", "core", "services", "api", "app", "jobs", "models", "BrsApi_Forecasting"]
files = []
for r in ROOTS:
    p = pathlib.Path(r)
    if p.exists():
        files += [f for f in p.rglob("*.py") if "test" not in f.parts and "venv" not in f.parts]
print("files_scanned=", len(files))

CHECKS = {
    "hardcoded_secret": re.compile(r"(password|api_key|secret_key|private_key)\s*=\s*['\"][^'\"]{3,}['\"]", re.I),
    "fstring_sql": re.compile(r"(text|execute)\s*\(\s*f['\"]"),
    "sql_concat": re.compile(r"execute\s*\(.*\+\s*(table|symbol|col)", re.I),
    "auth_bypass": re.compile(r"(skip_auth|no_auth|verify\s*=\s*False|allow_all|dev_bypass)", re.I),
    "float_money_col": re.compile(r"(price|pnl|profit|balance|amount|nav|fee|commission)\w*\s*=\s*.*(Float|FLOAT)", re.I),
    "lookahead": re.compile(r"shift\s*\(\s*-\d|iloc\s*\[\s*:.*-1|future.*price|peek.*next", re.I),
    "bare_except": re.compile(r"except\s*(Exception\s*)?:\s*pass"),
}
for name, rx in CHECKS.items():
    hits = []
    for f in files:
        try:
            for i, ln in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if rx.search(ln) and len(hits) < 12:
                    hits.append(f"{f}:{i}:{ln.strip()[:140]}")
        except Exception:
            pass
    print(f"== {name}: {len(hits)}")
    for h in hits[:12]:
        print("  ", h)

out = pathlib.Path("qa/security_static.txt")
out.write_text("static audit done", encoding="utf-8")
