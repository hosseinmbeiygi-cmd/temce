# Alert Engine — Audit, Coverage and Implementation Report

Date: 2026-11-15/16 · Scope: connect the Alerts section to an evidence-based analysis and notification workflow.
Everything below was verified against code, the local PostgreSQL database and executed tests — not against documentation.

**Boundary kept throughout:** analysis, recommendations and notifications only. No order is placed, changed or cancelled; no broker connection was added; every output is labelled *paper*.

---

## 1. Repository audit (state before this work)

Classification: **A** operational · **B** implemented but incomplete / under-supplied · **C** missing · **D** stale data, hidden failure, fabricated values or unsafe default · **E** needs integration/correction.

| Area | Finding | Evidence | Class |
|---|---|---|---|
| Alerts UI (`frontend/src/app/alerts/page.tsx`) | Only threshold alerts (price/volume/RSI/SMA). No analysis, no instrument page, no portfolio, no sound. | page source | B |
| Threshold alerts API/job (`/alerts`, `EvaluateAlertsJob`) | Works, owner-scoped. | `alert_history` 7,577 rows | A |
| …delivery semantics | Channel `console`/`sound`/`email` only write a log line yet set `delivered=true`. One alert (no cooldown) fired **7,568 times**. Two legacy alerts have `user_id NULL`, one with a mojibake symbol. | `services/alert_service.py:_deliver_notification`, `alerts` table | D |
| "Alert hub" (`app/alert_hub`, `symbol_alerts` router) | Unmounted by decision API-05. Its four modules return **hard-coded placeholder values** (`winRate 55`, `technicalHealthScore 75`, `confidence 0.5`, price 0) and a majority-vote verdict. Tables empty. | `app/alert_hub/services/*.py` | D — left untouched and unmounted; superseded |
| Instrument classification (`services/pre_buy_instrument.py`) | Fact-based, no name matching. Misses stocks outside `instruments` (only 499 rows) and all option contracts (`options` table empty). Probes take 2–5 s each. | live profiling | B/E — reused, extended, cached 24 h |
| Market snapshots (`brsapi_symbol_snapshots`) | 5-level book, real/legal flow, daily limits (`tmin`/`tmax`). Fresh to 2026-11-14 18:08 UTC. | DB | A |
| Price limits helper (`services/queue_analysis.get_price_limits`) | Assumes a fixed ±5 % (3 % base market). Moj's real band on 14 Nov was ±6 %. | code vs `raw_json` | D — not used; real limits are |
| Daily history (`brsapi_historical_daily`) | `gregorian_date` is the **load date, not the trade date** (Jalali 1405-06-23 stored as 2026-11-10). | DB rows | D — engine orders by the Jalali trade date |
| Index values (`brsapi_index_values`) | `name` is empty on every row; `index_change_pct` is 0.0 while the equal-weight change is −3,544. | DB rows | D — only the equal-weight series is used, as corroboration |
| Official NAV (`brsapi_nav_records`) | Last NAV for **every** fund is 1405-07-13 (2026-10-05): `/Tsetmc/Nav.php` sync has failed since (1,100 errors, "daily budget exhausted"). `fund_nav_results` rows are `BLOCKED` with null values. | `brsapi_sync_log` | D (stale) |
| Fund holdings / unit classes | `fund_holdings`, `fund_portfolio_reports`, `fund_unit_classes`, `fund_class_allocations` are **empty**. The NAV/class-allocation engines exist but have no input. | row counts | B — estimated NAV and leverage are blocked |
| Options (`brsapi_option_snapshots`) | 1.28 M rows, linked by `underlying_id`. Covers a subset of underlyings (e.g. none for فولاد). No index on `underlying_id` (22 s scan). `fetched_at` is varchar in mixed formats. | profiling | B/E — index added |
| Options pricing (`domain/options/pricing.py`) | BS + bracketed IV solver returning `None` when unreliable. | code | A — reused |
| Fee schedule (`domain/trading/iran_costs.py`) | Per-instrument-class all-in rates; file itself says "re-verify". | code | A (with caveat) |
| Disclosures (`brsapi_codal_announcements`) | 88 k rows, fresh to 14 Nov; titles/links only. 103 recent sync errors. | DB | B |
| Positions (`portfolios`, `portfolio_positions`, `paper_*`) | All empty. No trade history, fees or partial fills in the schema. | row counts | C — ledger added |
| Portfolio risk (`services/portfolio_risk.py`, `risk_engine_v1.py`) | Reads the (empty) paper ledger for the signal pipeline; not a capital/limits model. | code | B |
| Kill switch (`services/kill_switch.py`) | Works; halts new signals only. | code | A — honoured |
| Telegram (`integrations/notifications/telegram_sender.py`) | Works when configured, but logged/returned httpx error text that **contains the bot token**. No bot token set; no user has `telegram_chat_id`. | code, `.env`, `users` | D (fixed) + blocked on config |
| In-platform notifications / sound | None for alerts. `useNotificationSound` hook exists. | grep | C — built on the existing hook |
| Scheduler / job queue | APScheduler + Redis queue, `max_instances=1`, registry. | `apps/scheduler/app.py` | A — reused |
| BrsApi client / budget governor | Present with limiter, breaker, redaction. Key is set. Daily budget (10,000) is being exhausted; circuit breaker open on Candlestick/History/Shareholder. | `brsapi_sync_log` | A/D (capacity) |
| Backtesting | Large framework exists; not connected to these rules. | tree | B |

