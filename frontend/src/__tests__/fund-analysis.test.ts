import { describe, it, expect } from "vitest";
import {
  type Fund,
  type FundScore,
  type FundIssue,
} from "@/lib/fund-analysis";

describe("fund-analysis types", () => {
  it("FundScore has total field", () => {
    const score: FundScore = { total: 85 };
    expect(score.total).toBe(85);
  });

  it("FundIssue has required fields", () => {
    const issue: FundIssue = {
      id: 1,
      title: "Test",
      description: "Test issue",
      category: "مالی",
      priority: "A1",
      severity: 90,
      solution: "Fix it",
    };
    expect(issue.id).toBe(1);
    expect(issue.priority).toBe("A1");
  });

  it("Fund can have optional total_score", () => {
    const fund: Fund = {
      symbol: "TEST",
      name: "صندوق تست",
      isin: "IRTEST0001",
      nav: 10_000,
      nav_change: 100,
      nav_change_pct: 1.0,
      price_last: 10_000,
      price_close: 10_000,
      price_yesterday: 9_900,
      price_max: 10_200,
      price_min: 9_800,
      trade_volume: 500_000,
      trade_value: 5_000_000_000,
      trade_count: 200,
      shares_count: 10_000_000,
      base_volume: 100_000,
      market_value: 100_000_000_000,
      buy_real_volume: 200_000,
      buy_legal_volume: 100_000,
      sell_real_volume: 150_000,
      sell_legal_volume: 50_000,
      time: "12:00:00",
      total_score: 75,
    };
    expect(fund.total_score).toBe(75);
  });

  it("Fund can omit total_score", () => {
    const fund: Fund = {
      symbol: "TEST",
      name: "صندوق تست",
      isin: "IRTEST0001",
      nav: 10_000,
      nav_change: 100,
      nav_change_pct: 1.0,
      price_last: 10_000,
      price_close: 10_000,
      price_yesterday: 9_900,
      price_max: 10_200,
      price_min: 9_800,
      trade_volume: 500_000,
      trade_value: 5_000_000_000,
      trade_count: 200,
      shares_count: 10_000_000,
      base_volume: 100_000,
      market_value: 100_000_000_000,
      buy_real_volume: 200_000,
      buy_legal_volume: 100_000,
      sell_real_volume: 150_000,
      sell_legal_volume: 50_000,
      time: "12:00:00",
    };
    expect(fund.total_score).toBeUndefined();
  });
});
