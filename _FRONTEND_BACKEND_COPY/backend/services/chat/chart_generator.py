"""ChartGenerator — Generate charts for chat responses (Level 12).

Creates:
- Comparison bar charts for multi-symbol analysis
- Score radar charts
- Trend line charts

Returns base64-encoded PNG images or text-based chart fallback.
Uses matplotlib when available with cross-platform font handling.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import platform
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class ChartGenerator:
    """Generate charts using matplotlib, with text-based fallback."""

    def __init__(self):
        self._plt = None
        self._matplotlib_available = False
        self._try_import()

    def _try_import(self):
        """Try to import matplotlib (cross-platform)."""
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.font_manager as fm
            import matplotlib.pyplot as plt

            self._plt = plt
            self._fm = fm
            self._matplotlib_available = True
            logger.info("matplotlib available for chart generation")
        except ImportError:
            logger.info("matplotlib not available — using text-based chart fallback")
            self._matplotlib_available = False

    def _get_persian_font(self):
        """Get a Persian-compatible font for matplotlib (cross-platform)."""
        if not self._matplotlib_available or self._fm is None:
            return None

        # Try common Persian font names
        font_names = ["Vazir", "IRANSans", "Tahoma", "Arial", "DejaVu Sans"]

        for name in font_names:
            try:
                # Try to find font by name (cross-platform)
                font_path = self._fm.findfont(name, fallback_to_default=False)
                if font_path:
                    return self._fm.FontProperties(fname=font_path)
            except Exception:
                continue

        # Fallback: try common system paths
        system = platform.system()
        common_paths = []

        if system == "Windows":
            win_dir = os.environ.get("WINDIR", "C:\\Windows")
            common_paths = [
                os.path.join(win_dir, "Fonts", "Tahoma.ttf"),
                os.path.join(win_dir, "Fonts", "Arial.ttf"),
                os.path.join(win_dir, "Fonts", "Vazir.ttf"),
            ]
        elif system == "Linux":
            common_paths = [
                "/usr/share/fonts/truetype/vazir/Vazir.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
        elif system == "Darwin":  # macOS
            common_paths = [
                "/Library/Fonts/Arial.ttf",
                "/Library/Fonts/Tahoma.ttf",
            ]

        for path in common_paths:
            if os.path.exists(path):
                try:
                    return self._fm.FontProperties(fname=path)
                except Exception:
                    continue

        return None

    def generate_comparison_chart(self, symbols: list[str], scores_dict: dict[str, dict[str, float]]) -> dict[str, Any]:
        """Generate comparison chart for multiple symbols.

        Returns dict with base64 image or text-based chart fallback.
        """
        if not symbols or not scores_dict:
            return {"error": "No data for chart"}

        if self._matplotlib_available:
            try:
                return self._generate_matplotlib_chart(symbols, scores_dict)
            except Exception as e:
                logger.warning("matplotlib chart failed: %s", e)

        return self._generate_text_chart(symbols, scores_dict)

    def _generate_matplotlib_chart(
        self, symbols: list[str], scores_dict: dict[str, dict[str, float]]
    ) -> dict[str, Any]:
        """Generate PNG chart with matplotlib."""
        plt = self._plt

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # Try Persian font
        font_prop = self._get_persian_font()
        if font_prop:
            plt.rcParams["font.family"] = font_prop.get_name()

        # Chart 1: SMC Scores (bar chart)
        ax1 = axes[0]
        scores = [scores_dict[s].get("smc_score", 0) for s in symbols]
        bars = ax1.bar(symbols, scores, color=["#4CAF50" if s > 0.5 else "#FFC107" for s in scores])
        ax1.set_title("SMC Score Comparison", fontsize=12, fontweight="bold")
        ax1.set_ylabel("Score", fontsize=10)
        ax1.set_ylim(0, 1)
        ax1.axhline(y=0.5, color="red", linestyle="--", alpha=0.5, label="Threshold (0.5)")
        ax1.legend()

        for bar, score in zip(bars, scores, strict=False):
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.02,
                f"{score:.2f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )

        # Chart 2: Sub-scores (grouped bar)
        ax2 = axes[1]
        sub_keys = ["accumulation", "absorption", "breakout_readiness", "float_lock"]
        x = np.arange(len(symbols))
        width = 0.2
        colors = ["#2196F3", "#FF9800", "#9C27B0", "#009688"]

        for i, key in enumerate(sub_keys):
            values = [scores_dict[s].get(key, 0) for s in symbols]
            ax2.bar(x + i * width, values, width, label=key, color=colors[i])

        ax2.set_title("Sub-Score Comparison", fontsize=12, fontweight="bold")
        ax2.set_xticks(x + width * 1.5)
        ax2.set_xticklabels(symbols)
        ax2.set_ylabel("Score", fontsize=10)
        ax2.set_ylim(0, 1)
        ax2.legend(loc="upper right", fontsize=8)

        plt.tight_layout()

        # Convert to base64
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode("utf-8")

        return {
            "type": "image",
            "format": "png",
            "base64": img_base64,
            "width": 1400,
            "height": 500,
        }

    def _generate_text_chart(self, symbols: list[str], scores_dict: dict[str, dict[str, float]]) -> dict[str, Any]:
        """Generate text-based chart (fallback)."""
        lines = ["📊 **Score Comparison (Text Chart)**", ""]

        # SMC Score bar
        lines.append("SMC Score:")
        for sym in symbols:
            score = scores_dict[sym].get("smc_score", 0)
            bar_len = int(score * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            emoji = "🟢" if score >= 0.6 else "🟡" if score >= 0.4 else "🔴"
            lines.append(f"  {emoji} {sym:8s}: {bar} {score:.2f}")

        # Sub-scores table
        lines.append("")
        lines.append("Sub-Scores:")
        header = f"  {'Symbol':8s} | {'ACC':6s} | {'ABS':6s} | {'BR':6s} | {'FL':6s}"
        lines.append(header)
        lines.append("  " + "-" * len(header))
        for sym in symbols:
            s = scores_dict[sym]
            acc = s.get("accumulation", 0)
            abs_val = s.get("absorption", 0)
            br = s.get("breakout_readiness", 0)
            fl = s.get("float_lock", 0)
            lines.append(f"  {sym:8s} | {acc:.3f} | {abs_val:.3f} | {br:.3f} | {fl:.3f}")

        return {
            "type": "text",
            "content": "\n".join(lines),
            "width": 60,
            "height": len(lines) + 2,
        }

    def generate_text_chart(
        self, symbols: list[str], score_key: str = "smc_score", scores_dict: dict[str, dict[str, float]] | None = None
    ) -> str:
        """Generate a simple text-based bar chart."""
        if scores_dict is None:
            return ""

        lines = []
        max_len = max(len(s) for s in symbols) if symbols else 1

        for sym in symbols:
            score = scores_dict.get(sym, {}).get(score_key, 0)
            bar_len = int(score * 15)
            bar = "█" * bar_len
            lines.append(f"  {sym:>{max_len}s}: {bar} {score:.2f}")

        return "\n".join(lines)
