"""Versioned settings of the alert engine (pure — no I/O).

Every value here is a *provisional, configurable starting point for paper evaluation*,
not a standard and not a guarantee that losses stay inside it. Settings are stored as
immutable versions (see ``models.alert_engine.AlertEngineSettingsModel``); a change is a
new version recorded with who approved it, so a recommendation can always name the
settings it was produced under and a version can be rolled back to.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any

RIAL_PER_TOMAN = 10


def rial_to_toman(value: float | None) -> float | None:
    """The single place market rials become strategy tomans."""
    return None if value is None else value / RIAL_PER_TOMAN


def toman_to_rial(value: float | None) -> float | None:
    return None if value is None else value * RIAL_PER_TOMAN


class SettingsError(ValueError):
    """A proposed settings document is invalid."""


@dataclass(frozen=True)
class RiskSettings:
    # ── capital (tomans; confirmed by the user) ──
    capital_toman: float = 500_000_000.0
    currency: str = "IRT"
    # ── loss limits (percent) ──
    per_trade_risk_pct: float = 0.5          # of current strategy equity
    daily_loss_stop_pct: float = 1.5         # of start-of-day equity, flow-adjusted
    drawdown_review_pct: float = 5.0         # from the flow-adjusted high-water mark
    # ── allocation ceilings by regime (percent of equity, portfolio-wide) ──
    ceiling_favorable_pct: float = 100.0
    ceiling_neutral_pct: float = 60.0
    ceiling_unfavorable_pct: float = 0.0
    # ── concentration ──
    max_single_instrument_pct: float = 50.0
    #: Must be explicitly accepted before a single instrument may take the whole ceiling.
    full_single_allocation_accepted: bool = False
    # ── sizing realism ──
    min_stop_distance_pct: float = 2.0       # a tighter analytical stop never sizes bigger
    stop_vol_multiple: float = 1.5           # stop distance = max(floor, k × daily vol)
    stress_loss_multiple: float = 3.0        # limit-day gap loss ≤ k × per-trade budget
    min_slippage_bps: float = 10.0
    max_participation_pct: float = 1.0       # of average daily volume
    max_depth_multiple: float = 1.0          # entry ≤ k × visible executable depth
    max_spread_pct: float = 1.0              # wider spread ⇒ no entry recommendation
    # ── options analytics assumption (disclosed with every IV) ──
    assumed_risk_free_rate: float = 0.30
    # ── controls ──
    halt_new_entries: bool = False           # stops risk-increasing recommendations only
    recommendation_validity_minutes: int = 15
    mode: str = "paper"

    def ceiling_for(self, regime: str) -> float:
        return {
            "favorable": self.ceiling_favorable_pct,
            "neutral": self.ceiling_neutral_pct,
            "unfavorable": self.ceiling_unfavorable_pct,
        }.get(regime, 0.0)  # disrupted / insufficient data ⇒ no new allocation

    def budgets_toman(self, equity_toman: float) -> dict[str, float]:
        return {
            "per_trade_risk": equity_toman * self.per_trade_risk_pct / 100,
            "daily_loss_stop": equity_toman * self.daily_loss_stop_pct / 100,
            "drawdown_review": equity_toman * self.drawdown_review_pct / 100,
        }


@dataclass(frozen=True)
class FreshnessPolicy:
    """Maximum acceptable age per data type. Quotes and disclosures do not share a rule."""

    quote_open_seconds: int = 300            # while the session is open
    quote_closed_hours: int = 100            # last-session data across a weekend + holiday
    options_open_seconds: int = 900
    options_closed_hours: int = 100
    nav_official_days: int = 2
    history_days: int = 6
    index_closed_hours: int = 100
    index_open_seconds: int = 900
    disclosures_sync_hours: int = 48


@dataclass(frozen=True)
class NotificationPrefs:
    sound_enabled: bool = True
    #: severities that play a sound in the platform
    sound_severities: tuple[str, ...] = ("opportunity", "material_change", "risk_warning", "critical")
    telegram_enabled: bool = False
    #: Tehran wall-clock "HH:MM"; both empty ⇒ no quiet hours
    quiet_start: str = ""
    quiet_end: str = ""
    #: user-approved: deliver critical alerts to Telegram during quiet hours
    critical_during_quiet: bool = False
    #: balances / position sizes stay out of Telegram unless opted in
    telegram_include_financials: bool = False
    telegram_max_attempts: int = 3


@dataclass(frozen=True)
class EngineSettings:
    risk: RiskSettings = field(default_factory=RiskSettings)
    freshness: FreshnessPolicy = field(default_factory=FreshnessPolicy)
    notifications: NotificationPrefs = field(default_factory=NotificationPrefs)

    def to_dict(self) -> dict[str, Any]:
        doc = asdict(self)
        doc["notifications"]["sound_severities"] = list(self.notifications.sound_severities)
        return doc

    @classmethod
    def from_dict(cls, doc: dict[str, Any] | None) -> EngineSettings:
        doc = doc or {}
        return cls(
            risk=_build(RiskSettings, doc.get("risk")),
            freshness=_build(FreshnessPolicy, doc.get("freshness")),
            notifications=_build(NotificationPrefs, doc.get("notifications")),
        )

    def merged(self, patch: dict[str, Any]) -> EngineSettings:
        """Apply a partial update and validate the result. Unknown keys are an error."""
        doc = self.to_dict()
        for section, values in (patch or {}).items():
            if section not in doc:
                raise SettingsError(f"unknown settings section: {section}")
            if not isinstance(values, dict):
                raise SettingsError(f"section {section} must be an object")
            unknown = set(values) - set(doc[section])
            if unknown:
                raise SettingsError(f"unknown keys in {section}: {sorted(unknown)}")
            doc[section].update(values)
        out = EngineSettings.from_dict(doc)
        validate(out)
        return out


def _build(klass: Any, raw: dict[str, Any] | None) -> Any:
    raw = raw or {}
    known = {f.name for f in fields(klass)}
    values = {k: v for k, v in raw.items() if k in known}
    if "sound_severities" in values:
        values["sound_severities"] = tuple(values["sound_severities"])
    return klass(**values)


def _pct(name: str, value: float, lo: float = 0.0, hi: float = 100.0) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not lo <= value <= hi:
        raise SettingsError(f"{name} must be a number in [{lo}, {hi}]")


def _hhmm(name: str, value: str) -> None:
    if value == "":
        return
    try:
        hh, mm = value.split(":")
        if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
            raise ValueError
    except ValueError:
        raise SettingsError(f"{name} must be HH:MM or empty") from None


def validate(settings: EngineSettings) -> None:
    r = settings.risk
    if not isinstance(r.capital_toman, (int, float)) or r.capital_toman <= 0:
        raise SettingsError("capital_toman must be positive")
    if r.currency != "IRT":
        raise SettingsError("strategy currency is tomans (IRT); market rials are converted centrally")
    _pct("per_trade_risk_pct", r.per_trade_risk_pct, 0.01, 5)
    _pct("daily_loss_stop_pct", r.daily_loss_stop_pct, 0.1, 20)
    _pct("drawdown_review_pct", r.drawdown_review_pct, 0.5, 50)
    for name in ("ceiling_favorable_pct", "ceiling_neutral_pct", "ceiling_unfavorable_pct",
                 "max_single_instrument_pct"):
        _pct(name, getattr(r, name))
    if not r.ceiling_unfavorable_pct <= r.ceiling_neutral_pct <= r.ceiling_favorable_pct:
        raise SettingsError("ceilings must not increase as the regime worsens")
    if r.max_single_instrument_pct > 50 and not r.full_single_allocation_accepted:
        raise SettingsError(
            "a single-instrument cap above 50% requires full_single_allocation_accepted=true"
        )
    _pct("min_stop_distance_pct", r.min_stop_distance_pct, 0.5, 20)
    _pct("max_spread_pct", r.max_spread_pct, 0.05, 10)
    _pct("max_participation_pct", r.max_participation_pct, 0.01, 25)
    if r.stop_vol_multiple <= 0 or r.stress_loss_multiple < 1 or r.max_depth_multiple <= 0:
        raise SettingsError("stop_vol_multiple/stress_loss_multiple/max_depth_multiple out of range")
    if not 0 <= r.assumed_risk_free_rate <= 1:
        raise SettingsError("assumed_risk_free_rate must be a fraction in [0, 1]")
    if not 1 <= r.recommendation_validity_minutes <= 240:
        raise SettingsError("recommendation_validity_minutes must be in [1, 240]")
    if r.mode != "paper":
        raise SettingsError("only paper mode is available; operational mode needs evaluation + approval")
    n = settings.notifications
    _hhmm("quiet_start", n.quiet_start)
    _hhmm("quiet_end", n.quiet_end)
    if bool(n.quiet_start) != bool(n.quiet_end):
        raise SettingsError("quiet_start and quiet_end must be set together")
    if not 1 <= n.telegram_max_attempts <= 5:
        raise SettingsError("telegram_max_attempts must be in [1, 5]")


def loosens_risk(old: RiskSettings, new: RiskSettings) -> list[str]:
    """Names of limits the new version relaxes — these need explicit user approval."""
    higher_is_looser = (
        "capital_toman", "per_trade_risk_pct", "daily_loss_stop_pct", "drawdown_review_pct",
        "ceiling_favorable_pct", "ceiling_neutral_pct", "ceiling_unfavorable_pct",
        "max_single_instrument_pct", "stress_loss_multiple", "max_participation_pct",
        "max_depth_multiple", "max_spread_pct",
    )
    out = [k for k in higher_is_looser if getattr(new, k) > getattr(old, k)]
    if new.min_stop_distance_pct < old.min_stop_distance_pct:
        out.append("min_stop_distance_pct")
    if new.full_single_allocation_accepted and not old.full_single_allocation_accepted:
        out.append("full_single_allocation_accepted")
    if old.halt_new_entries and not new.halt_new_entries:
        out.append("halt_new_entries")
    return out
