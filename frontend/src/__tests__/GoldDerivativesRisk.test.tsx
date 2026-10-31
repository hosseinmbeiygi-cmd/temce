import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

const mocks = vi.hoisted(() => ({
  getGoldRiskScenarios: vi.fn(),
  runGoldRiskStress: vi.fn(),
  getOptionsChainAnalytics: vi.fn(),
  runOptionsStrategy: vi.fn(),
}));

vi.mock("@/lib/goldApi", () => mocks);

import GoldDerivativesRiskPage from "@/app/gold/options/page";

const shocks = {
  xau_usd_pct: -0.18,
  usd_irr_pct: 0.25,
  local_premium_pct: -0.12,
  fund_discount_pct: -0.1,
  volatility_points: 0.2,
  liquidity_haircut_pct: 0.15,
};

const scenarioCatalogue = [
  {
    scenario_id: "black_swan",
    name_fa: "شوک سیاه",
    name_en: "Black swan",
    description_fa: "ریزش اونس، جهش دلار و قفل نقدشوندگی.",
    shocks,
  },
  {
    scenario_id: "usd_spike",
    name_fa: "جهش دلار",
    name_en: "USD spike",
    description_fa: "افزایش دلار آزاد با انتقال محدود به طلای داخلی.",
    shocks: {
      xau_usd_pct: 0,
      usd_irr_pct: 0.15,
      local_premium_pct: 0.02,
      fund_discount_pct: 0,
      volatility_points: 0.03,
      liquidity_haircut_pct: 0,
    },
  },
];

const coinPosition = {
  symbol: "IR_COIN_EMAMI",
  asset_type: "coin" as const,
  direction: "long" as const,
  exposure_irr: 500_000_000,
  market_return_pct: -9.5,
  market_pnl_irr: -47_500_000,
  vega_pnl_irr: 0,
  liquidity_cost_irr: 75_000_000,
  pnl_irr: -122_500_000,
};

const etfPosition = {
  symbol: "ZARFSHANG",
  asset_type: "etf" as const,
  direction: "long" as const,
  exposure_irr: 250_000_000,
  market_return_pct: -7.5,
  market_pnl_irr: -18_750_000,
  vega_pnl_irr: 0,
  liquidity_cost_irr: 37_500_000,
  pnl_irr: -56_250_000,
};

const blackSwanResult = {
  scenario_id: "black_swan",
  name_fa: "شوک سیاه",
  name_en: "Black swan",
  description_fa: "ریزش اونس، جهش دلار و قفل نقدشوندگی.",
  shocks,
  pnl_irr: -178_750_000,
  pnl_pct_of_equity: -17.875,
  post_equity_irr: 821_250_000,
  margin_call: true,
  forced_liquidation: false,
  maintenance_coverage_ratio: 16.425,
  worst_position: coinPosition,
  positions: [coinPosition, etfPosition],
};

const usdSpikeResult = {
  scenario_id: "usd_spike",
  name_fa: "جهش دلار",
  name_en: "USD spike",
  description_fa: "افزایش دلار آزاد با انتقال محدود به طلای داخلی.",
  shocks: scenarioCatalogue[1].shocks,
  pnl_irr: 8_750_000,
  pnl_pct_of_equity: 0.875,
  post_equity_irr: 1_008_750_000,
  margin_call: false,
  forced_liquidation: false,
  maintenance_coverage_ratio: 20.175,
  worst_position: coinPosition,
  positions: [coinPosition, etfPosition],
};

const stressResult = {
  available: true,
  reason: null,
  equity_irr: 1_000_000_000,
  gross_exposure_irr: 750_000_000,
  net_exposure_irr: 750_000_000,
  net_exposure_pct_of_equity: 75,
  gross_leverage_ratio: 0.75,
  margin_irr: 100_000_000,
  maintenance_margin_irr: 50_000_000,
  margin_utilization_pct: 10,
  concentration_hhi: 0.4444,
  largest_position_pct: 66.6667,
  exposure_by_asset_type_irr: { coin: 500_000_000, etf: 250_000_000 },
  risk_level: "HIGH" as const,
  worst_case: blackSwanResult,
  scenarios: [blackSwanResult, usdSpikeResult],
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return render(<GoldDerivativesRiskPage />, { wrapper: Wrapper });
}

