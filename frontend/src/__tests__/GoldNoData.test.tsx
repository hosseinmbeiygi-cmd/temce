// F3 — تصمیم NO_DATA باید «داده ناکافی» باشد، نه سبز/قرمز (قرارداد C1).
//
// سه مسیر رندر decision در این درخت مقدار ناشناخته را می‌شکست:
//   * ScoreGauge و DecisionBadge با `map[decision]` بدون fallback → TypeError
//   * analytics با ternary سه‌تایی → هر چیز ناشناخته **قرمز** می‌شد
// هر چهار مسیر حالا از یک منبع مشترک (lib/gold-decision) تغذیه می‌شوند.

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Snapshot } from "@/types/gold";

import { decisionView, isNeutralDecision } from "@/lib/gold-decision";
import GoldSummarySection from "@/app/gold/components/SummarySection";

const baseSnapshot = (scoreOverrides: Record<string, unknown>): Snapshot => ({
  snapshot_at: "2026-10-24T10:00:00Z",
  references: {
    xau_usd: 2345.67,
    usd_irt: 900000,
    aed_irt: 245000,
    aed_parity_usd: 3.6725,
    aed_gap_pct: 1.25,
    source: "brsapi",
    age_seconds: 12,
  },
  gold: {},
  coins: {},
  funds: [],
  score: {
    total: 30,
    decision: "NO_DATA",
    components: {
      bubble: 0,
      bubble_reason: "",
      nav: 0,
      nav_reason: "",
      tsetmc: 0,
      tsetmc_reason: "",
      technical: 0,
      technical_reason: "",
      parity: 0,
      parity_reason: "",
      fund_flow: 0,
      fund_flow_reason: "",
    },
    hard_stop_active: false,
    hard_stop_reason: null,
    ...scoreOverrides,
  },
  quality_flag: "partial",
});

describe("decision view (C1 / F3)", () => {
  it("renders NO_DATA as neutral no-data, never as a colored verdict", () => {
    const view = decisionView("NO_DATA");
    expect(view.label).toContain("داده ناکافی");
    expect(isNeutralDecision(view)).toBe(true);
    expect(view.cls).not.toMatch(/emerald|rose/);
  });

  it("maps an unknown or missing decision to the same neutral state", () => {
    // این دقیقاً جایی بود که analytics مقدار ناشناخته را قرمز می‌کرد.
    for (const value of ["SOMETHING_NEW", "", null, undefined]) {
      const view = decisionView(value as never);
      expect(view.cls, `برای ${String(value)} رنگ قرمز داده نشد`).not.toMatch(/rose|emerald/);
      expect(view.dot).not.toBe("#f43f5e");
    }
  });

  it("never phrases GREEN as a definite buy", () => {
    // F3: «سبز بودن هرگز خرید قطعی نشان داده نشود».
    const green = decisionView("GREEN");
    expect(green.label).not.toMatch(/ورود|خرید قطعی|بخر|قطعی/);
  });

  it("uses one shared neutral color for no-data chart dots", () => {
    expect(decisionView("NO_DATA").dot).toBe(decisionView("UNKNOWN").dot);
  });
});

describe("SummarySection with NO_DATA", () => {
  it("shows the no-data label and the data coverage percentage", () => {
    render(<GoldSummarySection snapshot={baseSnapshot({ data_coverage_pct: 42 })} />);

    expect(screen.getByText(/داده ناکافی/)).toBeInTheDocument();
    expect(screen.getByText(/پوشش داده: 42٪/)).toBeInTheDocument();
    // total همچنان عددی است (برای نمودار) پس نباید پنهان شود
    expect(screen.getByText(/30/)).toBeInTheDocument();
  });

  it("keeps the analytics-not-advice disclaimer visible", () => {
    render(<GoldSummarySection snapshot={baseSnapshot({ data_coverage_pct: 42 })} />);
    expect(screen.getByText(/ابزار تحلیلی/)).toBeInTheDocument();
  });

  it("does not tint the decision badge green or red when data is missing", () => {
    render(<GoldSummarySection snapshot={baseSnapshot({ data_coverage_pct: 10 })} />);
    const badge = screen.getByText(/داده ناکافی/).closest("span");
    expect(badge?.className ?? "").not.toMatch(/emerald|rose/);
  });

  it("still shows coverage for a colored decision so thin data is visible either way", () => {
    render(<GoldSummarySection snapshot={baseSnapshot({ decision: "GREEN", data_coverage_pct: 61 })} />);
    expect(screen.getByText(/پوشش داده: 61٪/)).toBeInTheDocument();
  });
});
