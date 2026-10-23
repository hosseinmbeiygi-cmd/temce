# BASELINES — Definition of baselines, benchmarks and control tests (R4)

> A temporary substitute for the baseline needs until `SPEC_STRATEGIES.md` (S0 to S13) is in the repo root. If your S0a/S0c definitions differ, **yours win** and this file must be aligned with them.
> No numeric threshold is here; acceptance only via `acceptance.yaml`.

## 1. Why
The audit showed the current "random baseline" (90% cash sizing) is effectively buy-and-hold and makes returns uninterpretable. In the Iranian market, with high inflation, nominal equity returns carry an inflationary drift; so comparing only against nominal buy-and-hold is not enough.

## 2. Baselines (all long-only, all with costs from `rule_at`, executed per the reference rule)
| Code | Definition | Use |
|---|---|---|
| BL-1 | buy-and-hold per symbol (adjusted) | basic benchmark |
| BL-2 | equal-weight portfolio of the universe with rebalancing from config | market benchmark (less affected by a few large symbols) |
| BL-3 | **matched-exposure random:** long/flat, time-in-market equal to the compared strategy, 200 seeds (RNG separate per `seed+component_id`); report mean, std, 5th and 95th percentile | skill vs chance |
| BL-3b *(optional)* | **matched-lock-exposure random:** BL-3, plus the share of its entries that fall on days which turned out (ex post) to be lock days is matched to the compared strategy's own share | diagnostic only: shows how much a result depends on lock-day entries; uses after-the-fact lock information, so it is never a decision-time input and never a pass/fail control |
| BL-4 | the same BL-3 on a detrended series (subtract drift or shuffle returns) | measures "cost drag" |
| BL-5 | **look-ahead aligned with execution price** (signal = direction of the return between execution price at t+1 and t+2 in the same reference fill rule), long/flat | positive control: must give abnormal returns and be **rejected** by the leakage test; see note 5.2 |
| BL-6 | signal shifted +1 and −1 | control: a shift must not improve results |
| BL-7 | asset benchmarks: gold/coin, USD, fixed-income fund, deposit (only with available data; otherwise `suspended`) | inflation-aware benchmark |

## 3. Three measures for everything
**Nominal**, **real** (`(1+r)/(1+π) − 1`), **USD** (with an explicit reference rate) returns. A result positive only in nominal terms ⇒ warning. Reference rate and inflation index live in `acceptance.yaml`, section `reference_rates`.

## 4. Mandatory outputs next to every result
`beta` and value added beyond market timing; `N_eff` (effective number of symbols from the correlation matrix); `fillable_rate` by score decile (UNCALIBRATED until R7); `days_to_exit`; `unfillable_profit_share` (share of P&L coming from entries on a locked side without queue data; the threshold lives only in `acceptance.yaml`); `n_epochs`; leave-one-epoch-out; `n_trials`; DSR/PBO; "avoided loss" for exit signals.

## 5. Interpretation note
Matched-exposure random with full costs on the audit's real series was negative in 1000 of 1000 runs (roughly −50% to −62%); so "random with costs is profitable" is always a sign of a measurement bug, not a market reality.

### 5.1 BL-3b (optional)
A sensitivity analysis, not a gate. A random baseline cannot know tomorrow's lock state, so BL-3b does not filter entries by it. It only reports how the strategy's result changes when the share of entries landing on lock-contaminated days (known after the fact) is matched. If the strategy's profit depends heavily on such entries, report it next to `unfillable_profit_share`.

### 5.2 BL-5 definition and engine behaviour
BL-5 stays exactly as defined above (look-ahead aligned with the execution price, long/flat). Do **not** pre-filter it to "tradable days" using information that would not be known at decision time; that would itself be a form of look-ahead. The reference engine decides what is executable (rejection, `unfillable`, halts). Report separately the share of BL-5 signals that the engine rejected or marked `unfillable`.

### 5.3 What is a control and what is a threshold
Controls (BL-3, BL-4, BL-5, BL-6) check that the measurement works. Pass/fail thresholds on strategy results (including `unfillable_profit_share`, number of epochs, and the return measures) are written only by the owner in `acceptance.yaml`.
