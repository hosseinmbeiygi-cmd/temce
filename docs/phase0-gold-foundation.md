# Phase 0 — Gold Foundation: Contract, Acceptance & Evidence

**Status: DONE (code + tests) — 2026-10-26.**
**Phase 1: IMPLEMENTED separately — see `docs/phase1-gold-parity.md`.**
**Phase 3: NOT DONE (docs/copy only) — see `docs/phase3-decision-assistant.md`.**
Scope of this document: Phase 0, tasks A–F only. No Phase 1 feature (full Rahavard-style table, Score UI, treemap) and no order/wallet/custody surface was added.

Final evidence (2026-10-26, repo root, Windows venv):

| Check | Result |
|---|---|
| `pytest tests/gold_desk` | **364 passed, 1 skipped** in 83.35s |
| Phase 0 focused tests (5 files) | **41 passed** in 38.80s |
| Mount guard (`test_phase0_mount.py`) | **2 passed** in 23.37s |
| Frontend `npx vitest run` | **566 passed, 53 files** (final run below) |
| Frontend `npx tsc --noEmit` | **exit 0** |
| Direct-router `GET /gold/snapshot` | **200**, five contract fields present, `quality=DELAYED` on an 8-day-old row (correct) |

Remaining **external** item: production-authenticated `GET /api/v1/gold/snapshot` with a real user token was not executed (no credentials; `/api/v1/gold/health` returned 503 `redis_or_db` in the earlier probe). Mount and payload are proven at the assembled-router level; this is a smoke-credential gap, not a code gap.

---

## 1. Final data contract

Every asset block (`gold.*`, `coins.*`) contains all five contract fields:

| Field | Rule |
|---|---|
| `value` | Fair value (`fair_value`) in Toman, rounded to 0.1 Toman (= 1 Rial) with `Decimal` `ROUND_HALF_UP`. Never a placeholder. |
| `unit` | `"toman"` for all snapshot assets. `"rial"`/`"ounce"` exist in the engine type but are not emitted for asset blocks; ounce is only a reference unit. |
| `asOf` | **Source/data time.** Per asset: the asset row's `fetched_at`; if absent, the reference-set `asOf`; it is never the response build time in the happy path. Missing timestamps are marked `DELAYED` rather than borrowing freshness. |
| `source` | Exactly one of `"brsapi" \| "tgju" \| "cache"`. **`"mixed"` is forbidden** and rejected by Pydantic/schema tests. The whole snapshot comes from one complete source. |
| `quality` | `"LIVE" \| "DELAYED" \| "SAMPLE" \| "EDUCATIONAL"`. **`"fallback"` is forbidden.** Only proven-fresh BrsApi data may be `LIVE`. |

Legacy `quality_flag` (`clean|fallback`) still exists at snapshot level for backward compatibility and is **never** rendered as `quality`; the UI reads per-asset/per-reference provenance only.

### 1.1 Quality semantics — fail-closed

| Label | Rule in code | UI |
|---|---|---|
| `LIVE` | `source="brsapi"` **and** own row timestamp present **and** `0 ≤ age ≤ PRICE_LIVE_TTL_SECONDS=300s` | green badge + source + last update |
| `DELAYED` | TGJU (delayed source, no source timestamp), missing timestamp, future timestamp (clock skew), or age > 300s | amber badge |
| `SAMPLE` | Synthetic/demo values; never emitted by the snapshot backend. If it appears, it must be visually unmistakable (solid rose) and never feed decisions. | solid rose badge + alert |
| `EDUCATIONAL` | Static teaching values; never emitted by the snapshot backend. | solid violet badge |
| no data | No numeric block. UI shows «داده موجود نیست» / «—»; never a fabricated price. | neutral |

Frontend `normalizeQuality()` maps **any unknown value to `DELAYED`** (fail-closed), so a malformed backend value can never be displayed as `LIVE`.

Reference-set freshness uses the **oldest** timestamp among XAU/USD/AED, plus DXY when DXY is present. If any displayed reference has no timestamp, the reference `asOf` is `null` and quality is `DELAYED`. TGJU fallback uses fetch time as its stamp but is still always `DELAYED`.

### 1.2 Single-source rule

`_read_references()` accepts only a **complete** set of `XAUUSD`, `USD`, `AED` from one source:

1. Complete BrsApi set → `source="brsapi"`, all assets from the same BrsApi book.
2. Otherwise, complete TGJU set → `source="tgju"`, all assets from the same TGJU book (TGJU gold/coin slugs converted per-slug; `_rl` currency slugs are Rial → ×0.1 to Toman).
3. Both incomplete → `RuntimeError` → 503. No mixed snapshot is ever produced.

