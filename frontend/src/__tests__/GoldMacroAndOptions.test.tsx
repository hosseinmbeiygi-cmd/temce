import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import MacroPostureSection from "@/app/gold/components/MacroPostureSection";
import OptionsChainAnalytics, {
  sortContracts,
} from "@/app/gold/components/OptionsChainAnalytics";
import StrategyBuilder, { payoffCurve } from "@/app/gold/components/StrategyBuilder";
import type {
  MacroLiveResponse,
  OptionsChainContract,
  OptionsChainReport,
} from "@/types/gold";

const getMacroPosture = vi.fn();
const getOptionsChainAnalytics = vi.fn();
const runOptionsStrategy = vi.fn();

vi.mock("@/lib/goldApi", () => ({
  getMacroPosture: () => getMacroPosture(),
  getOptionsChainAnalytics: (params: unknown) => getOptionsChainAnalytics(params),
  runOptionsStrategy: (input: unknown) => runOptionsStrategy(input),
}));

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const macroAvailable: MacroLiveResponse = {
  available: true,
  missing: [],
  posture: {
    tips_yield: 1.85,
    dxy_index: 121.4,
    gold_trend: "up",
    real_yield_score: 0,
    real_yield_signal: "NEUTRAL",
    dxy_score: 0,
    dxy_signal: "NEUTRAL",
    trend_score: 1,
    composite_score: 1,
    posture: "BULLISH",
    inverse_correlation_expected: true,
    divergence: false,
    reasons: ["روند طلا صعودی است."],
  },
  inputs: { tips_yield: 1.85, dxy_index: 121.4, gold_trend: "up" },
  tips_staleness_seconds: 3600,
  dxy_staleness_seconds: 7200,
  trend_staleness_seconds: 60,
  high_vol_window: false,
  error: null,
};

const contract = (patch: Partial<OptionsChainContract>): OptionsChainContract => ({
  contract_key: "C1",
  option_type: "call",
  strike: 1_000_000,
  market_price: 55_000,
  days_to_expiry: 20,
  expiry: "2026-11-01",
  forward_price: 1_000_000,
  volume: 120,
  open_interest: 900,
  oi_change: 40,
  bid: 54_000,
  ask: 56_000,
  iv: 0.32,
  iv_error: null,
  iv_rank: null,
  iv_percentile: null,
  delta: 0.51,
  gamma: 0.0001,
  theta: -1200,
  vega: 800,
  rho: 12,
  is_liquid: true,
  liquidity_reasons: [],
  ...patch,
});

const chainReport: OptionsChainReport = {
  available: true,
  reason: null,
  source: "brsapi_ime_options+brsapi_ime_futures",
  commodity: "GoldBar",
  forward_price: 1_000_000,
  contracts: [
    contract({ contract_key: "C2", strike: 1_100_000, days_to_expiry: 55, iv: 0.35, delta: 0.33 }),
    contract({ contract_key: "P1", option_type: "put", strike: 950_000, days_to_expiry: 20, iv: 0.30, delta: -0.42, is_liquid: false, liquidity_reasons: ["missing_bid_ask"], bid: null, ask: null }),
    contract({ contract_key: "C1b", strike: 1_050_000, days_to_expiry: 20, iv: null, iv_error: "implied volatility did not converge", delta: null }),
  ],
  contracts_count: 3,
  skew_by_expiry: [
    {
      expiry: "2026-11-01",
      days_to_expiry: 20,
      forward_price: 1_000_000,
      put_strike: 950_000,
      put_iv: 0.30,
      call_strike: 1_050_000,
      call_iv: 0.34,
      skew: -0.04,
      reason: null,
    },
  ],
  iv_term_structure: [
    { expiry: "2026-11-01", days_to_expiry: 20, forward_price: 1_000_000, atm_strike: 1_000_000, atm_iv: 0.32, contract_key: "C1" },
    { expiry: "2026-12-05", days_to_expiry: 55, forward_price: 1_000_000, atm_strike: 1_100_000, atm_iv: 0.35, contract_key: "C2" },
  ],
  iv_available: true,
  iv_history_available: false,
  iv_history_source: "unavailable",
  iv_history_reason: "no dedicated historical IV series exists in brsapi_ime_options",
};

beforeEach(() => {
  getMacroPosture.mockReset();
  getOptionsChainAnalytics.mockReset();
  runOptionsStrategy.mockReset();
});