Operational observation (not changed): during this work two of your own scripts were running; `migrate_transactions_simple.py` had been waiting ~25 min on a row lock held by `update_jalali_dates.py`.

---

## 2. Data-coverage and gap matrix (verified on the stored data)

The engine reads what the existing sync jobs store; it never calls BrsApi itself, so it adds no API cost and cannot bypass the budget governor. Endpoint claims below come from `brsapi_sync_log`, not from documentation. Observed latency = age of the newest row when checked; publication frequency = the existing job cadence.

| Requirement | Source → endpoint | Key fields | Cadence / observed latency | History | Status | Criticality | Fallback |
|---|---|---|---|---|---|---|---|
| Identity, ISIN, market, state | `brsapi_symbol_details` ← `/Tsetmc/Symbol.php` | ins_id, isin, market, sub_sector, state | daily; 2–3 days old; budget errors | since Aug 2026 | Available but delayed | critical | snapshot row (ins_id, isin, name) |
| Quote + 5-level book + real/legal | `brsapi_symbol_snapshots` ← `/Tsetmc/AllSymbols.php` | pl, pc, py, pd/po/qd/qo 1–5 | minutes in session; last 14 Nov 18:08 UTC | ~4 months | Available and valid (when sync runs) | critical | none |
| Daily price limits | same payload (`tmin`,`tmax`) | tmin, tmax | with quote | — | Available and valid | critical for queue state | none — never assumed |
| Daily OHLC history | `brsapi_historical_daily` ← `/Tsetmc/History.php` | date (Jalali), price_close, volume | daily; breaker open intermittently | 260+ sessions for liquid names | Available; `gregorian_date` unreliable | critical for sizing | latest close appended from snapshot |
| Intraday trades | `/Tsetmc/Transaction.php` | — | 400/424 errors, tables empty | — | Incomplete | non-critical | none → no tick analytics |
| Intraday candles | `brsapi_candlesticks` | o,h,l,c | breaker open (5,303 errors) | to 11–12 Nov | Available but delayed | not used | — |
| Related options | `brsapi_option_snapshots` ← `/Tsetmc/Option.php` | strike, expiry, bid/ask, OI, volume | in session; last 14 Nov 21:39 | since Jul 2026 | Available and valid; subset of underlyings | non-critical input | state "none" vs "unavailable" kept apart |
| Official NAV | `brsapi_nav_records` ← `/Tsetmc/Nav.php` | nav_issue, nav_redemption, date | **stopped 2026-10-05** | 330 funds | Available but stale (41 days) | needed for premium/discount | none → premium not computed |
| Fund holdings, unit classes | `fund_holdings`, `fund_unit_classes` | — | never loaded | — | Not provided / not yet verified at source | needed for estimated NAV, leverage | none |
| Disclosures | `brsapi_codal_announcements` ← `/Codal/Announcement.php` | title, publish date/time, links | office hours; last 14 Nov | 88 k rows | Available and valid (titles only) | informational | — |
| Financial statements | codal financial tables | — | not wired to this flow | — | Not yet verified | needed for equity fundamentals | — |
| Market breadth | computed from snapshots | change % per symbol | with quote | — | Available and valid | critical for regime | none → regime "disrupted" |
| Index (total / equal weight) | `brsapi_index_values` ← `/Tsetmc/Index.php` | index_equal_weight(+change) | with quote | — | Incomplete (no names, pct = 0) | corroboration only | breadth |
| News relevance | `news_articles` | — | 22 k rows; no instrument mapping in this flow | — | Not yet verified | informational | — |
| Gold/FX basis for commodity funds | gold/currency tables | — | present, not integrated | — | Not yet verified | needed for category D | — |
| Subscriptions/redemptions, market-maker terms, prospectus | — | — | — | — | Not provided by the source | — | new source would be needed (approval required) |