Latest row per symbol is chosen by `(fetched_at, time_unix, id)`, not by list order; non-positive prices are ignored.

### 1.3 Observed 200 payload (direct router, real DB)

`GET /gold/snapshot` on 2026-10-26 (DB data is 8 days old, so `DELAYED` is the correct label):

```
status 200, success=true, snapshot_at=2026-10-26T06:08:33.057762Z
refs: source=brsapi, quality=DELAYED, unit=toman,
      asOf=2026-10-18T20:41:04.265000Z, age_seconds=638848.79,
      xau_usd=4165.175, usd_irt=262800.0, aed_irt=71801.0, dxy_index=null
gold.gold_18k: value=26396987.8, unit=toman, source=brsapi, quality=DELAYED,
               asOf=2026-10-18T20:41:03.358000Z,
               market_price=25937200.0, fair_value=26396987.8, bubble_pct=-1.7418
coins.coin_emami: value=257704041.7, unit=toman, source=brsapi, quality=DELAYED,
                  asOf=2026-10-18T20:41:03.358000Z,
                  market_price=264190000.0, fair_value=257704041.7, bubble_pct=2.5168
legacy quality_flag=clean (ignored by the UI)
```

The payload proves: source-time `asOf` (not `snapshot_at`), per-asset timestamps, fail-closed `DELAYED`, Toman unit, Rial-precision rounding, and all five fields on gold and coins.

---

## 2. Fixed disclaimer (D)

Canonical text, rendered in the gold layout header, market summary, chat footer, and antigravity page:

> این میز فقط ابزار تحلیلی، تصمیم‌یاری و آموزش است. سفارش اجرا نمی‌کند، دارایی نگهداری نمی‌کند، و توصیه قطعی خرید/فروش نیست. مسئولیت تصمیم با کاربر است.