describe("MacroPostureSection", () => {
  it("renders real yield, DXY and the posture without inventing a DXY percentile", async () => {
    getMacroPosture.mockResolvedValue(macroAvailable);
    renderWithQuery(<MacroPostureSection />);

    await waitFor(() => expect(screen.getByText(/وضعیت: صعودی/)).toBeInTheDocument());
    expect(screen.getByText("شاخص دلار (DXY)")).toBeInTheDocument();
    expect(screen.getByText("درصدک DXY")).toBeInTheDocument();
    // DXY percentile has no history series -> must stay an em dash.
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
    expect(screen.getByText(/روند طلا صعودی است/)).toBeInTheDocument();
  });

  it("lists missing inputs instead of substituting zeros when the posture is unavailable", async () => {
    getMacroPosture.mockResolvedValue({
      ...macroAvailable,
      available: false,
      posture: null,
      missing: ["tips_yield", "dxy_index_stale"],
      inputs: {},
      error: null,
    } satisfies MacroLiveResponse);

    renderWithQuery(<MacroPostureSection />);

    await waitFor(() =>
      expect(screen.getByText(/وضعیت کلان فعلاً قابل محاسبه نیست/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/بازده واقعی ۱۰ ساله/)).toBeInTheDocument();
    expect(screen.getByText(/شاخص دلار کهنه است/)).toBeInTheDocument();
  });

  it("shows an explicit 503 state", async () => {
    getMacroPosture.mockRejectedValue(new Error("HTTP 503: Service Unavailable"));
    renderWithQuery(<MacroPostureSection />);

    // The section retries once on failure, so allow for the retry delay.
    await waitFor(
      () => expect(screen.getByTestId("macro-posture-503")).toBeInTheDocument(),
      { timeout: 4000 },
    );
  });
});

describe("OptionsChainAnalytics", () => {
  it("renders IV, delta and the term structure, and flags null IV as —", async () => {
    getOptionsChainAnalytics.mockResolvedValue(chainReport);
    renderWithQuery(<OptionsChainAnalytics />);

    await waitFor(() => expect(screen.getByTestId("iv-term-chart")).toBeInTheDocument());
    // Same Intl.NumberFormat call the component uses, so the assertion does not
    // depend on hand-typed Persian decimal separators.
    const pct = (value: number) =>
      `${value.toLocaleString("fa-IR", { maximumFractionDigits: 2, minimumFractionDigits: 2 })}٪`;
    expect(screen.getByText(pct(0.35 * 100))).toBeInTheDocument();
    // A contract whose IV did not converge keeps the reason, never a zero.
    const failedIvCell = screen.getByTitle("implied volatility did not converge");
    expect(failedIvCell.textContent).toBe("—");
    expect(screen.getByTestId("iv-history-unavailable")).toBeInTheDocument();
    expect(screen.getAllByText("کال").length).toBeGreaterThan(0);
    expect(screen.getAllByText("پوت").length).toBeGreaterThan(0);
    expect(screen.getByText("محدود")).toBeInTheDocument();
  });

  it("reports an unavailable chain instead of an empty table", async () => {
    getOptionsChainAnalytics.mockResolvedValue({
      ...chainReport,
      available: false,
      reason: "no option contracts",
      contracts: [],
      contracts_count: 0,
      iv_term_structure: [],
      skew_by_expiry: [],
    } satisfies OptionsChainReport);

    renderWithQuery(<OptionsChainAnalytics />);

    await waitFor(() =>
      expect(screen.getByText(/در دسترس نیست/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/no option contracts/)).toBeInTheDocument();
  });

  it("sorts contracts by days-to-expiry then strike", () => {
    const sorted = sortContracts(chainReport.contracts);
    expect(sorted.map((row) => row.contract_key)).toEqual(["P1", "C1b", "C2"]);
  });
});

describe("StrategyBuilder payoff", () => {
  it("computes a straddle payoff that matches leg-by-leg intrinsic value", () => {
    const legs = [
      { option_type: "call" as const, strike: 100, quantity: 1, premium: 5 },
      { option_type: "put" as const, strike: 100, quantity: 1, premium: 5 },
    ];
    // net debit = 10 -> at S=100 P&L = -10, at S=130 P&L = 30 - 10 = 20
    const curve = payoffCurve(legs, 10, 60, 140, 8);
    const at = (price: number) => curve.find((point) => Math.abs(point.price - price) < 1e-9)!.pnl;
    expect(at(100)).toBeCloseTo(-10);
    expect(at(110)).toBeCloseTo(0);
    expect(at(140)).toBeCloseTo(30);
    expect(at(60)).toBeCloseTo(30);
  });

  it("renders the payoff chart with the API's breakevens after a run", async () => {
    runOptionsStrategy.mockResolvedValue({
      net_debit: 10,
      net_credit: 0,
      breakevens: [110, 90],
      max_profit: null,
      max_loss: -10,
      max_profit_unbounded: true,
      max_loss_unbounded: false,
    });
    renderWithQuery(<StrategyBuilder />);

    await waitFor(() => expect(screen.getByTestId("run-strategy")).toBeInTheDocument());
    screen.getByTestId("run-strategy").click();

    await waitFor(() => expect(screen.getByTestId("payoff-chart")).toBeInTheDocument());
    expect(screen.getByText("نقاط سربه‌سر")).toBeInTheDocument();
  });
});
