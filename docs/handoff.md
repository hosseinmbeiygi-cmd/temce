# Handoff — Phase 0 DONE; Phase 1 + Phase 2 IMPLEMENTED; Phase 3 NOT DONE

**Date:** 2026-10-26 (Phase 0 final evidence; Phase 1 and Phase 2 evidence appended below; local +03:30)
**Phase 0:** **DONE** — tasks A–F implemented and tested.
**Phase 1:** **IMPLEMENTED** — `GET /gold/terminal`, `POST /gold/what-if`, UI `/gold/terminal`; no OMS. Contract and limitations: `docs/phase1-gold-parity.md`.
**Phase 2:** **IMPLEMENTED** — `GET /gold/tehran-board`, `/gold/platforms`, `/gold/returns-matrix`, `/gold/fund-map`; UI `/gold/coverage`. Price comparison only, no trading surface. Contract, sources and limitations: `docs/phase2-market-coverage.md`.
**Phase 3:** **NOT DONE** — documentation/copy only; no `scoreVersion`, gate, Brief, news regime, silver surface, or Phase 3 tests. See `docs/phase3-decision-assistant.md`.
**Phase 4:** **NOT DONE / NOT STARTED.**
**Merge recommendation:** Phase 0 + Phase 1 + Phase 2 code/tests are mergeable on the evidence below; **Phase 3 must not be merged or accepted as DONE**. Production-authenticated snapshot smoke is the only external check not executed. Owner should sign the flagged assumptions in `docs/phase0-gold-foundation.md` §5/§10.

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

### Phase 1 evidence (same date)

| Check | Result |
|---|---|
| `pytest tests/gold_desk tests/unit/api/test_golddesk_http.py` | **415 passed, 1 skipped** (107.53 s) |
| `pytest tests/gold_desk/test_phase1_terminal.py` | **41 passed** |
| `cd frontend && npx vitest run` | **574 passed, 54 files** (78.89 s) |
| `cd frontend && npx tsc --noEmit` | **exit 0** |
| Real dev-DB `build_terminal` smoke | 8 physical rows, **38 gold funds**, 2 certificates; all `DELAYED` (source 8 days old); no null rendered as zero |

Phase 1 routes are `GET /api/v1/gold/terminal` and `POST /api/v1/gold/what-if` (UI tab «میز داده»). Capabilities are `orders=false`, `wallet=false`, `delivery=false`, `preview_only=true`. Certificate intrinsic and fund composition/intrinsic/real bubble remain `—` with explicit Persian data gaps — see `docs/phase1-gold-parity.md`.

### Phase 2 evidence (same date)

| Check | Result |
|---|---|
| `pytest tests/gold_desk tests/unit/api/test_golddesk_http.py` | **444 passed, 1 skipped** (235.90 s) |
| `pytest tests/gold_desk/test_phase2_market_coverage.py` | **29 passed** |
| `cd frontend && npx vitest run` | **583 passed, 55 files** (127.40 s) |
| `cd frontend && npx tsc --noEmit` | **exit 0** |
| Dev-DB returns smoke (2026-10-26) | coin 1m **+12.66%**, USD/IRR **+12.33%**, XAU/USD **+9.01% in IRR base**, BTC **+16.63% in IRR base**; gold-fund/TEDPIX 6m+ `no_data` (67 observations only); CPI all `no_data`; JSON `allow_nan=False` OK |
| Dev-DB coverage smoke | Tehran **11 rows / 0 priced** (`not_connected`), platforms **0** (`not_connected`), fund map **38 cells / 112.61 T Rial**, top عیار 45.14% / طلا 9.19% / جام طلا 5.34% / سایر 15.19% |

Two data-integrity bugs found by the dev-DB smoke were fixed before this evidence:

1. `brsapi_gold_currency_pro_daily_history` stores FX closes in **Rial**, but the loader applied the Toman×10 conversion, fabricating a ~−90% "1-month" USD return. `_load_pro_history` now takes an explicit unit (`rial` for FX, `usd` for XAU/USD).
2. History loaders used `ORDER BY id DESC LIMIT n`; backfilled 2010 rows carry high ids, so a "3-month" coin return came out at **+26,996%**. Loaders now read a 500-day calendar window and drop rows outside it, and `_period_return` reports `no_data` when the actual span exceeds the nominal period by more than 30 days.

Phase 2 UI tab is «پوشش بازار»; all four sections fail independently, keep their full column sets when data is missing, and carry `orders/wallet/delivery/checkout/payment=false`, `preview_only=true`.

---

## 1b. Phase 3 acceptance — NOT DONE (2026-10-26)

**Verdict: NOT DONE.** The Persian copy is finalized, but there is no Phase 3 implementation to accept. `scoreVersion` and `actionLanguageAllowed` occur only in `docs/`; there are zero occurrences in `src/`, `apps/`, `frontend/src/`, or `tests/`.

