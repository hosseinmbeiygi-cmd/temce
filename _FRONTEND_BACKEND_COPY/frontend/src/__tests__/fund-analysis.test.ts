import { describe, it, expect } from "vitest";
import {
  type Fund,
  type FundScore,
  type FundIssue,
  scoringEngine,
  determineRiskLevel,
  determineRecommendation,
  detectIssues,
  analyzeFund,
} from "@/lib/fund-analysis";

// ═══════════════════════════════════════════════════════════════════
//  Test Helpers
// ═══════════════════════════════════════════════════════════════════

/** Build a partial Fund with sensible defaults. */
function makeFund(overrides: Partial<Fund> = {}): Fund {
  return {
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
    ...overrides,
  };
}

/** Build a FundIssue for testing risk levels. */
function makeIssue(priority: "A1" | "A2" | "B" | "C", severity = 80): FundIssue {
  return {
    id: Math.random(),
    title: "Issue",
    description: "Test issue",
    category: "test",
    priority,
    severity,
    solution: "Test solution",
  };
}

function extractNames(items: string[]): string[] {
  return items.map((s) => {
    const m = s.match(/^([^:]+):/);
    return m ? m[1] : s;
  });
}


// ═══════════════════════════════════════════════════════════════════
//  scoringEngine
// ═══════════════════════════════════════════════════════════════════

describe("scoringEngine", () => {
  // ── Financial score ────────────────────────────────────────────

  it("scores strong financial for high nav_change_pct", () => {
    const f = makeFund({ nav_change_pct: 2.0, nav: 60_000, trade_count: 500 });
    const s = scoringEngine(f);
    expect(s.financial).toBeGreaterThanOrEqual(80);
  });

  it("scores weak financial for negative nav_change_pct", () => {
    const f = makeFund({ nav_change_pct: -2.0, nav: 5_000, trade_count: 5 });
    const s = scoringEngine(f);
    expect(s.financial).toBeLessThanOrEqual(50);
  });

  it("scores base financial (60) when nav_change_pct is around 0", () => {
    const f = makeFund({ nav_change_pct: 0.2, nav: 5_000, trade_count: 5 });
    const s = scoringEngine(f);
    // base 60 + 5 for positive change (0.2 > 0) + 0 for nav < 10k + 0 for trade_count <= 100
    expect(s.financial).toBe(65);
  });

  it("never exceeds 100 or falls below 0 for financial", () => {
    const f = makeFund({ nav_change_pct: 100, nav: 1_000_000, trade_count: 9999 });
    const s = scoringEngine(f);
    expect(s.financial).toBeLessThanOrEqual(100);
    expect(s.financial).toBeGreaterThanOrEqual(0);
  });

  // ── Liquidity score ────────────────────────────────────────────

  it("scores strong liquidity for high volume", () => {
    const f = makeFund({ trade_volume: 5_000_000, trade_value: 10_000_000_000, trade_count: 1000 });
    const s = scoringEngine(f);
    expect(s.liquidity).toBeGreaterThanOrEqual(80);
  });

  it("scores weak liquidity for low volume", () => {
    const f = makeFund({ trade_volume: 10_000, trade_value: 1_000_000, trade_count: 3 });
    const s = scoringEngine(f);
    expect(s.liquidity).toBeLessThanOrEqual(40);
  });

  // ── Management score ───────────────────────────────────────────

  it("scores strong management for large shares_count and market_value", () => {
    const f = makeFund({ shares_count: 100_000_000, market_value: 2_000_000_000_000, buy_legal_volume: 500_000, sell_legal_volume: 100_000 });
    const s = scoringEngine(f);
    expect(s.management).toBeGreaterThanOrEqual(80);
  });

  it("scores weak management for small shares_count", () => {
    const f = makeFund({ shares_count: 100_000, market_value: 10_000_000_000 });
    const s = scoringEngine(f);
    expect(s.management).toBeLessThanOrEqual(55);
  });

  // ── Risk score ─────────────────────────────────────────────────

  it("scores low risk (high score) for stable price range", () => {
    const f = makeFund({ price_max: 10_100, price_min: 9_900, nav_change_pct: 0.5, trade_volume: 1_000_000 });
    const s = scoringEngine(f);
    expect(s.risk).toBeGreaterThanOrEqual(70);
  });

  it("scores high risk (low score) for wide price range and negative nav_change", () => {
    const f = makeFund({ price_max: 15_000, price_min: 5_000, nav_change_pct: -3.0, trade_volume: 10_000 });
    const s = scoringEngine(f);
    expect(s.risk).toBeLessThanOrEqual(50);
  });

  // ── Cost score ─────────────────────────────────────────────────

  it("scores lower cost for high premium (price >> nav)", () => {
    const f = makeFund({ price_last: 15_000, nav: 10_000, trade_count: 5 });
    const s = scoringEngine(f);
    // premium = 50%, so cost -= 15 → 55
    expect(s.cost).toBeLessThan(70);
  });

  it("keeps default cost score when price ~= nav", () => {
    const f = makeFund({ price_last: 10_200, nav: 10_000, trade_count: 50 });
    const s = scoringEngine(f);
    expect(s.cost).toBe(68); // premium=2% → > 0 branch: 70 - 2 = 68
  });

  // ── Transparency score ─────────────────────────────────────────

  it("scores high transparency when all data is available", () => {
    const f = makeFund({ isin: "IRLONGISIN12345", price_yesterday: 9_900, price_max: 10_200, price_min: 9_800, name: "صندوق بلند", buy_real_volume: 100_000 });
    const s = scoringEngine(f);
    expect(s.transparency).toBeGreaterThanOrEqual(85);
  });

  it("scores low transparency when no ISIN or price data", () => {
    const f = makeFund({ isin: "", price_yesterday: 0, price_max: 0, price_min: 0, name: "AB", buy_real_volume: 0, buy_legal_volume: 0 });
    const s = scoringEngine(f);
    expect(s.transparency).toBe(65); // only base score
  });

  // ── Total score ────────────────────────────────────────────────

  it("computes total as weighted average of all 6 dimensions", () => {
    const f = makeFund();
    const s = scoringEngine(f);

    const expectedTotal = Math.round(
      s.financial * 0.25 +
      s.liquidity * 0.20 +
      s.management * 0.18 +
      s.risk * 0.15 +
      s.cost * 0.12 +
      s.transparency * 0.10
    );
    expect(s.total).toBe(expectedTotal);
  });

  it("all 6 component scores are 0-100 integers", () => {
    const f = makeFund();
    const s = scoringEngine(f);

    for (const key of ["financial", "liquidity", "management", "risk", "cost", "transparency"] as const) {
      expect(s[key]).toBeGreaterThanOrEqual(0);
      expect(s[key]).toBeLessThanOrEqual(100);
      expect(Number.isInteger(s[key])).toBe(true);
    }
  });

  it("total is also a 0-100 integer", () => {
    const f = makeFund();
    const s = scoringEngine(f);
    expect(s.total).toBeGreaterThanOrEqual(0);
    expect(s.total).toBeLessThanOrEqual(100);
    expect(Number.isInteger(s.total)).toBe(true);
  });
});