No new external source was introduced.

---

## 3. Supported-instrument matrix (what is honestly analysed today)

Live result = `scripts/alert_engine_live_check.py --assume-closed` on the real data of 14 Nov (transaction rolled back).

| Category | Support | Analysed | Explicitly not analysed | Live test | Result |
|---|---|---|---|---|---|
| Ordinary equity | Partial | identity, quote quality, limits/queue, spread, depth, trend, volatility, disclosures, related options, sizing, portfolio risk | fundamentals, valuation, industry/macro | فولاد | `await/no entry`: locked in **buy queue** at 5,090, zero offer depth |
| Equity fund | Partial | as above + official NAV (with freshness) | estimated NAV, holdings, concentration, flows | آگاس | `await_confirmation`; NAV **stale** → premium not computed |
| Leveraged fund | Partial | as above + related options | unit-class structure, effective leverage, path dependence, class-attributable NAV | موج | `no_trade`: **locked sell queue** at the −6 % limit (2,552,342 units, 154 orders); 52 option contracts, **0 with a reliable IV** |
| Gold / commodity fund | Partial | market + official NAV | gold/FX basis, certificates | عیار | `await_confirmation` (5- and 20-session trend negative) |
| Fixed-income fund | Market only | market + official NAV | composition, credit, duration | کیان | `await_confirmation` |
| Option contract | Restricted | recognised, described | any trade recommendation (needs separate approval) | ضموج834 | `restricted` |
| Subscription right | Unsupported | identity only (ISIN class `IRR`) | everything | امینح | `unsupported` + stated limitation |
| Futures, commodity certificates | Unsupported | identity only | everything | — | — |
| Unknown symbol | Refused | — | — | نمادناموجود | activation refused; nothing created |
| Instrument without options | — | — | — | آگاس, فولاد | options state `none` (distinct from `unavailable`/`stale`) |

With the real clock (market open, sync not running) the same instruments returned **"insufficient data — quote stale"**, which is the intended behaviour.

---

## 4. Architecture

```
Alerts page (tab «پایش ابزارها»)  ──  /api/v1/alerts/monitors, /alerts/engine/*
        │
services/alert_engine/engine.py     activate · analyze · remove · portfolio · settings
   ├─ data.py          identity + every DB read, each with provenance and a coverage status
   ├─ analytics.py     queue/limits, spread, depth, VWAP, volatility, trend, discontinuities   (pure)
   ├─ options_view.py  related options as an input; IV only from valid quotes                  (pure)
   ├─ regime.py        experimental breadth classifier with hysteresis                         (pure)
   ├─ risk.py          ledger → cash/positions/equity, daily loss, drawdown, sizing            (pure)
   ├─ decision.py      recommendation contract                                                 (pure)
   ├─ notifier.py      in-platform store + Telegram states, dedup, quiet hours, retries
   └─ settings.py      versioned risk / freshness / notification settings                      (pure)
jobs/definitions/alert_jobs.py::MonitorAlertInstrumentsJob   every 2 min (apps/scheduler/app.py)
```

Design decisions:

