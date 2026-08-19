import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import DashboardPage from "@/app/page";

// ── Mocks ───────────────────────────────────────────────────────────────────
// The page is a composition shell: it renders DashboardShell + dashboard
// sections. Those modules pull in next/navigation, recharts and data hooks
// that are out of scope for this test (and are covered by their own suites),
// so we mock them and test the page's own logic — the header, the ready gate
// (skeleton → sections) and that every section mounts — deterministically.

// Fixes `Error: invariant expected app router to be mounted` — TopNavbar (via
// DashboardShell) uses next/navigation hooks without a router context.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
    section: ({ children }: { children?: ReactNode }) => <section>{children}</section>,
  },
}));

// Layout shell mocked so TopNavbar / TickerBar / SmartScreenerFab don't need
// to render here (they are exercised by AppLayout.test.tsx).
vi.mock("@/components/layout/DashboardShell", () => ({
  default: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/layout/DashboardSkeleton", () => ({
  default: () => <div data-testid="dashboard-skeleton" />,
}));

// Every dashboard section is stubbed to a marker div. The page mounts them all
// inside the ready gate — asserting each marker proves the full section set is
// wired up without dragging charts / data hooks into this test.
vi.mock("@/components/dashboard/NewsStrip", () => ({
  default: () => <div data-testid="section-NewsStrip" />,
}));
vi.mock("@/components/dashboard/QuoteCards", () => ({
  default: () => <div data-testid="section-QuoteCards" />,
}));
vi.mock("@/components/dashboard/GlobalMarkets", () => ({
  default: () => <div data-testid="section-GlobalMarkets" />,
}));
vi.mock("@/components/dashboard/IndexCards", () => ({
  default: () => <div data-testid="section-IndexCards" />,
}));
vi.mock("@/components/dashboard/TrendChart", () => ({
  default: () => <div data-testid="section-TrendChart" />,
}));
vi.mock("@/components/dashboard/TripleChartsGroup", () => ({
  default: () => <div data-testid="section-TripleChartsGroup" />,
}));
vi.mock("@/components/dashboard/MarketMap", () => ({
  default: () => <div data-testid="section-MarketMap" />,
}));
vi.mock("@/components/dashboard/MarketOverview", () => ({
  default: () => <div data-testid="section-MarketOverview" />,
}));
vi.mock("@/components/dashboard/TopStocksToday", () => ({
  default: () => <div data-testid="section-TopStocksToday" />,
}));
vi.mock("@/components/dashboard/OwnershipChange", () => ({
  default: () => <div data-testid="section-OwnershipChange" />,
}));
vi.mock("@/components/dashboard/AssetAllocationPie", () => ({
  default: () => <div data-testid="section-AssetAllocationPie" />,
}));
vi.mock("@/components/dashboard/IndexImpacts", () => ({
  default: () => <div data-testid="section-IndexImpacts" />,
}));
vi.mock("@/components/dashboard/ValueVolumePanel", () => ({
  default: () => <div data-testid="section-ValueVolumePanel" />,
}));
vi.mock("@/components/dashboard/EventCalendar", () => ({
  default: () => <div data-testid="section-EventCalendar" />,
}));
vi.mock("@/components/dashboard/LiquidityBlocks", () => ({
  default: () => <div data-testid="section-LiquidityBlocks" />,
}));

const SECTION_TESTIDS = [
  "section-NewsStrip",
  "section-QuoteCards",
  "section-GlobalMarkets",
  "section-IndexCards",
  "section-TrendChart",
  "section-TripleChartsGroup",
  "section-MarketMap",
  "section-MarketOverview",
  "section-TopStocksToday",
  "section-OwnershipChange",
  "section-AssetAllocationPie",
  "section-IndexImpacts",
  "section-ValueVolumePanel",
  "section-EventCalendar",
  "section-LiquidityBlocks",
];

// ── Tests ───────────────────────────────────────────────────────────────────

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the page header immediately and shows the skeleton while loading", () => {
    render(<DashboardPage />);

    expect(screen.getByText("داشبورد بازار سرمایه")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-skeleton")).toBeInTheDocument();
    // Sections are gated behind the ready timer — not mounted yet.
    expect(screen.queryByTestId("section-NewsStrip")).not.toBeInTheDocument();
  });

  it("mounts the dashboard sections once the ready gate passes", () => {
    render(<DashboardPage />);

    act(() => {
      vi.advanceTimersByTime(700); // ready timer is 620ms
    });

    expect(screen.queryByTestId("dashboard-skeleton")).not.toBeInTheDocument();
    expect(screen.getByTestId("section-NewsStrip")).toBeInTheDocument();
    expect(screen.getByTestId("section-QuoteCards")).toBeInTheDocument();
    expect(screen.getByTestId("section-TopStocksToday")).toBeInTheDocument();
  });

  it("mounts every dashboard section after ready without crashing", () => {
    render(<DashboardPage />);

    act(() => {
      vi.advanceTimersByTime(700);
    });

    for (const testid of SECTION_TESTIDS) {
      expect(screen.getByTestId(testid)).toBeInTheDocument();
    }
    // Header persists alongside the sections.
    expect(screen.getByText("داشبورد بازار سرمایه")).toBeInTheDocument();
  });
});
