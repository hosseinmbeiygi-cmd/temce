import re, pathlib
log = pathlib.Path("qa/upgrade_head.log").read_text(encoding="utf-8", errors="ignore")
print("log_bytes=", len(log))
# find Running upgrade lines and first error
runs = re.findall(r"Running upgrade ([0-9a-f]+) -> ([0-9a-f]+)", log)
print("last_runs=", runs[-5:])
m = re.search(r"(FAILED|Error|error)[^\n]{0,200}", log)
print("first_err=", m.group(0)[:300] if m else None)
for i, line in enumerate(log.splitlines()):
    if "already exists" in line and ("ERROR" in log[max(0,log.find(line)-500):log.find(line)][:500] or True):
        pass
# print context around first 'already exists' that is an exception
idx = log.find("already exists")
print("ctx=", log[max(0,idx-800):idx+400])