/** The page starts empty by design; load the educational sample before acting. */
async function renderWithSample() {
  const user = userEvent.setup();
  renderPage();
  await screen.findByTestId("scenario-card-black_swan");
  await user.click(
    screen.getByRole("button", { name: "بارگذاری نمونهٔ آموزشی" }),
  );
  return user;
}

describe("GoldDerivativesRiskPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getGoldRiskScenarios.mockResolvedValue(scenarioCatalogue);
    mocks.runGoldRiskStress.mockResolvedValue(stressResult);
    mocks.getOptionsChainAnalytics.mockResolvedValue({
      available: false,
      reason: "unavailable in tests",
      contracts: [],
    });
    mocks.runOptionsStrategy.mockResolvedValue({
      available: false,
      reason: "unavailable in tests",
    });
  });

  it("renders the scenario catalogue and the sample portfolio", async () => {
    await renderWithSample();

    expect(screen.getByTestId("scenario-card-black_swan")).toBeInTheDocument();
    expect(screen.getByTestId("scenario-card-usd_spike")).toBeInTheDocument();
    expect(screen.getByDisplayValue("IR_COIN_EMAMI")).toBeInTheDocument();
    expect(screen.getByDisplayValue("ZARFSHANG")).toBeInTheDocument();
    expect(screen.getByTestId("equity-input")).toHaveValue(1_000_000_000);
  });

  it("runs the stress test and renders the worst case", async () => {
    const user = await renderWithSample();

    await user.click(screen.getByTestId("run-stress"));

    const badge = await screen.findByTestId("risk-level");
    expect(badge).toHaveTextContent("HIGH");
    expect(screen.getByTestId("worst-pnl")).toHaveAttribute(
      "data-raw",
      "-178750000",
    );
    expect(screen.getByTestId("scenario-row-black_swan")).toBeInTheDocument();
    expect(screen.getByText("جزئیات: شوک سیاه")).toBeInTheDocument();

    expect(mocks.runGoldRiskStress).toHaveBeenCalledTimes(1);
    const payload = mocks.runGoldRiskStress.mock.calls[0][0];
    expect(payload.equity_irr).toBe(1_000_000_000);
    expect(payload.positions).toHaveLength(2);
    expect(payload.positions[0]).toMatchObject({
      symbol: "IR_COIN_EMAMI",
      asset_type: "coin",
      direction: "long",
      exposure_irr: 500_000_000,
    });
    expect(payload.positions[1]).toMatchObject({
      symbol: "ZARFSHANG",
      asset_type: "etf",
      exposure_irr: 250_000_000,
    });
  });

  it("shows margin-call and liquidation flags per scenario", async () => {
    const user = await renderWithSample();

    await user.click(screen.getByTestId("run-stress"));
    const row = await screen.findByTestId("scenario-row-black_swan");

    expect(within(row).getByText("بله")).toBeInTheDocument();
    expect(within(row).getByText("خیر")).toBeInTheDocument();
  });

  it("renders the position-level breakdown for the selected scenario", async () => {
    const user = await renderWithSample();

    await user.click(screen.getByTestId("run-stress"));
    await screen.findByTestId("scenario-row-black_swan");

    expect(screen.getByText("IR_COIN_EMAMI", { selector: "td" })).toBeInTheDocument();
    expect(screen.getByText("ZARFSHANG", { selector: "td" })).toBeInTheDocument();
    expect(screen.getByText("هزینهٔ نقدشوندگی")).toBeInTheDocument();
  });
});
