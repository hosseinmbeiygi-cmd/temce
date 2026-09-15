"""Run Manifest — reproducibility metadata for every backtest run.

Every backtest run stores a manifest with:
- Strategy name/version
- Data version and hash
- Market rules version
- Corporate actions version
- Calendar version
- Random seed
- Full config snapshot
- Engine version
- Python version
- Dependency versions
- Git commit hash

This ensures any result can be exactly reproduced.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


def _git_commit_hash() -> str:
    """Get current git commit hash if available."""
    try:
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _dependency_versions() -> dict[str, str]:
    """Get versions of key dependencies."""
    deps = {}
    for pkg in ["numpy", "pandas", "fastapi", "pydantic", "sqlalchemy", "redis"]:
        try:
            import importlib

            mod = importlib.import_module(pkg)
            deps[pkg] = getattr(mod, "__version__", "unknown")
        except ImportError:
            pass
    return deps


def _data_hash(data: list[dict[str, Any]] | None) -> str:
    """Compute a hash of the input data for reproducibility."""
    if not data:
        return "empty"
    try:
        content = json.dumps(data[:100], sort_keys=True, default=str)  # first 100 rows
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    except Exception:
        return "hash_error"


@dataclass
class RunManifest:
    """Complete metadata for a single backtest run."""

    # Identity
    run_id: str = ""
    run_name: str = ""
    created_at: str = ""

    # Strategy
    strategy_name: str = ""
    strategy_version: str = "1.0.0"
    strategy_params: dict[str, Any] = field(default_factory=dict)

    # Data
    data_version: str = ""
    data_hash: str = ""
    data_start: str = ""
    data_end: str = ""
    data_rows: int = 0
    symbols: list[str] = field(default_factory=list)

    # Market rules
    rules_version: str = ""
    calendar_version: str = ""
    corporate_actions_version: str = ""

    # Engine
    engine_version: str = "2.0.0"
    seed: int = 42
    initial_capital: float = 1_000_000_000

    # Runtime
    python_version: str = ""
    platform_info: str = ""
    git_commit: str = ""
    dependencies: dict[str, str] = field(default_factory=dict)

    # Config snapshot
    config: dict[str, Any] = field(default_factory=dict)

    # Results summary (filled after run)
    status: str = "pending"  # pending | running | completed | failed
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    total_trades: int = 0
    duration_seconds: float = 0.0
    error: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()
        if not self.python_version:
            self.python_version = sys.version.split()[0]
        if not self.platform_info:
            self.platform_info = platform.platform()
        if not self.git_commit:
            self.git_commit = _git_commit_hash()
        if not self.dependencies:
            self.dependencies = _dependency_versions()

    def start(self) -> None:
        """Mark run as started."""
        self.status = "running"
        self.created_at = datetime.now(UTC).isoformat()

    def complete(self, result_summary: dict[str, Any] | None = None) -> None:
        """Mark run as completed with optional result summary."""
        self.status = "completed"
        if result_summary:
            self.total_return_pct = result_summary.get("total_return_pct", 0.0)
            self.sharpe_ratio = result_summary.get("sharpe_ratio", 0.0)
            self.max_drawdown_pct = result_summary.get("max_drawdown_pct", 0.0)
            self.total_trades = result_summary.get("total_trades", 0)
            self.duration_seconds = result_summary.get("duration_seconds", 0.0)

    def fail(self, error: str) -> None:
        """Mark run as failed."""
        self.status = "failed"
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return asdict(self)

    def save(self, path: str | Path) -> None:
        """Save manifest to JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False, default=str)
        logger.info("Run manifest saved: %s", p)

    @classmethod
    def load(cls, path: str | Path) -> RunManifest:
        """Load manifest from JSON file."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def fingerprint(self) -> str:
        """Generate a unique fingerprint for this run configuration.

        Two runs with the same fingerprint should produce identical results.
        """
        fp_data = {
            "strategy": self.strategy_name,
            "params": self.strategy_params,
            "data_hash": self.data_hash,
            "rules_version": self.rules_version,
            "seed": self.seed,
            "capital": self.initial_capital,
            "config": self.config,
        }
        content = json.dumps(fp_data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()[:24]

    def summary_line(self) -> str:
        """One-line summary for logging."""
        return (
            f"[{self.run_id}] {self.strategy_name} | "
            f"Return={self.total_return_pct:+.2f}% Sharpe={self.sharpe_ratio:.2f} "
            f"MaxDD={self.max_drawdown_pct:.2f}% Trades={self.total_trades} "
            f"Duration={self.duration_seconds:.1f}s"
        )
