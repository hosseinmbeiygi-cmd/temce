# Risks / Suspicious Patterns — `temce` (2026-11-01)

**Stance:** every item below is a *heuristic* derived from reading configuration and code
structure. None is a confirmed runtime bug. Each item lists the evidence needed to verify or
dismiss it before any change is made.

Legend — **Evidence class:** `confirmed-fact` (directly observed in the tree) vs
`heuristic` (plausible consequence, not executed). **Severity:** High / Medium / Low.

---

## R1 — Type checking is not a gate (High, confirmed-fact)

- `pyproject.toml:79` defines mypy, but `pyproject.toml:108` sets `ignore_errors = true` for
  the bulk of the codebase (`backtesting.*`, `ml.*`, `brsapi.*`, `repositories.*`,
  `reports.*`, `integrations.*`, `domain.*`, `schemas.*`, `models.*`, `services.smart_money.*`,
  `services.chat.*`), and `exclude` removes several roots entirely.
- `.github/workflows/ci.yml:105` runs `mypy apps core domain services --ignore-missing-imports || true`.
- Only ten signal-chain files are strict, in `.github/workflows/ci-pr.yml` (mypy strict step).
- Also `Makefile: typecheck` ends with `|| true`.

**Impact (heuristic):** type regressions in the majority of modules can merge without CI
signal; the strict list is the only protected island.

**To verify:** run `mypy apps core domain services` and compare the error count with the
baseline recorded in `baseline_*.txt`; check whether the strict ten still pass.

---

## R2 — The layering contract is measured, not enforced (High, confirmed-fact)

- `.importlinter:59-63`: the contract “services must import sqlalchemy only via repositories
  or core.database” is neutralised by a wildcard `ignore_imports: services.* -> sqlalchemy`
  until “the 65 raw-sqlalchemy imports in services/” reach zero (ADR-0001).
- `.github/workflows/ci.yml:102` runs `lint-imports ... || echo "::warning::…"` — violations
  never fail CI.

**Impact (heuristic):** `services/` can keep growing direct DB/SQL access without a blocking
signal; the repository seam described in `repositories/` erodes silently.

**To verify:** `lint-imports --config .importlinter` without the wildcard ignore and count
`services.* -> sqlalchemy` edges.

---

## R3 — The default test command skips the DB-backed path (Medium, confirmed-fact)

- `pyproject.toml:130`: `addopts = ["--capture=no", "-m", "not needs_db"]`.
- 16 test files reference `needs_db`; CI runs `pytest tests/unit` and `tests/gold_desk`
  (`.github/workflows/ci.yml:265,282`).
- `pyproject.toml:140` pins `timeout_method = "thread"` on Windows with an explicit warning
  that a native stall kills the whole process.

**Impact (heuristic):** the admin dashboard path that scans ~5.5M rows is excluded from the
default run, so “tests green” does not cover the heaviest read path.

**To verify:** run `pytest -m needs_db` against a reachable PostgreSQL and record pass/fail.

---

## R4 — A database WAL is tracked without its database (Medium, confirmed-fact)

- `git ls-tree` lists `transactions.db-wal` at **26,322,712 bytes**.
- The 5.2 GB `transactions.db` itself is **not** tracked (present only on disk).
- Other tracked binaries: `Redis/redis-server.pdb` (7 MB), `Redis/Redis.zip` (5.2 MB),
  `Redis/redis-cli.pdb`, `Redis/redis-benchmark.pdb`, `Redis/redis-check-aof.pdb`.

**Impact (heuristic):** a WAL without its main DB is unusable and misleading; a fresh clone
gets a stale artifact that can never be replayed. Repo size and clone time grow for no
functional gain.

**To verify:** confirm no script consumes `transactions.db-wal` from a fresh clone
(`grep -rn "transactions.db-wal"`).

---

## R5 — Generated code dumps are tracked next to the code they summarise (Medium, confirmed-fact)

Tracked snapshots: `BACKTEST_ALL_CODE.txt` (2.4 MB), `gold_complete_bundle.txt` (4.8 MB),
`GOLD_CODE_FULL.txt` / `GOLD_CODE_COMPILATION.txt` (~1.6 MB each), `symbol_reports/dashboard.md`
(3.4 MB), `reports/runs/2026-09-27_run_full-run.txt` (2.7 MB).

**Impact (heuristic):** dumps drift from the source immediately after any edit and can be
mistaken for the current implementation during review or by an agent.

**To verify:** diff one dump against its source module list; check whether anything imports
or reads them at runtime.

---

## R6 — A duplicated backend tree contains its own security code (Medium, confirmed-fact)

- `_FRONTEND_BACKEND_COPY/backend/` holds 1,848 Python files, including
  `_FRONTEND_BACKEND_COPY/backend/core/security/secrets.py` and
  `_FRONTEND_BACKEND_COPY/backend/integrations/secrets.py`, which are tracked alongside the
  live `core/security/secrets.py` and `integrations/secrets.py`.
- Similarly `_audit_base/` (5,040 py, 308 MB), `_base_wt/` (4,859 py, 216 MB),
  `_base_wt_clean/` (4,492 py, 226 MB) and `.freebuff/worktrees/…` are full copies.
- Two further nested repositories sit at the root: `InkGist` (219 MB on disk, including its
  own `node_modules/`) and `dsh-our-free-model` (182 MB, including its own `.git/`).