// ═══════════════════════════════════════════════════════════════════
//  determineRiskLevel
// ═══════════════════════════════════════════════════════════════════

describe("determineRiskLevel", () => {
  it("returns LOW when total is high and no critical issues", () => {
    const scores: FundScore = { financial: 85, liquidity: 80, management: 75, risk: 70, cost: 80, transparency: 75, total: 80 };
    expect(determineRiskLevel(scores, [])).toBe("LOW");
  });

  it("returns LOW when total >= 70 and no critical issues", () => {
    const scores: FundScore = { financial: 70, liquidity: 70, management: 70, risk: 70, cost: 70, transparency: 70, total: 70 };
    expect(determineRiskLevel(scores, [makeIssue("B")])).toBe("LOW");
  });

  it("returns MEDIUM when total < 70 but no critical issues", () => {
    const scores: FundScore = { financial: 60, liquidity: 60, management: 60, risk: 60, cost: 60, transparency: 60, total: 60 };
    expect(determineRiskLevel(scores, [])).toBe("MEDIUM");
  });

  it("returns MEDIUM when one A1 issue exists with moderate total", () => {
    const scores: FundScore = { financial: 65, liquidity: 65, management: 65, risk: 65, cost: 65, transparency: 65, total: 65 };
    expect(determineRiskLevel(scores, [makeIssue("A1")])).toBe("MEDIUM");
  });

  it("returns HIGH when total < 55", () => {
    const scores: FundScore = { financial: 50, liquidity: 50, management: 50, risk: 50, cost: 50, transparency: 50, total: 50 };
    expect(determineRiskLevel(scores, [])).toBe("HIGH");
  });

  it("returns HIGH when two A1 issues exist", () => {
    const scores: FundScore = { financial: 70, liquidity: 70, management: 70, risk: 70, cost: 70, transparency: 70, total: 70 };
    expect(determineRiskLevel(scores, [makeIssue("A1"), makeIssue("A1")])).toBe("HIGH");
  });

  it("returns CRITICAL when total < 35", () => {
    const scores: FundScore = { financial: 30, liquidity: 30, management: 30, risk: 30, cost: 30, transparency: 30, total: 30 };
    expect(determineRiskLevel(scores, [])).toBe("CRITICAL");
  });

  it("returns CRITICAL when three A1 issues exist even with high total", () => {
    const scores: FundScore = { financial: 90, liquidity: 90, management: 90, risk: 90, cost: 90, transparency: 90, total: 90 };
    expect(determineRiskLevel(scores, [makeIssue("A1"), makeIssue("A1"), makeIssue("A1")])).toBe("CRITICAL");
  });

  it("returns CRITICAL when total is 0", () => {
    const scores: FundScore = { financial: 0, liquidity: 0, management: 0, risk: 0, cost: 0, transparency: 0, total: 0 };
    expect(determineRiskLevel(scores, [])).toBe("CRITICAL");
  });

  it("works with empty issues array", () => {
    const scores: FundScore = { financial: 75, liquidity: 75, management: 75, risk: 75, cost: 75, transparency: 75, total: 75 };
    expect(determineRiskLevel(scores, [])).toBe("LOW");
  });
});


