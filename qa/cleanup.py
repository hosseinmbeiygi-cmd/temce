"""Cleanup synthetic QA artifacts (no app source touched)."""
import pathlib
import shutil

for d in ["qa/tmp_orders","qa/tmp_alerts","test-screenshots/tmp"]:
    p=pathlib.Path(d)
    if p.exists(): shutil.rmtree(p,ignore_errors=True)
# remove scan helper scripts only if needed? keep them.
print("cleanup done: synthetic QA dirs purged")