**Impact (heuristic):** security fixes can be applied to the copy (or missed there) and the
grep-based audits can report two different truths. Tools that scan “all Python files” read
duplicates.

**To verify:** compare hashes of the paired `secrets.py` files; confirm no runtime import
path resolves into `_FRONTEND_BACKEND_COPY`.

---

## R7 — UTF-8 BOM in a strict-mypy module (Low, confirmed-fact)

- `services/quant_signal_orchestrator.py:1` begins with U+FEFF; a plain
  `ast.parse(text, encoding="utf-8")` fails with *invalid non-printable character U+FEFF*.
- CPython and mypy tolerate the BOM, so this is not a runtime defect.
- The repo already fixed the same class of issue once: commit `4a239d84
  fix(audit): API-05 router surface inventory + strip ime.py BOM`.

**Impact (heuristic):** any tool that decodes with `utf-8` instead of `utf-8-sig`
(linters, custom scanners, code-graph builders) silently errors on this file — which is one
of the ten strict-mypy files.

**To verify:** `python -c "open('services/quant_signal_orchestrator.py','rb').read(3)"`;
strip and re-run the strict mypy job.

---

## R8 — API documentation is always exposed (Medium, confirmed-fact)

- `apps/api/app.py:1068-1069`: `docs_url="/docs"`, `openapi_url="/openapi.json"` are
  unconditional — no `settings.is_production` branch.
- `SecurityMiddleware` gates only sensitive *write* prefixes (`apps/api/middleware.py:125-160`);
  GET `/docs` and `/openapi.json` are not in that list.

**Impact (heuristic):** the full route and schema surface (including internal admin routes)
is publicly enumerable in production. Whether that is acceptable is a product decision, not
an observed vulnerability.

**To verify:** hit `/openapi.json` on a staging/steps deployment and decide whether exposure
is intended; if not, gate on `settings.is_production`.

---

## R9 — CORS defaults to `["*"]` and is corrected only by the production validator (Low, confirmed-fact)

- `core/config/api.py:16`: `cors_origins` default `["*"]`; `apps/api/app.py:1075-1076` enables
  `allow_credentials=True`.
- `core/config/__init__.py:484` rejects `["*"]`, but only inside `validate_production()`, which
  runs for `production`/`staging` (`core/config/__init__.py:473-480`).
- Startup calls exist in `apps/api/app.py:899`, `apps/admin/app.py:19`,
  `apps/currency_service/app.py:26`.

**Impact (heuristic):** wildcard origin + credentials is only safe because the validator fails
closed; any process path that constructs settings and skips validation would run the insecure
combination. (Starlette will not emit `Access-Control-Allow-Origin: *` with credentials, so the
practical failure mode is a broken preflight rather than a leak — still worth pinning.)

**To verify:** enumerate every process entrypoint that builds a FastAPI app and confirm each
calls `validate_production()`.

---

## R10 — Analysis was performed against a dirty tree (Medium, methodological)

- `git status --porcelain` returned **236** entries (modified/staged) on `w4-fix-security`.
- The concurrent-editor memory for this repo says the tree is shared and files can change
  under an analysis.

**Impact:** line-number citations can shift if the tree changes; conclusions describe the
observed snapshot, not a frozen commit.

**To verify:** re-run the cited `grep`/`sed` commands before acting on any line number.

---

## R11 — Root directory is a scratch area (Low, confirmed-fact)

- 105 `.txt/.log/.db/.bin` artifacts at repo root (`collector.log` 14 MB,
  `full_unit_issue4.log` ~11 MB, `unit_v*.log`, `_probe_*.py`, `z.py`, `t.bin` …), plus
  untracked `.env.bak.1790980646` and `.env.production` (untracked — no secret leak, but
  rotation/backup files live next to the code).

**Impact (heuristic):** no functional effect; it slows every whole-tree scan and invites
accidental use of stale probe output as evidence.

**To verify:** `git status --ignored --short | head` and confirm `.gitignore` covers them.

---

## R12 — Undeclared nested repositories (Medium, confirmed-fact)

- `git ls-tree HEAD` records `InkGist` and `dsh-our-free-model` as mode `160000` gitlinks at
  commits `cc81661…` and `482500f…`.
- There is **no `.gitmodules`** file, and `git submodule status` returns nothing.
- On disk they occupy 219 MB and 182 MB respectively, each with its own VCS/dependency tree;
  `git status` reports the `InkGist` gitlink as modified (` m InkGist`).

**Impact (heuristic):** a fresh clone cannot materialise either directory (git has no URL to
fetch from), so any build, import or audit step that expects them behaves differently on a
clean checkout than on this machine. The modified gitlink also means the recorded commit does
not match the local content.

**To verify:** `git ls-tree HEAD | grep -E 'InkGist|dsh-our-free-model'`, check for
`.gitmodules`, and run `git clone --recurse-submodules` into a temp dir to observe the empty
directories.

---

## Explicit non-findings (checked, nothing suspicious)

- No silent bare `except:` blocks in 1,488 backend modules (AST scan).
- `.env`, credentials and PEM/key material are **not** tracked (`git ls-tree` check).
- Mount-level auth is present on 72 of 80 router mounts; the remaining 8 are `health`,
  `auth`, `golddesk` (scoped tokens), `gold_desk_public`, `gold/analytics` (per-endpoint
  `Depends(get_current_user)`), two WebSocket routers (`verify_websocket_token`), and
  `system` (per-endpoint dual-role checks).
- Production configuration is checked at boot and fails closed.
