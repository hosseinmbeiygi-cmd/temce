/**
 * Tests for the threshold-alert condition contract (audit F4, 2026-11-28).
 *
 * buildAlertCondition is the exact logic the Alerts form sends to the backend —
 * kept pure in lib/alert-conditions.ts so the branch order (cross before the
 * generic "below" mapping), the RSI user threshold and the unit semantics are
 * regression-locked.
 */
import { describe, expect, it } from "vitest";

import { buildAlertCondition, thresholdMeta } from "@/lib/alert-conditions";

describe("buildAlertCondition — price alerts", () => {
  it("builds a gte price condition with the anti-spam cooldown", () => {
    const result = buildAlertCondition("price_above", "50000");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.condition).toEqual({
        threshold: 50000, operator: "gte", field: "price", cooldown_minutes: 30,
      });
    }
  });

  it("maps price_below to lte", () => {
    const result = buildAlertCondition("price_below", "40000");
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.condition.operator).toBe("lte");
  });

  it("rejects a missing or non-numeric threshold for price alerts", () => {
    expect(buildAlertCondition("price_above", "")).toEqual({ ok: false, error: "THRESHOLD_REQUIRED" });
    expect(buildAlertCondition("price_above", "abc")).toEqual({ ok: false, error: "THRESHOLD_REQUIRED" });
  });
});

describe("buildAlertCondition — volume alerts", () => {
  it("targets the cumulative daily volume field", () => {
    const result = buildAlertCondition("volume_above", "10000000");
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.condition.field).toBe("volume");
  });
});

describe("buildAlertCondition — RSI alerts (F4: user threshold honoured)", () => {
  it("rsi_oversold falls back to the historical default 30 when the input is empty", () => {
    const result = buildAlertCondition("rsi_oversold", "");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.condition).toMatchObject({ field: "rsi", operator: "lte", threshold: 30 });
    }
  });

  it("rsi_oversold honours a custom user threshold", () => {
    const result = buildAlertCondition("rsi_oversold", "25");
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.condition.threshold).toBe(25);
  });

  it("rsi_overbought falls back to 70 and maps to gte", () => {
    const result = buildAlertCondition("rsi_overbought", "");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.condition).toMatchObject({ field: "rsi", operator: "gte", threshold: 70 });
    }
  });

  it("rejects RSI thresholds outside (0, 100)", () => {
    expect(buildAlertCondition("rsi_oversold", "150")).toEqual({ ok: false, error: "RSI_RANGE" });
    expect(buildAlertCondition("rsi_overbought", "0")).toEqual({ ok: false, error: "RSI_RANGE" });
    expect(buildAlertCondition("rsi_oversold", "-5")).toEqual({ ok: false, error: "RSI_RANGE" });
  });
});

describe("buildAlertCondition — SMA cross alerts", () => {
  it("cross_above_sma is a boolean eq-1 condition and needs no user threshold", () => {
    const result = buildAlertCondition("cross_above_sma", "");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.condition).toEqual({
        field: "sma_cross_above", operator: "eq", threshold: 1, cooldown_minutes: 30,
      });
    }
  });

  it("cross_below_sma is NOT mapped to the generic price-below lte branch", () => {
    // Branch-order regression guard: "cross_below_sma" contains "below".
    const result = buildAlertCondition("cross_below_sma", "");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.condition).toEqual({
        field: "sma_cross_below", operator: "eq", threshold: 1, cooldown_minutes: 30,
      });
    }
  });
});

describe("thresholdMeta — unit disclosure (F4)", () => {
  it("price alerts declare the rial unit explicitly", () => {
    const meta = thresholdMeta("price_above");
    expect(meta.label).toContain("قیمت");
    expect(meta.hint).toContain("ریال");
  });

  it("volume alerts declare the share unit", () => {
    expect(thresholdMeta("volume_above").hint).toContain("سهم");
  });

  it("cross alerts hide the numeric input", () => {
    expect(thresholdMeta("cross_above_sma").hide).toBe(true);
    expect(thresholdMeta("cross_below_sma").hide).toBe(true);
  });

  it("unknown alert types fall back to the price meta", () => {
    expect(thresholdMeta("no_such_type")).toEqual(thresholdMeta("price_above"));
  });
});
