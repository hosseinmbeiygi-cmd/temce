import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import BacktestResultsDashboard, { type BacktestResultData } from "@/components/charts/BacktestResultsDashboard";

// ── MLBacktestTab needs useQuery + api + toast; mock them so it renders idle state ─
const mockUseQuery = vi.fn();
vi.mock("@tanstack/react-query", () => ({
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
  useMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import MLBacktestTab from "@/components/charts/MLBacktestTab";

// ── BacktestResultsDashboard ────────────────────────────────────────────────

function fullResult(): BacktestResultData {
  return {
    initial_capital: 1_000_000_000,
    final_value: 1_250_000_000,
    total_return_pct: 25.0,
    annualized_return_pct: 15.2,
    sharpe_ratio: 1.4,
    max_drawdown_pct: -8.5,
    win_rate: 55.0,
    total_trades: 40,
    winning_trades: 22,
    losing_trades: 18,
    profit_factor: 1.6,
    equity_curve: [
      { timestamp: "2026-01-01T00:00:00Z", nav: 1_000_000_000 },
      { timestamp: "2026-01-02T00:00:00Z", nav: 1_020_000_000 },
      { timestamp: "2026-01-03T00:00:00Z", nav: 1_010_000_000 },
      { timestamp: "2026-01-04T00:00:00Z", nav: 1_050_000_000 },
      { timestamp: "2026-01-05T00:00:00Z", nav: 1_080_000_000 },
    ],
    trades: [
      { instrument_id: "فولاد", side: "buy", quantity: 1000, price: 2100, pnl: 500_000 },
      { instrument_id: "خودرو", side: "sell", quantity: 500, price: 565, pnl: -200_000 },
    ],
  };
}

describe("BacktestResultsDashboard", () => {
  it("renders without crashing with an empty result", () => {
    render(<BacktestResultsDashboard result={{}} />);
    // MetricCard renders "{icon} {label}" as ONE text node; exact match is required
    // because the tooltip text ("درصد بازده کل سرمایه...") also contains "بازده کل"
    expect(screen.getByText("📈 بازده کل")).toBeInTheDocument();
    expect(screen.getByText(/داده کافی برای نمایش منحنی سرمایه/)).toBeInTheDocument();
  });

  it("renders metrics and trade summary with a full result", () => {
    render(<BacktestResultsDashboard result={fullResult()} />);
    expect(screen.getByText("📈 بازده کل")).toBeInTheDocument();
    // pct(25.0) → "+25.00%" (ASCII digits), standalone value text node
    expect(screen.getByText(/\+25\.00%/)).toBeInTheDocument();
    // Exact label match: "معاملات" also appears in "خلاصه معاملات" card title and
    // "توزیع سود/زیان معاملات" chart title
    expect(screen.getByText("🔄 معاملات")).toBeInTheDocument();
    // subtitle uses ASCII digits from JS template literal: "22 برد / 18 باخت"
    expect(screen.getByText(/22 برد/)).toBeInTheDocument();
    // Trades table renders the side badge ("خرید"), not instrument_id
    expect(screen.getByText("خرید")).toBeInTheDocument();
  });
});

// ── MLBacktestTab ────────────────────────────────────────────────────────────

describe("MLBacktestTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseQuery.mockImplementation((opts: { queryKey?: string[] }) => {
      const key = opts.queryKey?.[0];
      if (key === "ml-all-symbols") return { data: ["فولاد", "خودرو"] };
      return { data: undefined };
    });
  });

  it("renders the run button and feature-group controls", () => {
    render(<MLBacktestTab />);
    // Unique text: the button label — not present in the idle prompt
    expect(screen.getByText(/اجرای بک‌تست/)).toBeInTheDocument();
    // "گروه ویژگی:" with colon only appears in the feature-group label span — the
    // idle prompt uses "گروه ویژگی را انتخاب کنید" (no colon)
    expect(screen.getByText(/گروه ویژگی:/)).toBeInTheDocument();
    // Symbol select should render the mocked symbols as options
    expect(screen.getByRole("option", { name: "فولاد" })).toBeInTheDocument();
  });

  it("shows the empty-state prompt when no result has been run", () => {
    render(<MLBacktestTab />);
    expect(screen.getByText(/بک‌تست Walk-Forward/)).toBeInTheDocument();
  });
});