* **Extend, don't fork.** Reuses the classifier, option pricing, fee table, kill switch, scheduler/registry, `TelegramSender`, `useNotificationSound`, `SymbolSelector`. The fabricating `app/alert_hub` was not revived.
* **State in the database.** `alert_monitors` has a partial unique index `(user_id, symbol) WHERE status='active'`; analysis locks the row `FOR UPDATE SKIP LOCKED`. Duplicate monitors, concurrent duplicate analysis and orphaned work after removal are structurally impossible; a restart just re-reads active rows.
* **Unchanged inputs create no new record** (input hash + validity), so history is not padded.
* **Critical-data map:** new entry needs identity, quote, history, breadth; position management needs identity, quote. A stale NAV is reported as missing information, not a block.
* **Shared capital.** One toman pool per user; sizing = the tightest of risk budget, regime ceiling, concentration, cash, stress gap, participation, visible depth. Rials→tomans conversion in one function.
* **Positions only from the ledger.** A recommendation is never treated as executed; an unconfirmed exit never frees cash; paper and actual books are separate.
* **No fabricated precision.** No price targets, no probabilities, no estimated NAV, no leverage figure, no IV from invalid quotes. Confidence is descriptive ("low — unvalidated heuristic").

Recommendation states: `conditional_entry`, `await_confirmation`, `hold`, `reduce`, `exit`, `exit_infeasible`, `no_trade`, `insufficient_data`, `unsupported`, `restricted`. Same-day exit classes A/B/C/D are in `exit_assessment`.

---

## 5. Implemented changes

New:

* `services/alert_engine/` — `__init__`, `settings`, `analytics`, `risk`, `options_view`, `regime`, `decision`, `data`, `notifier`, `engine`
* `models/alert_engine.py` — `alert_monitors`, `alert_analyses`, `alert_notifications`, `alert_engine_settings`, `alert_ledger_entries`, `alert_equity_state`
* `migrations/versions/0127_alert_engine.py` (revises your pending, uncommitted `0126_transactions_jalali_date`)
* `apps/api/endpoints/alert_monitors.py`
* `frontend/src/components/alerts/MonitorWorkspace.tsx`
* `scripts/alert_engine_apply_tables.py`, `scripts/alert_engine_live_check.py`
* `tests/unit/alert_engine/test_alert_engine_core.py`, `test_alert_engine_decision.py`, `tests/integration/test_alert_engine_lifecycle.py`

Modified:

* `apps/api/router.py` — mounts the engine router under `/alerts`
* `jobs/definitions/alert_jobs.py`, `jobs/definitions/__init__.py`, `apps/scheduler/app.py` — `MonitorAlertInstrumentsJob`
* `models/__init__.py` — registers the new models
* `frontend/src/app/alerts/page.tsx` — tabs: «پایش ابزارها» / «هشدارهای آستانه‌ای»
* `integrations/notifications/telegram_sender.py` — bot token redacted from errors/logs

API (all owner-scoped, under `/api/v1/alerts`): `GET/POST /monitors`, `GET/DELETE /monitors/{id}`, `POST /monitors/{id}/analyze`, `GET /engine/portfolio`, `GET/POST /engine/ledger`, `GET/PUT /engine/settings`, `POST /engine/settings/rollback`, `GET /engine/notifications`, `POST /engine/notifications/ack`, `POST /engine/notifications/test-telegram`, `GET /engine/health`, `GET /engine/support-matrix`.

---

## 6. Configuration and migration

1. Tables. Either `alembic upgrade head` (this also applies your pending 0126), or — as done on the dev DB — `python scripts/alert_engine_apply_tables.py`, which runs only 0127's idempotent statements and leaves `alembic_version` (still 0125) alone.
2. Scheduler: restart it so `MonitorAlertInstrumentsJob` is registered.
3. Telegram (optional): set `TELEGRAM_BOT_TOKEN`; store each user's own chat id in `users.telegram_chat_id`; enable in the UI. Messages go only to the chat linked to that user. Optional `frontend_base_url` setting adds a report link.
4. Risk settings are per user, versioned, default to the agreed starting values (500,000,000 toman; 0.5 % / 1.5 % / 5 % = 2.5 M / 7.5 M / 25 M). Loosening any limit requires `confirm_loosening=true`; every change is a new version; rollback creates a new version from an old one.