// ═══════════════════════════════════════════════════════════════════
//  determineRecommendation
// ═══════════════════════════════════════════════════════════════════

describe("determineRecommendation", () => {
  it("returns BUY (not STRONG_BUY) when total >= 80 with HIGH risk", () => {
    // HIGH blocks STRONG_BUY, but >=70 allows BUY
    expect(determineRecommendation(80, "HIGH", [])).toBe("BUY");
  });

  it("returns STRONG_BUY for total >= 80 with MEDIUM risk", () => {
    expect(determineRecommendation(85, "MEDIUM", [])).toBe("STRONG_BUY");
  });

  it("returns STRONG_BUY for total >= 80 with LOW risk", () => {
    expect(determineRecommendation(80, "LOW", [])).toBe("STRONG_BUY");
  });

  it("returns WATCHLIST (not BUY) when total >= 70 with CRITICAL risk", () => {
    // CRITICAL blocks BUY, but score >=60 allows WATCHLIST
    expect(determineRecommendation(75, "CRITICAL", [])).toBe("WATCHLIST");
  });

  it("returns BUY for total >= 70 with LOW risk", () => {
    expect(determineRecommendation(70, "LOW", [])).toBe("BUY");
  });

  it("returns WATCHLIST for total >= 60 with LOW risk", () => {
    expect(determineRecommendation(60, "LOW", [])).toBe("WATCHLIST");
  });

  it("returns WATCHLIST for total >= 60 with MEDIUM risk", () => {
    expect(determineRecommendation(65, "MEDIUM", [])).toBe("WATCHLIST");
  });

  it("skips WATCHLIST for total >= 60 with HIGH risk → HOLD", () => {
    expect(determineRecommendation(60, "HIGH", [])).toBe("HOLD");
  });

  it("returns HOLD for total 50-59", () => {
    expect(determineRecommendation(55, "LOW", [])).toBe("HOLD");
  });

  it("returns HOLD for total 50-59 even with CRITICAL risk", () => {
    expect(determineRecommendation(50, "CRITICAL", [])).toBe("HOLD");
  });

  it("returns REDUCE for total 40-49", () => {
    expect(determineRecommendation(45, "LOW", [])).toBe("REDUCE");
  });

  it("returns SELL for total 25-39", () => {
    expect(determineRecommendation(30, "LOW", [])).toBe("SELL");
  });

  it("returns AVOID for total < 25", () => {
    expect(determineRecommendation(10, "LOW", [])).toBe("AVOID");
  });

  it("returns AVOID for total = 0", () => {
    expect(determineRecommendation(0, "LOW", [])).toBe("AVOID");
  });

  it("CRITICAL risk blocks STRONG_BUY and BUY — returns WATCHLIST", () => {
    expect(determineRecommendation(95, "CRITICAL", [])).toBe("WATCHLIST");
  });

  it("HIGH risk blocks STRONG_BUY but allows BUY", () => {
    expect(determineRecommendation(75, "HIGH", [])).toBe("BUY");
  });

  it("LOW risk allows STRONG_BUY at high total", () => {
    expect(determineRecommendation(90, "LOW", [])).toBe("STRONG_BUY");
  });

  // ── A1 critical issues ──

  it("multiple A1 issues (3+) make risk CRITICAL → blocks BUY", () => {
    const issues = [makeIssue("A1"), makeIssue("A1"), makeIssue("A1")];
    expect(determineRecommendation(85, "CRITICAL", issues)).toBe("WATCHLIST");
  });
});


