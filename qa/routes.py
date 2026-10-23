import pathlib, re, json

pages = sorted(pathlib.Path("frontend/src/app").rglob("page.tsx"))
routes = []
for p in pages:
    rel = p.parent.relative_to(pathlib.Path("frontend/src/app")).as_posix()
    route = "/" if rel == "." else "/" + re.sub(r"/\[([^\]]+)\]", r"/:param", rel)
    # strip route groups (parentheses)
    route = re.sub(r"/\([^/]+\)", "", route) or "/"
    routes.append(route)
# dynamic sample values for :param segments
def fill(r):
    return r.replace(":param", "test")
out = {"total": len(routes), "routes": sorted(set(routes))}
pathlib.Path("qa").mkdir(exist_ok=True)
pathlib.Path("qa/route_catalog.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("routes=", out["total"], "unique=", len(out["routes"]))
for r in sorted(set(routes))[:10]:
    print("  ", r)