---

## 7. Test results (executed)

| Suite | Result |
|---|---|
| `tests/unit/alert_engine` (pure logic) | **32 passed** |
| `tests/integration/test_alert_engine_lifecycle.py -m needs_db` (real schema + real market data, rolled back) | **11 passed** |
| Existing guards: router mount decisions, route inventory, migration ids, cron alerts | **16 passed** |
| `ruff` on all new/changed Python | clean |
| `tsc --noEmit` (frontend) | no errors in new/changed files; 2 pre-existing errors in `options/components/AnalyticsPanel.tsx` |
| `MonitorAlertInstrumentsJob` smoke run | success, 0.48 s with no monitors |

Acceptance coverage:

* Instruments — stock, equity fund, leveraged fund, gold fund, fixed-income fund, no-options instrument, unsupported, unknown: live run (section 3).
* Lifecycle — add, duplicate add, restart, remove, re-add, remove with shared instrument, remove with a recorded position (acknowledgement required), concurrent analysis skipped: integration tests.
* Data — missing/zero/invalid fields, stale quote, stale NAV, missing limits, corporate-action discontinuity: unit tests; stale data live. *Contradictory sources*: classification conflict is flagged; price-source contradiction is not tested (single price source).
* Portfolio — shared 500 M pool, purchase beyond cash, partial fill, oversell, paper vs actual, daily-loss breach, drawdown review, deposits not counted as performance, unmarked positions: unit + integration.
* Execution realism — wide spread, zero depth, locked sell and buy queues, suspension, unfilled exit (`exit_infeasible`), overnight gap scenario: unit tests; locked queues live.
* Notifications — stored in-platform, dedup, Telegram success and failure with bounded retries, not-configured, stale-opportunity suppression, quiet hours with and without approved critical delivery, token never stored, acknowledgement: integration tests with a fake sender.

**Not executed:** API rate-limit / outage injection (the engine does not call the API; an outage surfaces as stale data, which is tested); a real Telegram send (no bot token or chat id configured); audio in a browser and the UI end-to-end (see section 9); correlated-position and fund/stock overlap tests (no holdings data).

---

## 8. Historical and paper evaluation

**None exists, and none is claimed.** The rule set (`rules-2026.11.15-a`) and the regime classifier have not been backtested or evaluated out of sample. Every stored analysis records its inputs, rule/engine/settings versions and timestamps, so live paper monitoring starts accumulating an evaluable record once the scheduler runs with fresh data. Connecting the rules to the existing `backtesting/` framework with availability-time data is open work. A working software path is not evidence of a profitable strategy.

---

## 9. End-to-end and notification evidence

* Engine end-to-end on real data: section 3, reproducible with `python scripts/alert_engine_live_check.py [--assume-closed]`.
* HTTP end-to-end against the running local API (`python scripts/alert_engine_api_e2e.py`, real routes, real auth, a throw-away local account whose credentials live in the git-ignored `.env.alert_e2e`): **all 15 checks passed** — add, identity, coverage, idempotent duplicate, unknown symbol refused, threshold-alert routes intact, portfolio defaults, purchase beyond cash rejected, confirmed trade recorded, removal asks for acknowledgement, loosening needs confirmation, notification stored, support matrix. The Telegram test correctly reported `not_configured`.
* The scheduler job executes; routes pass the route-inventory guard.
* The browser UI was type-checked but **could not be exercised in the browser**: in this dev setup the login page lost its session on reload and then hit the app's own login rate limit (10/min) on retries — an existing auth/dev-environment behaviour, not investigated further. The Alerts tab therefore remains visually unverified.
* Notifications: in-platform storage and Telegram state handling are tested; an actual Telegram delivery and audible playback are unverified.

---

## 10. Known limitations and unresolved risks