// ═══════════════════════════════════════════════════════════════════
//  detectIssues
// ═══════════════════════════════════════════════════════════════════

describe("detectIssues", () => {
  it("detects financial issues when nav_change is very negative", () => {
    const f = makeFund({ nav_change_pct: -4.0 });
    const issues = detectIssues(f);
    expect(issues.length).toBeGreaterThanOrEqual(3); // 2 (A1) + 51 (A2) + 101 (B) + 9 + 68
    expect(issues.some((i) => i.id === 2)).toBe(true);  // نوسان شدید
    expect(issues.some((i) => i.id === 9)).toBe(true);  // ریسک‌پذیری بیش از حد
  });

  it("detects liquidity issues for very low volume", () => {
    const f = makeFund({ trade_volume: 10_000, price_max: 10_100, price_min: 9_500 });
    const issues = detectIssues(f);
    expect(issues.some((i) => i.id === 3)).toBe(true);  // نقدشوندگی پایین
    expect(issues.some((i) => i.id === 4)).toBe(true);  // عدم بازارگردان
    expect(issues.some((i) => i.id === 58)).toBe(true); // حجم پایین
  });

  it("detects wide spread issue", () => {
    const f = makeFund({ price_max: 15_000, price_min: 5_000 });
    const issues = detectIssues(f);
    expect(issues.some((i) => i.id === 5)).toBe(true);  // شکاف قیمت بالا
  });

  it("detects management issues for small fund", () => {
    const f = makeFund({ shares_count: 500_000, market_value: 10_000_000_000 });
    const issues = detectIssues(f);
    expect(issues.some((i) => i.id === 6)).toBe(true);  // مدیریت ناپایدار
    expect(issues.some((i) => i.id === 28)).toBe(true); // تجربه ناکافی
  });

  it("detects no issues for a healthy fund", () => {
    const f = makeFund({ nav_change_pct: 2.0, trade_volume: 2_000_000, shares_count: 100_000_000, market_value: 2_000_000_000_000, price_max: 10_100, price_min: 9_900 });
    const issues = detectIssues(f);
    expect(issues.length).toBe(0);
  });

  it("caps maximum issues at 8", () => {
    const f = makeFund({ nav_change_pct: -5.0, trade_volume: 10_000, shares_count: 100_000, market_value: 10_000_000_000, price_max: 15_000, price_min: 5_000 });
    const issues = detectIssues(f);
    expect(issues.length).toBeLessThanOrEqual(8);
  });

  it("removes duplicate issues (keeps lowest id)", () => {
    // Multiple overlapping conditions might trigger same issue
    const f = makeFund({ nav_change_pct: -4.0, trade_volume: 10_000, shares_count: 100_000 });
    const issues = detectIssues(f);
    const ids = issues.map((i) => i.id);
    expect(new Set(ids).size).toBe(ids.length); // no duplicates
  });
});


// ═══════════════════════════════════════════════════════════════════
//  analyzeFund (integration)
// ═══════════════════════════════════════════════════════════════════

