import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import DashboardPage from "@/app/page";

// ── Mock data-fetching deps so the page renders deterministically ────────────
const mockUseQuery = vi.fn();
vi.mock("@tanstack/react-query", () => ({
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
}));

vi.mock("@/hooks/useSectorCounts", () => ({
  useSectorCounts: () => ({ sectors: [] }),
}));

vi.mock("@/lib/api", () => ({ apiGet: vi.fn() }));

// The page uses Link + AppLayout; mock layout shell to render children only.
vi.mock("@/components/layout/AppLayout", () => ({
  default: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

// ── Helpers ───────────────────────────────────────────────────────────────────
interface QueryOptions {
  queryKey?: string[];
}

function mockDashboardData(active: Record<string, unknown>[]) {
  mockUseQuery.mockImplementation((opts: QueryOptions) => {
    const key = opts.queryKey?.[0];
    if (key === "market-dashboard") {
      return {
        data: {
          overview: {},
          screener: [],
          commodities: [],
          crypto: [],
          gainers: [],
          losers: [],
          active,
        },
        isLoading: false,
      };
    }
    // Every other query returns nothing so the page uses its fallback/mock data.
    return { data: undefined, isLoading: false };
  });
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the active symbols table from dashboardData.active", () => {
    // Prices chosen to be UNIQUE across the page (must not collide with the
    // fallback mock widgets — topTraded uses 565 for خودرو, metals 3550, etc.)
    mockDashboardData([
      { symbol: "فولاد", price_last: 2150, price_change_pct: 1.5, volume: 1_000_000, value: 2_000_000_000 },
      { symbol: "خودرو", price_last: 999, price_change_pct: -0.8, volume: 500_000, value: 1_000_000_000 },
    ]);

    render(<DashboardPage />);

    // Section title + active symbols rendered. The price strings (۲٬۱۵۰ / ۹۹۹)
    // come from price_last.toLocaleString("fa-IR") and appear ONLY in the active
    // table (fallback widgets use different values), so they uniquely prove the
    // dashboardData.active data made it into the DOM.
    expect(screen.getByText("فعال‌ترین نمادها")).toBeInTheDocument();
    expect(screen.getByText("۲٬۱۵۰")).toBeInTheDocument();
    expect(screen.getByText("۹۹۹")).toBeInTheDocument();
  });

  it("shows empty state when there is no active data", () => {
    mockDashboardData([]);
    render(<DashboardPage />);
    expect(screen.getByText("داده‌ای موجود نیست")).toBeInTheDocument();
  });

  it("does not crash when dashboardData is missing entirely", () => {
    mockUseQuery.mockImplementation((opts: QueryOptions) => {
      const key = opts.queryKey?.[0];
      if (key === "market-dashboard") return { data: undefined, isLoading: true };
      return { data: undefined, isLoading: false };
    });
    render(<DashboardPage />);
    // Should render without throwing (fallback path)
    expect(screen.getByText("فعال‌ترین نمادها")).toBeInTheDocument();
  });
});