| Acceptance item | Status | Owner |
|---|---|---|
| Score with documented components/weights | NOT DONE — existing scorer is Phase 0 (`bubble/nav/tsetmc/technical/parity/fund_flow`) | Assistant 1 |
| `scoreVersion` present | NOT DONE — zero code occurrences | Assistant 1 |
| `gate=red` → `actionLanguageAllowed=false` in API + UI | NOT DONE — no gate; ungated BUY/SELL text in `antigravity`, `coins`, `physical`, `etf` | Assistant 1 + 2 |
| Separate `short`/`medium` horizons | NOT DONE — no Brief endpoint or schema | Assistant 1 |
| Brief with no fabricated price | NOT DONE — no Brief; copy contract is ready in `docs/phase3-vocabulary-fa.md` | Assistant 1 + 2 |
| Silver at least read-only | NOT DONE — only fund classification and `SilverBar` derivative | Assistant 1 + 2 |
| One read-only derivative, no order | NOT DONE — options analytics exist but not this contract | Assistant 1 + 2 |
| Fixed news-regime labels | NOT DONE — no tagging code; Persian labels finalized in copy | Assistant 1 |
| Phase 0–2 regression (disclaimer, bubble, NAV, no buy CTA) | DONE — 111 backend + 40 frontend tests passed | — |
| No order route in current gold diff | DONE for the diff — pre-existing `auto_trade.py` live mode and Tabdeal `/orders` are outside it and must be reviewed before Phase 4 | Owner |

**Who is blocked**

- **Assistant 1 (backend):** blocked on writing the Phase 3 engine/API — `scoreVersion`, gate thresholds, Brief for two horizons, news regime, silver/derivative read-only schemas, and the five missing tests.
- **Assistant 2 (frontend):** blocked until the API exists; then gate-red suppression, Brief panel, read-only silver/derivative surfaces, and the disclaimer panel.
- **Owner:** must provide a documented source for «میلی» before any comparison is published, and sign off the proposed weights/thresholds in `docs/phase3-decision-assistant.md` §2–§3.

**Red tests:** none are failing. Five required Phase 3 tests are **missing, not red**: extreme-bubble gate, stale `asOf` → `data_stale`, gate-red UI without buy language, weight-change guard, and what-if/fund-bubble regression (the last is covered by the green Phase 1/2 suites).

**Phase 3 DONE?** No. **Phase 4?** Not done and not started.

Copy docs rewritten from the corrupted mixed-language versions: `docs/phase3-decision-assistant.md`, `docs/phase3-vocabulary-fa.md`, `docs/phase3-disclaimer-fa.md`.

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
3. **Phase 1 and Phase 2 are implemented** and must stay preview/comparison-only. **Phase 3 is NOT DONE** (see §1b) and must not be accepted or merged as done. Phase 4 is not started.
4. **PR guard:** reject any order/cart/checkout/wallet/custody/broker-execution route or profit promise. Phase 1 files are listed in the Phase 1 evidence section and `docs/phase1-gold-parity.md`; Phase 2 files are `src/gold_desk/phase2.py`, `src/gold_desk/phase2_schemas.py`, `frontend/src/types/phase2.ts`, `frontend/src/app/gold/coverage/**`, `frontend/src/__tests__/GoldMarketCoverage.test.tsx`, `tests/gold_desk/test_phase2_market_coverage.py`, and `docs/phase2-market-coverage.md`. Keep other untracked files (`InkGist`, `SummarySection.tsx.bak`, `Phase2Overview.tsx`, other assistants' `docs/phase1-*-api.md`, `docs/phase3-*`, `docs/data-sources-phase1/2/3.md`, `docs/contracts/*`, `tests/fixtures/phase1-*.json`) out unless reviewed.
5. **Unsafe docs:** `docs/data-sources-phase0.md` still conflicts with the approved contract (cutoff→SAMPLE is wrong; missing→NO_DATA). Do not implement against it. Use `docs/phase0-gold-foundation.md` and `docs/phase1-gold-parity.md` as the authorities.

---

## Assistant 4 — Market Data & Integrations (لایه منبع) — ۲۰۲۶-۱۰-۲۶

- انجام‌شده: رابط یکسان منبع (`services/data/adapters/`): BrsApiAdapter، SilverAdapter (نقره داخل+بین‌المللی)، DerivativeAdapter (مشتقه read-only: قیمت/سررسید/فاصله از اسپات، guarded)، NewsAdapter (رژیم خبری، برچسب‌های ثابت، یادآوری غیرقیمتی)، FreshnessAdapter (نشان تازگی ageSeconds/freshness/staleFlag برای گیت `data_stale` دستیار ۱); فیکست‌های آفلاین `tests/fixtures/phase3-{silver,derivative,news,stale,secret}.json`؛ ۱۴ تست آفلاین در `tests/gold_desk/test_phase3_adapters.py` (بدون شبکه، سبز); `ruff check` تمیز؛ `docs/data-sources.md` ثبت شد.
- بلوکر: منبعی قطع نیست؛ فاز ۴ قبل از DONE شدن فاز ۳ (دستیار ۱) و دستور صریح باز نمی‌شود.
- LIVE به دستیار ۱: فقط فیکست/آفلاین در CI؛ عدد LIVE واقعی فقط از طریق قرارداد/API دستیار ۱ پس از اتصال توسط آن طرف.
