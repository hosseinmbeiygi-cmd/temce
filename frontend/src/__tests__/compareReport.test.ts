import { describe, it, expect } from "vitest";
import { generateCompareReportHtml, type CompareResult } from "../app/backtest/compareReport";

/** Helper to build a successful CompareResult */
function successResult(overrides: Partial<CompareResult> = {}): CompareResult {
  return {
    strategy: "test_strategy",
    run_id: "run-1",
    status: "completed",
    metrics: {
      total_return_pct: 12.5,
      sharpe_ratio: 1.8,
      win_rate: 65,
      max_drawdown_pct: -8.2,
      total_trades: 42,
      annualized_return_pct: 24.0,
    },
    ...overrides,
  };
}

/** Helper to build a failed CompareResult */
function failedResult(overrides: Partial<CompareResult> & { error?: string } = {}): CompareResult {
  const { error, ...rest } = overrides;
  return {
    strategy: "broken_strategy",
    run_id: "run-fail",
    status: "failed",
    error: error ?? "Division by zero",
    ...rest,
  };
}

const defaultParams = {
  snapshotSymbol: "فولاد",
  displaySymbol: "فولاد",
  results: [] as CompareResult[],
  best: null as string | null,
  worst: null as string | null,
};

// ═══════════════════════════════════════════════════════════════
describe("generateCompareReportHtml", () => {
  // ── Edge case: empty results array ──
  describe("empty results", () => {
    it("returns a valid HTML document even with no results", () => {
      const html = generateCompareReportHtml({ ...defaultParams, results: [] });

      expect(html).toContain("<!DOCTYPE html>");
      expect(html).toContain("<html dir=\"rtl\" lang=\"fa\">");
      expect(html).toContain("<title>📊 گزارش مقایسه استراتژی‌ها — فولاد</title>");
      expect(html).toContain("</html>");
    });

    it("shows zero for all stats when results is empty", () => {
      const html = generateCompareReportHtml({ ...defaultParams, results: [] });

      // All three stat cards show 0: کل, موفق, ناموفق
      expect(html).toContain('class="value" style="color:#e2e8f0">0<');
      expect(html).toContain('class="value green">0<');
      expect(html).toContain('class="value red">0<');
    });

    it("shows '—' for best/worst return when no completed strategies", () => {
      const html = generateCompareReportHtml({ ...defaultParams, results: [] });

      expect(html).toContain("—"); // em-dash for missing returns
    });

    it("displays the SVG fallback message when no completed strategies", () => {
      const html = generateCompareReportHtml({ ...defaultParams, results: [] });

      expect(html).toContain("هیچ استراتژی موفقی برای نمایش نمودار وجود ندارد");
    });

    it("does NOT output SVG chart elements when hasCompleted is false", () => {
      const html = generateCompareReportHtml({ ...defaultParams, results: [] });

      expect(html).not.toContain("<svg ");
      expect(html).not.toContain("viewBox");
    });
  });

  // ── Edge case: all strategies failed ──
  describe("all strategies failed", () => {
    const allFailed: CompareResult[] = [
      failedResult({ strategy: "strat_a", error: "timeout" }),
      failedResult({ strategy: "strat_b", error: "no data" }),
      failedResult({ strategy: "strat_c" }),
    ];

    it("shows correct failed count and zero completed", () => {
      const html = generateCompareReportHtml({ ...defaultParams, results: allFailed });

      // total = 3, failed = 3, completed = 0
      expect(html).toContain("❌ timeout");
      expect(html).toContain("❌ no data");
      // Third failed result uses the default error: "Division by zero"
      expect(html).toContain("❌ Division by zero");
    });

    it("shows all failed rows with opacity styling", () => {
      const html = generateCompareReportHtml({ ...defaultParams, results: allFailed });

      expect(html).toContain('style="opacity:0.5"');
      expect(html).toContain("strat_a");
      expect(html).toContain("strat_b");
      expect(html).toContain("strat_c");
    });

    it("shows SVG fallback text instead of chart", () => {
      const html = generateCompareReportHtml({ ...defaultParams, results: allFailed });

      expect(html).toContain("هیچ استراتژی موفقی برای نمایش نمودار وجود ندارد");
      expect(html).not.toContain("<svg ");
    });
  });

  // ── Normal case: mixed success/failure with SVG ──
  describe("mixed success and failure", () => {
    const results: CompareResult[] = [
      successResult({ strategy: "SMA Cross", metrics: { total_return_pct: 25.0, sharpe_ratio: 2.1, win_rate: 70, max_drawdown_pct: -5.0, total_trades: 100 } }),
      successResult({ strategy: "RSI Reversal", metrics: { total_return_pct: -8.5, sharpe_ratio: -0.5, win_rate: 40, max_drawdown_pct: -15.0, total_trades: 80 } }),
      successResult({ strategy: "BB Squeeze", metrics: { total_return_pct: 15.0, sharpe_ratio: 1.5, win_rate: 55, max_drawdown_pct: -10.0, total_trades: 60 } }),
      failedResult({ strategy: "Broken MACD" }),
    ];
    const params = { ...defaultParams, results, best: "SMA Cross", worst: "RSI Reversal" };

    it("includes the SVG chart section", () => {
      const html = generateCompareReportHtml(params);

      expect(html).toContain("<svg ");
      expect(html).toContain("viewBox=\"0 0");
      expect(html).toContain("</svg>");
    });

    it("includes bar chart bars for each completed strategy", () => {
      const html = generateCompareReportHtml(params);

      // Each bar row is a <tr> with the strategy name
      expect(html).toContain("SMA Cross");
      expect(html).toContain("RSI Reversal");
      expect(html).toContain("BB Squeeze");
    });

    it("includes the failed row for broken strategies", () => {
      const html = generateCompareReportHtml(params);

      expect(html).toContain("Broken MACD");
      expect(html).toContain("❌");
    });

    it("shows correct stats: 4 total, 3 completed, 1 failed", () => {
      const html = generateCompareReportHtml(params);

      expect(html).toContain('class="value" style="color:#e2e8f0">4<'); // total
      expect(html).toContain('class="value green">3<'); // completed
      expect(html).toContain('class="value red">1<'); // failed
    });

    it("shows the emoji trophy for best strategy", () => {
      const html = generateCompareReportHtml(params);

      expect(html).toContain("🏆");
    });

    it("shows best and worst badges in the header", () => {
      const html = generateCompareReportHtml(params);

      expect(html).toContain('class="best-badge"');
      expect(html).toContain("🏆 بهترین: SMA Cross");
      expect(html).toContain('class="worst-badge"');
      expect(html).toContain("🫤 بدترین: RSI Reversal");
    });

    it("does NOT show badges when best/worst are null", () => {
      const noBadgesHtml = generateCompareReportHtml({ ...defaultParams, results: [successResult()], best: null, worst: null });

      // "best-badge" appears in CSS but the HTML badge element should not be present
      expect(noBadgesHtml).not.toContain('class="best-badge"');
      expect(noBadgesHtml).not.toContain('class="worst-badge"');
    });

    it("includes positive return values with + prefix", () => {
      const html = generateCompareReportHtml(params);

      expect(html).toContain("+25.0%");  // SMA Cross = +25.0
      expect(html).toContain("+15.0%");  // BB Squeeze = +15.0
    });

    it("includes negative return values without double sign", () => {
      const html = generateCompareReportHtml(params);

      expect(html).toContain("-8.5%");   // RSI Reversal
    });

    it("renders the footer", () => {
      const html = generateCompareReportHtml(params);

      expect(html).toContain("تولید شده توسط سامانه تحلیل بازار");
    });

    it("includes the print button", () => {
      const html = generateCompareReportHtml(params);

      expect(html).toContain("window.print()");
      expect(html).toContain("ذخیره به صورت PDF");
    });
  });

  // ── Snapshot symbol vs display symbol ──
  describe("symbol handling", () => {
    it("uses snapshotSymbol in the HTML title", () => {
      const html = generateCompareReportHtml({
        ...defaultParams,
        snapshotSymbol: "فملی",
        displaySymbol: "فولاد",
        results: [successResult()],
      });

      expect(html).toContain("<title>📊 گزارش مقایسه استراتژی‌ها — فملی</title>");
    });

    it("uses displaySymbol in the report header subtitle", () => {
      const html = generateCompareReportHtml({
        ...defaultParams,
        snapshotSymbol: "فملی",
        displaySymbol: "فولاد",
        results: [successResult()],
      });

      expect(html).toContain("نماد: فولاد");
    });
  });

  // ── Metrics edge cases ──
  describe("metrics edge cases", () => {
    it("handles missing metrics gracefully — strategy filtered out of table", () => {
      const results: CompareResult[] = [
        { strategy: "no_metrics", run_id: "r1", status: "completed" },
      ];
      const html = generateCompareReportHtml({ ...defaultParams, results });

      // Strategy with no total_return_pct is excluded from both completed and failed lists
      expect(html).toContain("هیچ استراتژی موفقی");
      expect(html).not.toContain("no_metrics");
    });

    it("handles null total_return_pct as incomplete — strategy filtered out", () => {
      const results: CompareResult[] = [
        { strategy: "null_return", run_id: "r2", status: "completed", metrics: { total_return_pct: undefined } },
      ];
      const html = generateCompareReportHtml({ ...defaultParams, results });

      // undefined total_return_pct means it's excluded from completed (and also not in failed)
      expect(html).toContain("هیچ استراتژی موفقی");
      expect(html).not.toContain("null_return");
    });

    it("handles zero total_return_pct correctly", () => {
      const results: CompareResult[] = [
        successResult({ strategy: "zero_return", metrics: { total_return_pct: 0, sharpe_ratio: 0, win_rate: 50, max_drawdown_pct: 0, total_trades: 10 } }),
      ];
      const html = generateCompareReportHtml({ ...defaultParams, results });

      // 0 != null, so it should be included
      expect(html).toContain("<svg ");
      expect(html).toContain("zero_return");
    });
  });

  // ── XSS hardening: user/API-controlled strings are HTML-escaped ──
  describe("XSS escaping", () => {
    it("escapes strategy names from the API", () => {
      const malicious = "<img src=x onerror=alert(1)>";
      const results: CompareResult[] = [successResult({ strategy: malicious })];
      const html = generateCompareReportHtml({ ...defaultParams, results });

      // Raw script/markup must not appear verbatim
      expect(html).not.toContain(malicious);
      expect(html).not.toContain("<img src=x");
      // Escaped form is present
      expect(html).toContain("&lt;img");
    });

    it("escapes error messages from failed runs", () => {
      const malicious = "</td><script>alert('xss')</script>";
      const results: CompareResult[] = [failedResult({ error: malicious })];
      const html = generateCompareReportHtml({ ...defaultParams, results });

      expect(html).not.toContain("<script>alert");
      expect(html).toContain("&lt;/td&gt;");
    });

    it("escapes symbols and best/worst labels", () => {
      const malicious = "\"><script>alert(2)</script>";
      const html = generateCompareReportHtml({
        ...defaultParams,
        snapshotSymbol: malicious,
        displaySymbol: malicious,
        best: malicious,
        worst: malicious,
        results: [successResult()],
      });

      expect(html).not.toContain("<script>alert(2)");
      expect(html).toContain("&lt;script&gt;");
    });
  });
});
