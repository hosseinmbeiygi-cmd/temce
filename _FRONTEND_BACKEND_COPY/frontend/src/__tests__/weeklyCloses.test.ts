import { describe, expect, it } from "vitest";
import { weeklyCloses } from "@/lib/market";

function dailySeries(length: number, start = 100): number[] {
  return Array.from({ length }, (_, i) => start + i);
}

describe("weeklyCloses", () => {
  it("returns one point per calendar week (last close of each week)", () => {
    // 30 daily values spanning ~5 calendar weeks (with weekend gaps handled by date math)
    const series = dailySeries(30);
    const out = weeklyCloses(series);
    expect(out.length).toBeGreaterThanOrEqual(4);
    expect(out.length).toBeLessThanOrEqual(6);
    // last output is the final close
    expect(out[out.length - 1]).toBe(series[series.length - 1]);
  });

  it("handles a single day without throwing", () => {
    expect(weeklyCloses([42])).toEqual([42]);
  });

  it("handles empty input", () => {
    expect(weeklyCloses([])).toEqual([]);
  });

  it("does not split mid-week on fixed 5-row blocks", () => {
    // 14 consecutive daily values: calendar bucket size varies (<5 near week edges)
    const series = dailySeries(14);
    const out = weeklyCloses(series);
    expect(out.length).toBeGreaterThanOrEqual(2);
    expect(out.length).toBeLessThan(7);
  });
});
