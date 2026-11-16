"""Alert Engine — instrument monitoring, analysis and notification behind the Alerts section.

Workflow (one pass per monitored instrument):

    identity → data coverage/freshness → instrument analytics → shared portfolio risk
    → conditional recommendation → notifications → persisted, auditable history

Hard boundaries (enforced by construction — nothing in this package can do otherwise):

* Analysis, recommendations and notifications only. No module here imports a broker
  client or submits/modifies/cancels orders.
* Positions exist only when the user records a confirmed trade in the ledger.
* Missing, stale and invalid inputs are distinct states and never replaced by defaults.
* Heuristic outputs are labelled as such; no number here is a calibrated probability.

Module map:

* ``settings``   — versioned risk / freshness / notification settings (pure)
* ``analytics``  — order-book, liquidity, trend and volatility maths (pure)
* ``risk``       — ledger → positions/cash/equity, sizing, portfolio limits (pure)
* ``options_view`` — related-options summary as an analytical input (pure)
* ``regime``     — experimental market-regime classifier (pure)
* ``decision``   — the recommendation contract (pure)
* ``data``       — every database read, each value tagged with its provenance
* ``notifier``   — in-platform + Telegram delivery with dedup / quiet hours / states
* ``engine``     — lifecycle (activate / analyse / remove) and persistence
"""

ENGINE_VERSION = "alert-engine/0.1.0"
#: Version of the heuristic rule set in ``decision``. Bump on any rule change so every
#: stored recommendation names the rules that produced it.
RULES_VERSION = "rules-2026.11.15-a"
#: Everything this engine emits today is paper/decision-support output.
MODE_PAPER = "paper"
