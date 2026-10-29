import json
import pathlib
import re

routes=set()
for p in list(pathlib.Path('frontend/src').rglob('*.tsx'))+list(pathlib.Path('frontend/src').rglob('*.ts')):
    try:
        t=p.read_text(encoding='utf-8',errors='ignore')
        for m in re.findall(r'path\s*:\s*["\']([^"\']+)["\']',t):
            routes.add(m)
    except Exception:
        pass
npy=len(list(pathlib.Path("src").rglob("*.py")))
deps={"routes_sample":sorted(routes)[:80],"total_routes":len(routes),"src_py_count":npy}
pathlib.Path("qa").mkdir(exist_ok=True)
pathlib.Path("qa/dependencies.map.json").write_text(json.dumps(deps,ensure_ascii=False,indent=1),encoding="utf-8")
print(f"routes={len(routes)} py={npy} wrote ok")
