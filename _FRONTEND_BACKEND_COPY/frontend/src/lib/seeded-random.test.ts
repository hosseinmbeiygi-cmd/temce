import { describe, expect, it } from "vitest";
import { seededRandom, stringSeed } from "./seeded-random";

describe("seededRandom", () => {
  it("produces values in [0, 1)", () => {
    const rand = seededRandom(1);
    for (let i = 0; i < 1000; i++) {
      const v = rand();
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    }
  });

  it("is deterministic for the same seed", () => {
    const a = seededRandom(42);
    const b = seededRandom(42);
    for (let i = 0; i < 50; i++) {
      expect(a()).toBe(b());
    }
  });

  it("produces different sequences for different seeds", () => {
    const a = seededRandom(1);
    const b = seededRandom(2);
    const first = a();
    const second = b();
    expect(first).not.toBe(second);
  });

  it("seed 0 is treated as 1 (Numerical Recipes LCG requires non-zero)", () => {
    const r = seededRandom(0);
    // Should not infinite-loop or return NaN.
    expect(Number.isFinite(r())).toBe(true);
  });
});

describe("stringSeed", () => {
  it("returns the same seed for the same string", () => {
    expect(stringSeed("BTC-USDT")).toBe(stringSeed("BTC-USDT"));
  });

  it("returns different seeds for different strings", () => {
    expect(stringSeed("BTC-USDT")).not.toBe(stringSeed("ETH-USDT"));
  });

  it("never returns 0 (would be coerced to 1 by the LCG)", () => {
    expect(stringSeed("")).not.toBe(0);
  });
});
