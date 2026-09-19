/**
 * Unit tests for fund-nav pure helpers (بدون رندر کامپوننت).
 */

import { describe, expect, it } from "vitest";
import {
  DIFF_LABELS,
  QUALITY_LABELS,
  diffTone,
  formatBps,
  formatNav,
  hasOpenBreach,
  labelOf,
  qualityTone,
  referenceTone,
  type FundNavDashboard,
} from "@/lib/fund-nav";

describe("fund-nav helpers", () => {
  it("maps quality to tone", () => {
    expect(qualityTone("COMPLETE")).toBe("pos");
    expect(qualityTone("ESTIMATED")).toBe("warn");
    expect(qualityTone("PARTIAL")).toBe("warn");
    expect(qualityTone("BLOCKED")).toBe("neg");
    expect(qualityTone(undefined)).toBe("default");
  });

  it("maps diff and reference to tone", () => {
    expect(diffTone("MATCHED")).toBe("pos");
    expect(diffTone("WARNING")).toBe("warn");
    expect(diffTone("BREACH")).toBe("neg");
    expect(referenceTone("VALID")).toBe("pos");
    expect(referenceTone("STALE")).toBe("warn");
    expect(referenceTone("INVALID")).toBe("neg");
  });

  it("formats bps and NAV with sign and Persian separators", () => {
    expect(formatBps(12.345)).toBe("+12.35 bps");
    expect(formatBps(-4.05)).toBe("-4.05 bps");
    expect(formatBps(null)).toBe("—");
    expect(formatNav(1234567)).not.toBe("—");
    expect(formatNav(null)).toBe("—");
  });

  it("labels unknown keys gracefully", () => {
    expect(labelOf(DIFF_LABELS, "BREACH")).toBe("مغایرت");
    expect(labelOf(QUALITY_LABELS, "UNKNOWN")).toBe("UNKNOWN");
    expect(labelOf(QUALITY_LABELS, null)).toBe("—");
  });

  it("detects open breaches", () => {
    const base: FundNavDashboard = {
      fund_id: "tse:آگاس",
      latest_run: null,
      recent_runs: [],
      latest_reconciliation: null,
      reconciliation_history: [],
      open_breaks: [],
      engine_version: "test",
    };
    expect(hasOpenBreach(base)).toBe(false);
    expect(
      hasOpenBreach({
        ...base,
        open_breaks: [
          {
            break_id: 1,
            fund_id: "tse:آگاس",
            recon_run_id: 1,
            lifecycle: "OPEN",
            severity: "BREACH",
            owner: null,
            opened_at: null,
            resolved_at: null,
            sla_due_at: null,
            notes: null,
          },
        ],
      })
    ).toBe(true);
    expect(
      hasOpenBreach({
        ...base,
        open_breaks: [
          {
            break_id: 2,
            fund_id: "tse:آگاس",
            recon_run_id: 2,
            lifecycle: "RESOLVED",
            severity: "WARNING",
            owner: null,
            opened_at: null,
            resolved_at: null,
            sla_due_at: null,
            notes: null,
          },
        ],
      })
    ).toBe(false);
  });
});
