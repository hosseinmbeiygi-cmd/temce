"""Pattern scanner for the temce repo.

Emits a JSON list of findings with exact file/line/snippet so the report can
quote the real source line instead of a guessed location.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(".")
PY_ROOTS = [
    "brsapi",
    "apps",
    "ingestion",
    "jobs",
    "core",
    "domain",
    "services",
    "api",
    "repositories",
    "providers",
    "orchestration",
    "monitoring",
    "integrations",
    "contracts",
    "schemas",
    "config",
]
TS_ROOT = "frontend/src"
SKIP_PARTS = {"__pycache__", "node_modules", ".next", "test", "tests", "__tests__", ".venv", "venv"}


def iter_py():
    for root in PY_ROOTS:
        for p in Path(root).rglob("*.py"):
            if any(part in SKIP_PARTS for part in p.parts):
                continue
            yield p


def iter_ts():
    for p in Path(TS_ROOT).rglob("*"):
        if p.suffix not in {".ts", ".tsx"}:
            continue
        if any(part in SKIP_PARTS for part in p.parts):
            continue
        yield p


def find(p: Path, patterns, limit=400):
    out = []
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    in_async = False
    async_indent = -1
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if re.match(r"^(\s*)async def ", line):
            in_async = True
            async_indent = indent
        elif re.match(r"^(\s*)(def|class) ", line) and indent <= async_indent:
            in_async = False
        for det in patterns:
            if det.get("async_only") and not in_async:
                continue
            if det["re"].search(line):
                if len(out) < limit:
                    out.append(
                        {
                            "rule": det["rule"],
                            "line": i,
                            "snippet": line.strip()[:200],
                        }
                    )
                break
    return out


DETECTORS = [
    {"rule": "PY_BARE_EXCEPT", "re": re.compile(r"^\s*except\s*:")},
    {"rule": "PY_EXCEPT_PASS", "re": re.compile(r"^\s*except[^:]*:\s*pass\s*$")},
    {"rule": "PY_SLEEP_IN_ASYNC", "re": re.compile(r"\btime\.sleep\("), "async_only": True},
    {"rule": "PY_SYNC_REQUESTS", "re": re.compile(r"(^|\s)import requests|requests\.(get|post|put|delete)\(")},
    {"rule": "PY_SYNC_HTTPX_CLIENT", "re": re.compile(r"httpx\.Client\(")},
    {"rule": "PY_VERIFY_FALSE", "re": re.compile(r"verify\s*=\s*False")},
    {"rule": "PY_NAIVE_NOW", "re": re.compile(r"datetime\.now\(\s*\)")},
    {"rule": "PY_UTCNOW", "re": re.compile(r"datetime\.utcnow\(")},
    {"rule": "PY_EVAL", "re": re.compile(r"(?<![\w.])(eval|exec)\(")},
    {"rule": "PY_PICKLE", "re": re.compile(r"pickle\.loads?\(")},
    {"rule": "PY_YAML_UNSAFE", "re": re.compile(r"yaml\.load\((?![^)]*Loader)")},
    {"rule": "PY_SHELL_TRUE", "re": re.compile(r"shell\s*=\s*True")},
    {"rule": "PY_EQ_NONE", "re": re.compile(r"[!=]=\s*None\b")},
    {"rule": "PY_MUTABLE_DEFAULT", "re": re.compile(r"def [\w_]+\([^)]*=\s*(\[\]|\{\})")},
    {"rule": "PY_TODO", "re": re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")},
    {"rule": "PY_PRINT", "re": re.compile(r"^\s*print\(")},
    {"rule": "PY_SQL_FSTRING", "re": re.compile(r"(?<![A-Za-z_0-9])(execute|text)\(\s*f[\"']")},
    {"rule": "PY_SQL_FORMAT", "re": re.compile(r"\.execute\([^)]*\.format\(")},
    {"rule": "PY_GLOBAL", "re": re.compile(r"^\s*global\s+\w+")},
    {"rule": "PY_ASSERT", "re": re.compile(r"^\s*assert\s+")},
    {"rule": "PY_EXCEPT_BASE", "re": re.compile(r"except\s+BaseException")},
    {"rule": "PY_RAISE_GENERIC", "re": re.compile(r"raise Exception\(")},
    {"rule": "PY_NOQA", "re": re.compile(r"#\s*noqa")},
    {"rule": "PY_TYPE_IGNORE", "re": re.compile(r"#\s*type:\s*ignore")},
    {"rule": "PY_OPEN_NO_WITH", "re": re.compile(r"^\s*\w+\s*=\s*open\(")},
    {"rule": "PY_HARDCODED_LOCAL", "re": re.compile(r"(localhost|127\.0\.0\.1):\d{2,5}")},
    {"rule": "PY_HARDCODED_SECRET", "re": re.compile(r"(?i)(password|passwd|secret|api_key|apikey|token)\s*[:=]\s*[\"'][^\"']{4,}[\"']")},
    {"rule": "PY_CREATE_TASK_UNSAVED", "re": re.compile(r"^\s*asyncio\.create_task\(")},
    {"rule": "PY_SUBPROCESS", "re": re.compile(r"subprocess\.(run|call|Popen|check_output)\(")},
    {"rule": "PY_EXCEPT_LOG_RETURN_EMPTY", "re": re.compile(r"return \[\]")},
]

TS_DETECTORS = [
    {"rule": "TS_CONSOLE", "re": re.compile(r"console\.(log|debug)\(")},
    {"rule": "TS_ANY", "re": re.compile(r":\s*any\b")},
    {"rule": "TS_TSIGNORE", "re": re.compile(r"@ts-(ignore|expect-error)")},
    {"rule": "TS_ESLINT_DISABLE", "re": re.compile(r"eslint-disable")},
    {"rule": "TS_DANGEROUS_HTML", "re": re.compile(r"dangerouslySetInnerHTML")},
    {"rule": "TS_LOCALSTORAGE", "re": re.compile(r"localStorage\.(setItem|getItem)")},
    {"rule": "TS_LOCALHOST", "re": re.compile(r"http://(localhost|127\.0\.0\.1):\d+")},
    {"rule": "TS_TODO", "re": re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")},
    {"rule": "TS_SILENT_EMPTY", "re": re.compile(r"return \[\];")},
    {"rule": "TS_JSON_PARSE", "re": re.compile(r"JSON\.parse\(")},
    {"rule": "TS_AS_ANY", "re": re.compile(r"as any\b")},
    {"rule": "TS_CATCH_SILENT", "re": re.compile(r"\.catch\(\s*\(\s*\)\s*=>|\.catch\(\s*\(\s*\)\s*=>\s*undefined|catch\s*\{\s*$")},
    {"rule": "TS_EMPTY_FALLBACK", "re": re.compile(r"\?\?\s*\[\]")},
    {"rule": "TS_REFETCH_OFF", "re": re.compile(r"refetchOnWindowFocus:\s*false")},
    {"rule": "TS_INTERVAL", "re": re.compile(r"setInterval\(")},
    {"rule": "TS_POLL_FAST", "re": re.compile(r"refetchInterval:\s*\d{1,4}\b")},
]


def broad_except_blocks(p: Path, limit: int = 300):
    """Detect `except Exception` blocks whose body never re-raises.

    A swallowed broad handler is the mechanism that turns a failed sync into a
    silently stale dashboard, so these are reported with their real line.
    """
    out = []
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    pat = re.compile(r"^(\s*)except\s+(Exception|BaseException)(\s+as\s+\w+)?\s*:\s*$")
    for i, line in enumerate(lines):
        m = pat.match(line)
        if not m:
            continue
        indent = len(m.group(1))
        block = []
        j = i + 1
        while j < len(lines):
            cur = lines[j]
            if not cur.strip():
                j += 1
                continue
            cur_indent = len(cur) - len(cur.lstrip())
            if cur_indent <= indent:
                break
            block.append(cur)
            j += 1
        if not block:
            continue
        body = "\n".join(block)
        if re.search(r"^\s*raise\b", body, re.M) or re.search(r"\braise\s*$", body, re.M):
            continue
        out.append({"rule": "PY_BROAD_EXCEPT_SWALLOW", "line": i + 1, "snippet": line.strip()[:200]})
        if len(out) >= limit:
            break
    return out


def main() -> None:
    findings = []
    for p in iter_py():
        for hit in find(p, DETECTORS):
            hit["file"] = str(p).replace("\\", "/")
            findings.append(hit)
        for hit in broad_except_blocks(p):
            hit["file"] = str(p).replace("\\", "/")
            findings.append(hit)
    for p in iter_ts():
        for hit in find(p, TS_DETECTORS):
            hit["file"] = str(p).replace("\\", "/")
            findings.append(hit)

    from collections import Counter

    c = Counter(f["rule"] for f in findings)
    print("total", len(findings))
    for k, v in c.most_common():
        print(k, v)
    with open("_pattern_findings.json", "w", encoding="utf-8") as fh:
        json.dump(findings, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
