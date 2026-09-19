/**
 * Unit tests for fund-compliance pure helpers.
 */

import { describe, expect, it } from "vitest";
import {
  COMMITTEE_LABELS,
  TAX_TYPE_LABELS,
  circularTone,
  formatPct,
  hasCircularExposure,
  riskTone,
  type FofLatest,
} from "@/lib/fund-compliance";
import { labelOf } from "@/lib/fund-nav";

describe("fund-compliance helpers", () => {
  it("maps risk levels to tone", () => {
    expect(riskTone("LOW")).toBe("pos");
    expect(riskTone("MEDIUM")).toBe("warn");
    expect(riskTone("HIGH")).toBe("neg");
    expect(riskTone(null)).toBe("default");
  });

  it("maps circular flag to tone", () => {
    expect(circularTone(true)).toBe("neg");
    expect(circularTone(false)).toBe("pos");
  });

  it("formats percentages", () => {
    expect(formatPct(87.654)).toBe("87.7%");
    expect(formatPct(null)).toBe("—");
  });

  it("labels tax and committee types", () => {
    expect(labelOf(TAX_TYPE_LABELS, "TRANSFER_05")).toBe("مقطوع ۰.۵٪ نقل‌وانتقال");
    expect(labelOf(COMMITTEE_LABELS, "AUDIT")).toBe("کمیته حسابرسی");
  });

  it("detects circular exposure", () => {
    const base: FofLatest = {
      fund_id: "tse:آگاس",
      valuation_date: "2026-09-18",
      positions: [],
      summary: {
        total_value: 0,
        circular_value: 0,
        valued_positions: 0,
        missing_positions: 0,
        coverage_pct: 0,
      },
    };
    expect(hasCircularExposure(base)).toBe(false);
    expect(
      hasCircularExposure({
        ...base,
        positions: [
          {
            sub_fund_id: "tse:A",
            sub_nav_per_unit: 1000,
            units: 10,
            value: 10_000,
            circular_flag: true,
          },
        ],
      })
    ).toBe(true);
  });
});
