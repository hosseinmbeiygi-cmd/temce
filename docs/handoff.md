# Handoff — Phase 0 DONE (code + tests); Phase 1 not started

**Date:** 2026-10-26 (final evidence run; local +03:30)
**Phase 0:** **DONE** — tasks A–F implemented and tested.
**Phase 1:** **NOT STARTED** — gate remains closed; no Phase 1 feature was added.
**Phase 3:** **CLOSED.**
**Merge recommendation:** Phase 0 code/tests are mergeable on the evidence below; production-authenticated snapshot smoke is the only external check not executed. Owner should sign the flagged assumptions in `docs/phase0-gold-foundation.md` §5/§10.

The authoritative contract, formulas, decision table, endpoint inventory and residuals are in `docs/phase0-gold-foundation.md`. This file is the short operational handoff.

---

## 1. Final evidence

| Check | Result |
|---|---|
| `pytest tests/gold_desk` | **364 passed, 1 skipped** (83.35s) |
| Phase 0 focused (engine, provenance, integration, TGJU units, mount) | **41 passed** (38.80s) |
| Mount guard | **2 passed** — 33 frontend-critical gold paths mounted, no duplicate `(path, methods)` |
| `cd frontend && npx vitest run` | **566 passed, 53 files** (74.22s) |
| `cd frontend && npx tsc --noEmit` | **exit 0** |
| Direct-router `GET /gold/snapshot` | **200**, real DB row, five fields, correct `DELAYED` on 8-day-old data |

Observed snapshot (2026-10-26): `source=brsapi`, `quality=DELAYED`, `asOf=2026-10-18T20:41:04Z`, `age_seconds=638848`, `unit=toman`; gold 18k `value=26,396,987.8`, coin `value=257,704,041.7`; legacy `quality_flag=clean` is ignored by the UI.

Production `GET /api/v1/gold/snapshot` with a real user token was **not** run (no credentials; earlier `/api/v1/gold/health` was 503 `redis_or_db`). Mount + payload are proven at the assembled-router level.

---

## 2. What was delivered (A–F)

- **A. Engine:** canonical `pricer.py`; duplicate `antigravity/engine.py` retained as a delegate, double-purity bug fixed (`259,834,800.09` fixture now equals canonical); caller-supplied provenance metadata; exact tests for 18k, coins, weights/purity/mint, Rial rounding.
- **B. Endpoints:** 107 gold-related routes inventoried; 33 frontend-critical paths pinned by `tests/gold_desk/test_phase0_mount.py`; snapshot carries `value/unit/asOf/source/quality`; mount failure now logs a full traceback. `/api/v1/gold/*` is the single frontend prefix; `/golddesk/*` is a separate SaaS surface, not an alias.
- **C. Trust labels:** `DataTrustBadge` on summary cards, coin rows, funds reference, antigravity; `LIVE|DELAYED|SAMPLE|EDUCATIONAL`; SAMPLE solid rose vs LIVE green; unknown → DELAYED; source + last update shown; no fabricated `2650/85000`.
- **D. Disclaimer:** fixed text in gold header, summary, chat footer, antigravity footer; visible, `role="note"`, no order/profit language.
- **E. Tests:** all minimum tests green (engine fixed-input, snapshot 200 integration, UI disclaimer/badge, TGJU/mixed/no-data fail-closed). No formula change was reverted because nothing failed.
- **F. Docs:** `docs/phase0-gold-foundation.md` updated with formulas, assumptions, conflict table, endpoint status, LIVE/SAMPLE rules, commands, residuals.

---

## 3. Residual / external items

1. **Production auth smoke:** run `GET /api/v1/gold/snapshot` with a real token; confirm 200 + five fields.
2. **Formula literal:** assignment says `×0.75`; canonical code uses `750/999.9` **once** (`×0.750075`, ~0.01% difference). Owner decision; no silent change.
3. **Mint fee naming:** canonical table says `mint_fee_irr` but values are Toman; code treats as Toman (15k–80k) with a scale assert.
4. **Fund provenance:** `FundBlock` lacks per-row `source/asOf`; the funds table shows a badge labelled «مرجع دادهٔ صندوق». Extending the schema is a follow-up.
5. **IME spread:** labelled as an analytical ratio, not a price with independent provenance; endpoint derives both sides from one 18k price (accuracy topic outside Phase 0).
6. **DXY:** absent in current DB → «—»; freshness includes DXY when present; no synthetic value.
7. **Legacy `quality_flag`:** kept in payload, never displayed as quality.
8. **Duplicate engine:** retained for backward compatibility; deletion needs a consumer audit.

---

## 4. Next actions (in order)

1. Owner reviews flagged assumptions and (if desired) provisions a token for the production smoke.
2. If anything is changed, re-run both full suites and update the evidence table.
3. **Do not start Phase 1** until the owner explicitly opens the gate. No Score UI, full Rahavard-style table, or treemap was added.
4. **PR guard:** reject any order/cart/checkout/wallet/custody/broker-execution route or profit promise. Keep `InkGist`, `SummarySection.tsx.bak`, `Phase2Overview.tsx`, `docs/phase1-*`, `docs/phase2-*`, `docs/phase3-*`, `docs/data-sources-phase1/2/3.md`, `docs/contracts/*`, and Phase 1 fixtures out of the Phase 0 merge.
5. **Unsafe docs:** `docs/data-sources-phase0.md` still conflicts with the approved contract (cutoff→SAMPLE is wrong; missing→NO_DATA). Do not implement against it. Use `docs/phase0-gold-foundation.md` as the only authority.
