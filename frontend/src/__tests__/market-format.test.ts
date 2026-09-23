import { describe, it, expect } from "vitest";
import { fmtInt, fmtNum, fmtPct, fmtBillion, faNum } from "@/lib/market-format";

describe("market-format — terminal number contract (Latin digits, ltr)", () => {
  it("groups integers with thousands separators", () => {
    expect(fmtInt(1234567)).toBe("1,234,567");
    expect(fmtInt(0)).toBe("0");
  });

  it("returns em-dash for non-finite inputs", () => {
    expect(fmtInt(NaN)).toBe("—");
    expect(fmtNum(Infinity)).toBe("—");
    expect(fmtPct(NaN)).toBe("—");
  });

  it("formats signed percentages and billions", () => {
    expect(fmtPct(1.25)).toBe("+1.25%");
    expect(fmtPct(-0.84)).toBe("-0.84%");
    expect(fmtBillion(24850.44)).toBe("24,850.4");
  });

  it("keeps Latin digits — never locale-dependent Persian digits", () => {
    // The whole point: rendering must not flip between machines/browsers.
    expect(fmtInt(9999)).not.toContain("۹");
    expect(fmtInt(9999)).toBe("9,999");
  });

  it("faNum converts to Persian digits only for prose contexts", () => {
    expect(faNum("1234")).toBe("۱۲۳۴");
    expect(faNum("1,234")).toBe("۱۲۳۴");
  });
});