* Rules and regime thresholds are unvalidated heuristics. Outputs are decision support in paper mode.
* Freshness depends on the BrsApi sync cadence and budget; the 2-minute job cannot make data fresher. Budget exhaustion currently degrades several feeds.
* Snapshot microstructure only: no tick data, no order placement/cancellation history. Nothing is said about bots, participants or intent.
* Closed-market freshness uses a 100-hour window rather than an exchange holiday calendar; `market_holidays.json` is not wired in.
* Trading hours come from `jobs/market_hours.py` (Sat–Wed 08:45–12:30) for all instruments; instrument-specific sessions/auctions are not modelled.
* Options: European Black–Scholes with an assumed 30 % rate, no dividends; exercise/settlement terms are not in the source. On 14 Nov no Moj contract produced a reliable IV.
* Fees come from the repo table, which itself asks for re-verification.
* Concentration is shown by sector only; correlation and fund look-through are unavailable.
* Stress testing is limited to a one-limit-day gap scenario per position/entry.
* Quiet-hours-suppressed Telegram messages are not re-sent later; they remain in the platform.
* Legacy `alert_service` still reports log-only channels as delivered (left as is; out of the engine path).

---

## 11. Blockers

| Blocker | Affects | Safe partial mode | To unblock |
|---|---|---|---|
| `/Tsetmc/Nav.php` sync failing since 2026-10-05 (budget) | premium/discount for all funds | yes — NAV shown as stale, premium withheld | budget allocation for the NAV job |
| No fund holdings / unit-class data | estimated NAV, effective leverage, look-through, overlap | yes — stated as unavailable | a verified source for portfolio reports + prospectus terms (new source ⇒ your approval) |
| No bot token / chat ids | Telegram | yes — in-platform only; state `not_configured` | set token, link chat ids |
| Fundamentals not wired | equity valuation | yes — market-only analysis, stated | integrate existing Codal financial tables |
| No evaluation | any claim about rule quality; operational mode | yes — paper label enforced in settings validation | backtest + paper period |
| BrsApi budget exhausted daily | freshness of several feeds | yes — degraded/blocked states shown | budget review or plan change (cost decision) |

---

## 12. Operations

* Health: `GET /api/v1/alerts/engine/health` (market-data freshness, monitors by state, Telegram states, kill switch).
* Job result data: `monitors, analyzed, unchanged, skipped_locked, errors, deferred`. `deferred > 0` means the 90-second pass budget was hit and cadence is reduced — it is reported, not hidden.
* A failing instrument sets `monitoring_state='error'`, keeps the last valid analysis visible and raises one critical notification per hour; others continue.
* Stop new risk: "توقف توصیهٔ ورود جدید" in the UI (`risk.halt_new_entries`) or the system kill switch. Neither hides positions or risk warnings.
* Recovery after downtime: nothing to do; active monitors resume on the next run.
* Rollback: settings via `/engine/settings/rollback`; code by unscheduling the job and unmounting the router; `0127` downgrade drops only the new tables and index.

---

## 13. Completed / partial / blocked

**Completed and tested:** alert lifecycle, identity and classification, coverage and freshness matrix per instrument, market/liquidity analytics with real limits, related-options module, shared-capital ledger and risk limits, sizing, recommendation contract with same-day-exit classes, versioned settings, in-platform notifications with Telegram state machine, scheduler job, API, Alerts-page UI (type-checked).

**Partial:** equity and fund specialisation (market side only), regime (experimental), stress testing (single scenario), portfolio concentration (sector only), UI (not browser-verified), news/macro context (not integrated), factor registry (evidence is tagged by factor in each report; no standalone registry or ablation).

**Blocked:** estimated NAV, class-attributable NAV, leverage, fund look-through, premium/discount (until NAV sync is repaired), Telegram delivery, any historical or paper performance result.

## Decisions that need your approval

1. `ceiling_unfavorable_pct = 0` and `max_single_instrument_pct = 50` are my provisional choices inside the ranges you gave.
2. Assumed risk-free rate of 30 % for option analytics.
3. Whether to spend BrsApi budget on restoring the NAV feed (and at what priority).
4. Whether a new data source for fund portfolios / unit classes may be evaluated.
5. Whether `alembic upgrade head` (which includes your pending 0126) may be run, or 0127 should stay applied via the helper script.