- Meaning matches the assignment (analysis/education only; no execution; no custody; no definitive buy/sell advice; responsibility is the user's). Wording remains legally editable by the owner.
- Includes «ابزار تحلیلی» so the pre-existing `GoldNoData.test.tsx` regression test is green again.
- Always visible (not hover/expand), `role="note"`, `aria-label="سلب مسئولیت"`.
- No buy/sell CTA, order button, profit promise, or execution surface was added. BUY/SELL labels that already existed remain analysis-only and require a quality badge + disclaimer.

---

## 3. A–F checklist

| Task | Status | Evidence |
|---|---|---|
| **A. Unified engine + conflict report** | **DONE** | Canonical `pricer.py`; duplicate `antigravity/engine.py` retained as a thin delegate (not deleted), purity applied once; fixed fixture tests. §4–§5. |
| **B. Endpoints extracted, mounted, contract fields** | **DONE (mount + snapshot response)** | 107 gold-related routes; 33 frontend-critical paths pinned by `test_phase0_mount.py`; snapshot 200 carries `value/unit/asOf/source/quality`; no duplicate `(path, methods)`. Other routes are mount-verified, not individually response-smoked. §6. |
| **C. UI trust labels (source + last update + badge)** | **DONE** | `DataTrustBadge` on every summary card, every coin row, funds-table reference badge, antigravity reference/EDUCATIONAL badges; SAMPLE solid rose vs LIVE green; unknown → DELAYED; 0s age → «همین حالا». Tests: `GoldTrustLabels.test.tsx`. |
| **D. Fixed disclaimer in header + assistant footer** | **DONE** | `GoldDisclaimer` in `layout.tsx`, `SummarySection`, chat page, antigravity footer; test asserts exact text. |
| **E. Minimum tests before merge** | **DONE** | Engine fixed-input tests, snapshot 200 integration, UI disclaimer/badge tests, fail-closed TGJU/mixed/no-data tests. All green; no formula change was reverted. §7. |
| **F. This document** | **DONE** | Formula/weights/purity assumptions, conflict/decision table, endpoint/mount status, LIVE vs SAMPLE detection, test commands, residuals. |

---

## 4. Conflict / decision table (pre-fix → resolution)

| # | Conflict found | Resolution | Test evidence |
|---|---|---|---|
| 1 | `antigravity.engine.calculate_pure_gold_18k` applied purity **twice** (`750/999.9 × 0.75`) → 0.75× canonical (`194,876,100.07` vs `259,834,800.09` for `XAU=3998, USD=2,695,000`). | Delegates to `pricer.fair_gold_18k`; one purity application. Function kept (not deleted) as a deprecated delegate. | `test_phase0_engine_core.py` |
| 2 | Duplicate engine hard-coded `quality="LIVE"`, `source="brsapi"`, `asOf=now`. | `calculate_snapshot_fields` requires caller-supplied `source`/`quality`/`as_of`/`unit`; defaults fail closed (`DELAYED`); invalid `mixed`/`fallback`/`ounce` raise. | `test_snapshot_fields_metadata_is_caller_supplied` |
| 3 | `snapshot_service` emitted `quality="fallback"` and `source="mixed"`, both rejected by schema. | `_quality_for()` returns only `LIVE`/`DELAYED`; single complete source or 503. | provenance tests |
| 4 | Snapshot `asOf` was response build time. | `asOf` = source `fetched_at`; reference set uses the oldest displayed reference (including DXY when present); missing stamp → `DELAYED`/`null`. | `test_fresh_brsapi_snapshot_is_live_and_uses_source_time`, DXY test |
| 5 | TGJU fallback divided every price > 2,000,000 by 10, corrupting gold/coin values. | Per-slug unit table: only `_rl` currency slugs ×0.1; gold/coin ×1.0; XAU in USD. | `test_phase0_secondary_source.py` |
| 6 | Antigravity coin math used purity `0.915` and different weight/mint constants. | Coin bubble uses `8.133 g`, `900/999.9`, `80,000 Toman` mint, `31.1034768 g/oz`; returns `null` without market refs. | antigravity page + tests |
| 7 | 18k melted was priced per gram while the market quotes per Mesghal → +312% bubble. | `fair_value(IR_GOLD_MELTED)` = `4.6083 × 18k_per_gram`. | pricer tests |
| 8 | UI mapped snapshot-level `quality_flag="clean"` to SAMPLE; antigravity fabricated `2650`/`85000`. | Per-asset quality badges; unknown→DELAYED; fabricated fallbacks removed; NO_DATA panel. | `GoldTrustLabels.test.tsx`, `GoldNoData.test.tsx` |
| 9 | Disclaimer copy corrupted («آب-originated», «美国», «با_User_است»). | Canonical fixed text; corrupted labels fixed («مثقال طلای آب‌شده», «شاخص دلار (DXY)»). | frontend suite |

---

## 5. Formulas, weights, purity, rounding

```
base_24k_per_gram = XAU_USD × USD_IRT / 31.1034768          # Toman per gram, 24k
fair_18k          = base_24k_per_gram × (750 / 999.9)       # purity applied ONCE
fair_24k          = base_24k_per_gram
fair_melted       = 4.6083 × fair_18k                       # Mesghal, not per gram
fair_coin         = weight × (900 / 999.9) × base_24k_per_gram + mint_toman
bubble_abs        = market − fair
bubble_pct        = (market − fair) / fair × 100
implied_usd       = market × 31.1034768 / (pure_weight_g × XAU_USD)
```

- `XAU_USD` is USD/oz; `USD_IRT` and all asset values are **Toman**.
- `IR_COIN_EMAMI`/`IR_COIN_BAHAR`: 8.133 g, purity 900, mint 80,000 Toman. Half 4.066 g / 50,000; quarter 2.033 g / 35,000; 1g & gerami 1.010 g / 15,000.
- Coin purity is `900/999.9` (relative to 24k = 999.9), not `0.9/0.915` heuristics.
- Money rounding: `Decimal` `ROUND_HALF_UP`; Toman quantum `0.1` (= 1 Rial). `implied_usd` 2 decimals; `bubble_pct` full precision.
- **Assumption (flagged):** the assignment writes 18k as `×0.75`; the canonical engine uses `750/999.9 = 0.750075` (one application). The difference is ~0.01%; changing the canonical formula would change every fair value and needs owner sign-off. This is documented, not silently changed.
- **Assumption (flagged):** `services/gold/constants.py` names mint fees `mint_fee_irr`, but the values (15k–80k) are only plausible as **Toman**. Code treats them as Toman, asserted to a 0–5,000,000 Toman range.
- The engine is scale-agnostic: if `USD_IRT` is Rial, output is Rial. The snapshot contract fixes Toman because BrsApi labels gold/currency in Toman.

---

## 6. Endpoints — inventory and mount status

- Assembled `Router().setup()` exposes gold paths as `/gold/...`; `apps/api/app.py:1118` mounts that router under `settings.api_prefix`, so the public full path is **`/api/v1/gold/...`**.
- Inventory: **107** routes with "gold" in the path → **102** `/gold/*` (76 core/personal + 26 analytics), **3** `/golddesk/*`, **2** `/brsapi/*gold*`.
- `tests/gold_desk/test_phase0_mount.py` pins **33 frontend-critical paths** (`/gold/snapshot`, `/live-prices`, `/futures/*`, `/kill-switch`, `/portfolio/*`, `/alerts/*`, `/chat`, `/backtest*`, `/analytics/*`, `/ws`, …) and asserts no duplicate `(path, methods)` registrations under `/gold/`.
- The personal GoldDesk include is wrapped in `try/except` to keep startup non-fatal; it now logs the full traceback via `logger.exception(...)` instead of a one-line warning, so a future 404 storm is traceable. The mount test prevents silent regression.
- Sample status:
  - `GET /api/v1/gold/snapshot` — 200 at direct-router level with all five fields (§1.3); production auth smoke not run.
  - `GET /api/v1/gold/health` — earlier 503 `redis_or_db`; `assistant-rules` 200.
  - All 33 pinned routes — **mounted**; only the snapshot response was smoke-probed. Others are mount-verified, not response-verified.
- Alias policy: no alias was added. The frontend already calls `/api/v1/gold/*`; `/golddesk/*` is a **separate SaaS surface** with scoped tokens and must not be treated as an alias or as the Phase 0 snapshot.
- Every price-response path that uses `AssetBlock`/`ReferenceBlock` carries the five fields; non-price routes (health, rules) are not price responses.

---

## 7. Tests and reproducible commands

All commands from repo root with the project venv; frontend commands from `frontend/`.

```bash
# Full GoldDesk backend suite (default testpaths)
./venv/Scripts/python.exe -m pytest tests/gold_desk -q -p no:cacheprovider
# → 364 passed, 1 skipped in 83.35s

# Phase 0 focused: engine, provenance, integration, TGJU units, mount
./venv/Scripts/python.exe -m pytest \
  tests/gold_desk/test_phase0_engine_core.py \
  tests/gold_desk/test_phase0_snapshot_provenance.py \
  tests/gold_desk/test_phase0_snapshot_integration.py \
  tests/gold_desk/test_phase0_secondary_source.py \
  tests/gold_desk/test_phase0_mount.py -q -p no:cacheprovider
# → 41 passed in 38.80s

# Frontend UI + full suite
cd frontend && npx vitest run
# → 566 passed (53 files)   [final run recorded below]

cd frontend && npx tsc --noEmit
# → exit 0
```

What the tests pin:

- Engine: exact `18k`/coin values for `XAU=3998, USD=2,695,000`; duplicate == canonical; coin weights/purity/mint; Rial rounding; invalid metadata rejected.
- Provenance: latest row wins; non-positive rows ignored; complete BrsApi vs complete TGJU; partial sources raise instead of mixing; `LIVE` only inside 300s; TGJU always `DELAYED`; missing/future timestamp `DELAYED`; DXY freshness included; asset without its own timestamp `DELAYED`.
- Integration: direct-router snapshot 200 with five fields; legacy `quality_flag` does not become `quality`.
- UI: fixed disclaimer verbatim; LIVE badge + `منبع: brsapi` + last-update time; SAMPLE solid rose + alert; `clean` never rendered SAMPLE; null age shows «زمان: نامشخص»; missing snapshot shows no fabricated price; coin rows and funds reference carry badges.

---

## 8. LIVE vs SAMPLE detection — quick reference

1. `quality_flag` is **not** a quality label. Ignore it for display.
2. Read per-asset `quality`; if missing/unknown → `DELAYED`.
3. `LIVE` requires BrsApi **and** a source timestamp within 300s. Any TGJU value is `DELAYED` even if fetched this second.
4. `SAMPLE`/`EDUCATIONAL` must never be produced from real fetch paths; if they appear, they must be visually unmistakable and never drive score/signals.
5. No data → show NO_DATA / «—»; never `2650`, `85000`, `0`, or a stale value labelled `LIVE`.

---

## 9. PR / merge guard

- This Phase 0 change adds **no** order route, cart, checkout, wallet, custody, delivery, broker execution, or profit promise.
- Any PR adding such a surface must be rejected citing this section. Analysis-only BUY/SELL labels are acceptable only with disclaimer + quality badge, and must never become executable.
- Do **not** include in the Phase 0 merge: `InkGist`, `SummarySection.tsx.bak`, `Phase2Overview.tsx`, `docs/phase1-*`, `docs/phase2-*`, `docs/phase3-*`, `docs/data-sources-phase1/2/3.md`, `docs/contracts/*`, and Phase 1 fixtures.
- **Merge recommendation:** Phase 0 code/tests are mergeable on the evidence above. Production-authenticated snapshot smoke remains the only external check not executed; owner sign-off on the flagged assumptions (§5, §10) is recommended before operational rollout.

---

## 10. Residual items / owner decisions

1. **Production auth smoke** — token not available; run `GET /api/v1/gold/snapshot` with a real user token and confirm 200. Router-level 200 is already proven.
2. **Formula literal** — assignment says `×0.75`; code uses `750/999.9` once (`×0.750075`). Keep canonical or switch? Owner decision; changing it changes all fair values by ~0.01%.
3. **Unit table naming** — mint fees are named `mint_fee_irr` but treated as Toman; rename or confirm.
4. **Fund provenance** — `FundBlock` has no per-row `source`/`asOf`; the funds table shows a reference badge explicitly labelled «مرجع دادهٔ صندوق». If per-row provenance is required, extend the schema with tests.
5. **IME spread** — the section displays an analytical ratio computed from the snapshot; it is labelled as such and is not a price with independent provenance. The endpoint still derives both sides from one 18k price, which is an accuracy topic outside Phase 0's trust-label scope.
6. **DXY** — currently `null` in the DB; UI shows «—». When present, it participates in reference freshness. No synthetic DXY is fabricated.
7. **Duplicate engine** — retained as a delegate for backward compatibility; deleting it is a follow-up after consumer audit (not done in Phase 0 by design).
8. **Legacy `quality_flag`** — kept in the payload for compatibility; UI ignores it. Removing it is a later contract cleanup.

---

## 11. Phase 1 gate

**Phase 0 is DONE for code/tests. Phase 1 has NOT started and must not start under this document.**

The owner's standing instruction is explicit: finish the prior phase first. This document records Phase 0 completion only; it does not authorize a Score UI, a full Rahavard-style table, or a treemap. Phase 3 is **NOT DONE** and must not be accepted as complete; see `docs/phase3-decision-assistant.md`.

If/when the owner opens Phase 1, re-run the full backend + frontend suites, record fresh hashes, confirm the production auth smoke, and only then update `docs/handoff.md`.

---

## 12. Evidence hashes (SHA-256, first 12 hex)

| File | Hash |
|---|---|
| `src/gold_desk/pricer.py` | `e14c908d0bdc` |
| `src/gold_desk/snapshot_service.py` | `e5868bb141d3` |
| `src/gold_desk/schemas.py` | `46f5cf4cd375` |
| `src/gold_desk/secondary_source.py` | `0b0f77e24e7d` |
| `src/gold_desk/constants.py` | `e55e99848ed3` |
| `src/gold_desk/antigravity/engine.py` | `f21fa48c335e` |
| `apps/api/router.py` | `299ab6b0b8c4` |
| `tests/gold_desk/test_phase0_engine_core.py` | `9657ca33cf56` |
| `tests/gold_desk/test_phase0_snapshot_provenance.py` | `f9221fb1aa6b` |
| `tests/gold_desk/test_phase0_snapshot_integration.py` | `51b58e30b25c` |
| `tests/gold_desk/test_phase0_secondary_source.py` | `ece0c90fb764` |
| `tests/gold_desk/test_phase0_mount.py` | `60779ff8225a` |
| `frontend/src/types/gold.ts` | `e4d6dc00cae4` |
| `frontend/src/components/gold/DataTrustBadge.tsx` | `fc74e78ca8c1` |
| `frontend/src/components/gold/GoldDisclaimer.tsx` | `a62f3e25ff21` |
| `frontend/src/app/gold/components/SummarySection.tsx` | `2ba46de59983` |
| `frontend/src/app/gold/components/CoinBubbleTable.tsx` | `e7d37191e4ae` |
| `frontend/src/app/gold/components/FundsPnavTable.tsx` | `2ffb3c1e9bda` |
| `frontend/src/app/gold/layout.tsx` | `d34ba5e7bbf6` |
| `frontend/src/app/gold/chat/page.tsx` | `ab51158f530f` |
| `frontend/src/app/gold/antigravity/page.tsx` | `bfae74e42851` |
| `frontend/src/__tests__/GoldTrustLabels.test.tsx` | `a77551f60120` |

Hashes are evidence boundaries for the runs above; any later edit invalidates them and requires a re-run.
