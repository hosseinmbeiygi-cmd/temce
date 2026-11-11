"""Gate 9 portfolio-risk tests — audit finding D-03.

The orchestrator used to pass ``portfolio_risk_approved=True`` to the decision
engine with a comment admitting the portfolio validator was never called
(fail-open). These tests pin the replacement: the context is read from the
paper-trading ledger, and an unreadable ledger blocks instead of approving.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.portfolio_risk import (
    DEFAULT_INITIAL_CAPITAL,
    PortfolioRiskState,
    compute_open_risk,
    load_portfolio_risk,
    unapproved_state,
)
from services.quant_signal_orchestrator import EnrichedSignal, QuantSignalOrchestrator

# ═══════════════════════════════════════════════════════════════════════════════
# ── Pure risk math
# ═══════════════════════════════════════════════════════════════════════════════


def test_open_risk_and_exposure_are_ratios_of_equity():
    rows = [{"market": "stock", "open_risk": 25_000_000.0, "exposure": 200_000_000.0}]
    open_risk_pct, exposure = compute_open_risk(rows, 1_000_000_000.0)
    assert open_risk_pct == pytest.approx(0.025)
    assert exposure == {"stock": pytest.approx(0.2)}


def test_markets_share_one_risk_budget_but_keep_their_own_exposure():
    rows = [
        {"market": "stock", "open_risk": 30_000_000.0, "exposure": 100_000_000.0},
        {"market": "gold", "open_risk": 10_000_000.0, "exposure": 400_000_000.0},
    ]
    open_risk_pct, exposure = compute_open_risk(rows, 1_000_000_000.0)
    assert open_risk_pct == pytest.approx(0.04)
    assert exposure["stock"] == pytest.approx(0.1)
    assert exposure["gold"] == pytest.approx(0.4)


def test_missing_market_rows_still_contribute_to_open_risk():
    rows = [{"market": None, "open_risk": 5_000_000.0, "exposure": 1_000_000.0}]
    open_risk_pct, exposure = compute_open_risk(rows, 1_000_000_000.0)
    assert open_risk_pct == pytest.approx(0.005)
    assert exposure == {"unknown": pytest.approx(0.001)}


@pytest.mark.parametrize("equity", [None, 0.0, -5.0])
def test_non_positive_equity_falls_back_to_the_paper_account_base(equity):
    rows = [{"market": "stock", "open_risk": DEFAULT_INITIAL_CAPITAL * 0.25, "exposure": 0.0}]
    open_risk_pct, _ = compute_open_risk(rows, equity)
    assert open_risk_pct == pytest.approx(0.25)


def test_null_aggregates_do_not_raise():
    rows = [{"market": "stock", "open_risk": None, "exposure": None}]
    open_risk_pct, exposure = compute_open_risk(rows, 1_000_000_000.0)
    assert open_risk_pct == 0.0
    assert exposure == {"stock": 0.0}


# ═══════════════════════════════════════════════════════════════════════════════
# ── State handed to Gate 9
# ═══════════════════════════════════════════════════════════════════════════════


def test_for_market_selects_that_markets_exposure():
    state = PortfolioRiskState(
        approved=True,
        equity=1_000_000_000.0,
        open_risk_pct=0.12,
        exposure_by_market={"stock": 0.3, "gold": 0.55},
    )
    assert state.for_market("gold") == (True, 0.12, 0.55)
    assert state.for_market("stock") == (True, 0.12, 0.3)
    assert state.for_market("crypto") == (True, 0.12, 0.0)


def test_unapproved_state_never_approves_a_market():
    state = unapproved_state("ledger down")
    approved, open_risk, correlated = state.for_market("stock")
    assert approved is False
    assert open_risk == 0.0
    assert correlated == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# ── Ledger reads
# ═══════════════════════════════════════════════════════════════════════════════


class _FakeResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def mappings(self) -> _FakeResult:
        return self

    def all(self) -> list:
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    def __init__(self, results: list[_FakeResult]) -> None:
        self._results = list(results)

    async def execute(self, *_args, **_kwargs) -> _FakeResult:
        return self._results.pop(0)


class _ExplodingSession:
    async def execute(self, *_args, **_kwargs):
        raise RuntimeError("paper_trades is gone")


@pytest.mark.asyncio
async def test_load_reads_open_positions_and_latest_equity():
    session = _FakeSession(
        [
            _FakeResult(
                [
                    {"market": "stock", "open_risk": 0.0, "exposure": 0.0, "positions": 0},
                ]
            ),
            _FakeResult([(Decimal("847475349.0"),)]),
        ]
    )
    state = await load_portfolio_risk(session)
    assert state.approved is True
    assert state.equity == pytest.approx(847_475_349.0)
    assert state.open_risk_pct == 0.0
    assert state.exposure_by_market == {"stock": 0.0}


@pytest.mark.asyncio
async def test_load_fails_closed_when_the_ledger_cannot_be_read():
    state = await load_portfolio_risk(_ExplodingSession())
    assert state.approved is False
    assert "RuntimeError" in state.reason
    approved, _, _ = state.for_market("stock")
    assert approved is False


@pytest.mark.asyncio
async def test_load_fails_closed_without_any_database_handle():
    with patch("core.database.async_session_factory", None):
        state = await load_portfolio_risk()
    assert state.approved is False
    assert "not initialised" in state.reason


@pytest.mark.asyncio
async def test_load_falls_back_to_initial_capital_without_equity_history():
    session = _FakeSession(
        [
            _FakeResult(
                [{"market": "stock", "open_risk": 10_000_000.0, "exposure": 50_000_000.0}]
            ),
            _FakeResult([]),
        ]
    )
    state = await load_portfolio_risk(session)
    assert state.equity == DEFAULT_INITIAL_CAPITAL
    assert state.open_risk_pct == pytest.approx(0.01)
    assert state.exposure_by_market == {"stock": pytest.approx(0.05)}


# ═══════════════════════════════════════════════════════════════════════════════
# ── Orchestrator wiring
# ═══════════════════════════════════════════════════════════════════════════════


def _sig() -> EnrichedSignal:
    return EnrichedSignal(
        symbol="E2E", name="e2e", market="stock", direction="buy", timeframe="daily",
        entry_zone="z", stop_loss="95", targets="110", risk_reward="2",
        position_sizing="s", confirmation_condition="c", reason="r",
        invalidation="i", trailing_stop="t", price=100.0, change_pct=7.0,
        rule_score=70.0, ml_score=0.6, boosted_score=70.0, ml_influence_pct=10.0,
        confidence=0.7, calibration_level="medium",
        vote_direction_scores={"buy": 0.7, "sell": 0.2},
        source="test", created_at="now",
    )


async def _run_pipeline(captured: dict) -> tuple[list, list]:
    decision = MagicMock()
    decision.verdict = MagicMock()
    decision.verdict.value = "release"
    decision.calibrated_probability = 0.72
    decision.effective_threshold = 0.58
    decision.net_expectancy_r = 0.15
    decision.gate_results = []

    async def _evaluate(candidate):
        captured["candidate"] = candidate
        return decision

    engine = MagicMock()
    engine.evaluate = AsyncMock(side_effect=_evaluate)
    engine.signal_grade.return_value = "A"

    with patch("services.signal_decision_engine.SignalDecisionEngine", return_value=engine):
        orchestrator = QuantSignalOrchestrator(session=None)
        return await orchestrator._apply_signal_decision([_sig()])


@pytest.mark.asyncio
async def test_candidate_carries_the_ledger_derived_portfolio_context():
    captured: dict = {}
    with patch(
        "services.portfolio_risk.load_portfolio_risk",
        AsyncMock(
            return_value=PortfolioRiskState(
                approved=True,
                equity=1_000_000_000.0,
                open_risk_pct=0.03,
                exposure_by_market={"stock": 0.42},
            )
        ),
    ):
        released, rejected = await _run_pipeline(captured)

    candidate = captured["candidate"]
    assert candidate.portfolio_risk_approved is True
    assert candidate.open_risk_pct == pytest.approx(0.03)
    assert candidate.correlated_exposure_pct == pytest.approx(0.42)
    assert len(released) == 1
    assert rejected == []


@pytest.mark.asyncio
async def test_candidate_is_not_approved_when_the_ledger_is_unreadable():
    captured: dict = {}
    with patch(
        "services.portfolio_risk.load_portfolio_risk",
        AsyncMock(return_value=unapproved_state("paper_trades is gone")),
    ):
        await _run_pipeline(captured)

    candidate = captured["candidate"]
    assert candidate.portfolio_risk_approved is False
    assert candidate.open_risk_pct == 0.0
    assert candidate.correlated_exposure_pct == 0.0
