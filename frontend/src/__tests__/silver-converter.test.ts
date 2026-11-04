// SIL-05 — مبدل گرم/انس/ریال نباید ورودی نامعتبر را صفر تلقی کند.
import { describe, expect, it } from "vitest";
import { gramsToUsd, parseGramsInput, usdToIrr } from "@/lib/silver-converter";

describe("parseGramsInput", () => {
  it("accepts a positive decimal, with optional thousands separators", () => {
    expect(parseGramsInput("2.5")).toBe(2.5);
    expect(parseGramsInput(" 1,000 ")).toBe(1000);
  });

  it.each(["", "abc", "0", "-3", null, undefined])("returns null for %s", (raw) => {
    expect(parseGramsInput(raw as string | null | undefined)).toBeNull();
  });
});

describe("gramsToUsd / usdToIrr", () => {
  it("computes the troy-ounce conversion for a valid input", () => {
    expect(gramsToUsd(31.1035, 30)).toBeCloseTo(30, 10);
  });

  it("propagates unknown inputs instead of inventing zero", () => {
    expect(gramsToUsd(null, 30)).toBeNull();
    expect(gramsToUsd(1, null)).toBeNull();
    expect(usdToIrr(null, 600_000)).toBeNull();
    expect(usdToIrr(30, null)).toBeNull();
  });
});