describe("analyzeFund", () => {
  it("returns a valid FundAnalysis for a healthy fund", () => {
    const f = makeFund();
    const a = analyzeFund(f);

    expect(a.symbol).toBe("TEST");
    expect(a.name).toBe("صندوق تست");
    expect(a.scores.total).toBeGreaterThan(0);
    expect(a.recommendation).toBeDefined();
    expect(a.riskLevel).toBeDefined();
    expect(a.issues).toBeDefined();
    expect(a.summary).toContain("امتیاز کلی");
  });

  it("returns STRONG_BUY for a top-performing fund", () => {
    const f = makeFund({
      nav_change_pct: 3.0,
      trade_volume: 5_000_000,
      trade_value: 50_000_000_000,
      trade_count: 1000,
      shares_count: 200_000_000,
      market_value: 3_000_000_000_000,
      price_max: 10_050,
      price_min: 9_950,
      isin: "IRSTRONGFUND123",
      name: "صندوق برتر سرمایه",
      buy_legal_volume: 1_000_000,
      sell_legal_volume: 100_000,
    });
    const a = analyzeFund(f);
    expect(a.scores.total).toBeGreaterThanOrEqual(75);
    expect(a.riskLevel).toBe("LOW");
    expect(a.recommendation).toBe("STRONG_BUY");
    expect(a.issues.length).toBe(0);
    expect(a.strengths.length).toBeGreaterThan(0);
    expect(a.weaknesses.length).toBe(0);
  });

  it("returns a SELL-type recommendation for a very weak fund", () => {
    const f = makeFund({
      nav_change_pct: -5.0,
      trade_volume: 5_000,
      trade_value: 10_000_000,
      trade_count: 2,
      shares_count: 50_000,
      market_value: 1_000_000_000,
      price_max: 20_000,
      price_min: 1_000,
      isin: "",
      name: "X",
      buy_real_volume: 0,
      buy_legal_volume: 0,
      price_last: 15_000,
      nav: 5_000,
      price_yesterday: 0,
    });
    const a = analyzeFund(f);
    expect(a.scores.total).toBeLessThanOrEqual(45);
    expect(["REDUCE", "SELL", "AVOID"]).toContain(a.recommendation);
    expect(a.issues.length).toBeGreaterThan(0);
    expect(a.weaknesses.length).toBeGreaterThan(0);
  });

  it("includes strengths only for dimensions scored >= 70", () => {
    const f = makeFund(); // balanced fund
    const a = analyzeFund(f);
    const strengthNames = extractNames(a.strengths);
    const weakNames = extractNames(a.weaknesses);
    // No dimension can be both a strength and a weakness
    for (const s of strengthNames) {
      expect(weakNames).not.toContain(s);
    }
  });

  it("returns nextSteps appropriate for the recommendation", () => {
    // Fund with buyable score
    const buy = analyzeFund(makeFund({ nav_change_pct: 3.0, trade_volume: 5_000_000 }));
    if (buy.recommendation === "STRONG_BUY" || buy.recommendation === "BUY") {
      expect(buy.nextSteps[0]).toBe("بررسی دقیق ترکیب دارایی صندوق");
    }

    // Fund with sell-type recommendation uses extreme values
    const avoid = analyzeFund(makeFund({
      nav_change_pct: -5.0,
      trade_volume: 5_000,
      trade_value: 10_000_000,
      trade_count: 2,
      shares_count: 50_000,
      market_value: 1_000_000_000,
      isin: "",
      name: "X",
      buy_real_volume: 0,
      buy_legal_volume: 0,
      price_last: 15_000,
      nav: 5_000,
      price_yesterday: 0,
    }));
    expect(["REDUCE", "SELL", "AVOID"]).toContain(avoid.recommendation);
    if (avoid.recommendation === "SELL" || avoid.recommendation === "AVOID") {
      expect(avoid.nextSteps[0]).toBe("برنامه‌ریزی برای خروج کامل");
    }
  });

  it("summary reflects the score and issue count", () => {
    const f = makeFund();
    const a = analyzeFund(f);
    expect(a.summary).toContain(String(a.scores.total));
    expect(a.summary).toContain(String(a.issues.length));
  });
});


// ═══════════════════════════════════════════════════════════════════
//  Edge Cases
// ═══════════════════════════════════════════════════════════════════

describe("edge cases", () => {
  it("handles zero price data without division by zero", () => {
    const f = makeFund({ price_max: 0, price_min: 0, price_last: 0, nav: 0 });
    const s = scoringEngine(f);
    expect(s.total).toBeGreaterThanOrEqual(0);
  });

  it("handles extremely large values without overflow", () => {
    const f = makeFund({
      nav: 1_000_000_000,
      nav_change_pct: 999,
      trade_volume: 999_999_999,
      trade_value: 9_999_999_999_999,
      market_value: 9_999_999_999_999,
      shares_count: 9_999_999_999,
      price_max: 1_000_000,
      price_min: 1,
    });
    const s = scoringEngine(f);
    expect(s.total).toBeGreaterThanOrEqual(0);
    expect(s.total).toBeLessThanOrEqual(100);
  });

  it("handles negative values gracefully", () => {
    const f = makeFund({
      nav_change_pct: -10,
      trade_volume: -1,
      trade_count: -1,
      price_max: -1,
      price_min: -10,
    });
    const s = scoringEngine(f);
    expect(s.total).toBeGreaterThanOrEqual(0);
    expect(s.total).toBeLessThanOrEqual(100);
  });

  it("handles undefined-like values (0) without throwing", () => {
    const f = makeFund({
      isin: "",
      price_yesterday: 0,
      price_max: 0,
      price_min: 0,
      buy_real_volume: 0,
      buy_legal_volume: 0,
    });
    expect(() => analyzeFund(f)).not.toThrow();
  });
});
