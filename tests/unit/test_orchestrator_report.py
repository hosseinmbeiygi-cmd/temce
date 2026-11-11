"""Unit tests for ``OrchestratorReport.to_dict`` accuracy None-safety.

Regression test for the hourly orchestrator cron crash
(``AttributeError: 'NoneType' object has no attribute 'get'`` at
``apps/api/app.py`` ``_orchestrator_hourly_cron``): the early-return path of
``QuantSignalOrchestrator.generate`` (no raw signals) leaves
``accuracy_snapshot=None`` and consumers call ``d.get("accuracy").get(...)``.

The serialized contract is: ``to_dict()["accuracy"]`` is **always a dict**,
never ``None`` — even when the dataclass field is left unset.
"""

from __future__ import annotations

from services.quant_signal_orchestrator import OrchestratorReport


def _make_report(**overrides) -> OrchestratorReport:
    """Build a minimal report; dataclass defaults keep the test DB-free."""
    defaults: dict = {
        "signals": [],
        "summary": {},
        "generation_reports": [],
    }
    defaults.update(overrides)
    return OrchestratorReport(**defaults)


class TestAccuracyNoneSafety:
    """``to_dict()["accuracy"]`` must always be a dict (cron consumers rely on it)."""

    def test_none_accuracy_snapshot_serializes_to_empty_dict(self) -> None:
        """The bug path: field left at its default (None) must serialize as {}."""
        report = _make_report()  # accuracy_snapshot not passed -> None
        d = report.to_dict()
        assert isinstance(d["accuracy"], dict)
        assert d["accuracy"] == {}

    def test_none_accuracy_supports_get_overall(self) -> None:
        """Exact access pattern used by the hourly cron that used to crash."""
        report = _make_report()
        accuracy = report.to_dict().get("accuracy", {})
        assert accuracy.get("overall", 0) == 0  # AttributeError before the fix

    def test_explicit_none_is_coerced_to_empty_dict(self) -> None:
        """Even an explicit ``accuracy_snapshot=None`` must serialize as {}."""
        report = _make_report(accuracy_snapshot=None)
        assert report.to_dict()["accuracy"] == {}

    def test_populated_snapshot_survives_serialization(self) -> None:
        """A real snapshot must pass through unchanged."""
        snapshot = {"stock": 100.0, "gold": 36.92, "overall": 33.93}
        report = _make_report(accuracy_snapshot=snapshot)
        assert report.to_dict()["accuracy"] == snapshot

    def test_early_return_kwargs_produce_consistent_contract(self) -> None:
        """The generate() early-return path passes accuracy_snapshot={};
        serialization must keep it a dict."""
        report = _make_report(accuracy_snapshot={})
        d = report.to_dict()
        assert isinstance(d["accuracy"], dict)
        assert d["accuracy"].get("overall", 0) == 0


class TestSerializationShape:
    """Guard the overall to_dict() contract expected by API consumers."""

    def test_required_keys_present(self) -> None:
        d = _make_report().to_dict()
        for key in ("signals", "summary", "reports", "accuracy", "cross_market", "retrain", "generated_at"):
            assert key in d, f"missing key: {key}"

    def test_list_fields_never_none(self) -> None:
        d = _make_report().to_dict()
        assert isinstance(d["signals"], list)
        assert isinstance(d["reports"], list)
        assert isinstance(d["cross_market"], list)
        assert isinstance(d["retrain"], list)
