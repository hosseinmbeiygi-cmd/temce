import json
import pathlib
import re

roots=["src","core","api","services","app","gold_desk" if pathlib.Path("src/gold_desk").exists() else "src"]
files=[]
for r in ["src","core","api","services","app"]:
    p=pathlib.Path(r)
    if p.exists():
        files+=list(p.rglob("*.py"))
idem={"idempotency_key":0,"unique_constraint":0,"mutex_lock":0,"files_with_post":0}
posts=[]
for f in files:
    try:
        t=f.read_text(encoding="utf-8",errors="ignore")
    except Exception:
        continue
    if re.search(r"@.*(post|put)|def (create_order|create_alert|submit_backtest|place_order)",t,re.I):
        idem["files_with_post"]+=1
        posts.append(str(f))
    if re.search(r"idempotency",t,re.I):
        idem["idempotency_key"]+=1
    if re.search(r"UniqueConstraint|unique=True|ON CONFLICT",t):
        idem["unique_constraint"]+=1
    if re.search(r"Lock|mutex|Semaphore|transaction|atomic|select_for_update",t,re.I):
        idem["mutex_lock"]+=1
alert=[str(p) for p in files if "alert" in str(p).lower()][:15]
out={"idempotency":idem,"post_endpoints_sample":posts[:20],"alert_files":alert,
 "verdict":"NO idempotency-key mechanism found" if idem["idempotency_key"]==0 else "partial"}
pathlib.Path("qa/concurrency_static.json").write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding="utf-8")
md="# Concurrency & Alert Static Audit\n\n- POST/creation endpoints: {}\n- idempotency-key hits: {}\n- unique constraints: {}\n- lock/transaction hits: {}\n\nVerdict: {} — P0: add Idempotency-Key header + DB unique constraint on (client_key) for orders/alerts/backtest jobs.\n".format(idem["files_with_post"],idem["idempotency_key"],idem["unique_constraint"],idem["mutex_lock"],out["verdict"])
pathlib.Path("reports/concurrency_static.md").write_text(md,encoding="utf-8")
st=json.loads(pathlib.Path("qa/phase_status.json").read_text(encoding="utf-8"))
st["concurrency_static"]="done"
pathlib.Path("qa/phase_status.json").write_text(json.dumps(st),encoding="utf-8")
print(json.dumps(idem))
