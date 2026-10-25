import pathlib
import re

revs = {}
for p in pathlib.Path("migrations/versions").glob("*.py"):
    t = p.read_text(encoding="utf-8", errors="ignore")
    m1 = re.search(r"^revision[^\"']*[\"'](\w+)[\"']", t, re.M)
    m2 = re.search(r"^down_revision[^\"']*[\"'](\w+)[\"']", t, re.M)
    if m1:
        revs[m1.group(1)] = m2.group(1) if m2 else None
c = "0105"
chain = [c]
while revs.get(c):
    c = revs[c]
    chain.append(c)
print("chain:", chain[:4], "len=", len(chain))
