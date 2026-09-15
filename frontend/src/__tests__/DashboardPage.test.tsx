import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import DashboardPage from "@/app/page";

// ── Mocks ───────────────────────────────────────────────────────────────────
// The page is a composition shell: it renders DashboardShell + dashboard
// sections. Those modules pull in next/navigation, recharts and data hooks
// that are out of scope for this test (and are covered by their own suites),
// so we mock them and test the page's own logic — the header and that every
// section mounts — deterministically.

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

// Every dashboard section is stubbed to a marker div. Asserting each marker
// proves the full section set is wired up without dragging charts / data
// hooks into this test. The three recharts widgets load via next/dynamic, so
// their stubs resolve synchronously through the dynamic import mock below.
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
  it("renders the page header immediately", () => {
    render(<DashboardPage />);

    expect(screen.getByText("داشبورد بازار سرمایه")).toBeInTheDocument();
    expect(screen.getByText(/نمای زنده قیمت‌ها/)).toBeInTheDocument();
  });

  it("mounts the static dashboard sections on first render", () => {
    render(<DashboardPage />);

    expect(screen.getByTestId("section-NewsStrip")).toBeInTheDocument();
    expect(screen.getByTestId("section-QuoteCards")).toBeInTheDocument();
    expect(screen.getByTestId("section-GlobalMarkets")).toBeInTheDocument();
    expect(screen.getByTestId("section-IndexCards")).toBeInTheDocument();
    expect(screen.getByTestId("section-TopStocksToday")).toBeInTheDocument();
    expect(screen.getByTestId("section-MarketMap")).toBeInTheDocument();
  });

  it("mounts every dashboard section, including lazy-loaded charts", async () => {
    render(<DashboardPage />);

    // The recharts widgets stream in via next/dynamic — await them.
    expect(await screen.findByTestId("section-TrendChart")).toBeInTheDocument();
    expect(await screen.findByTestId("section-TripleChartsGroup")).toBeInTheDocument();
    expect(await screen.findByTestId("section-AssetAllocationPie")).toBeInTheDocument();

    for (const testid of SECTION_TESTIDS) {
      expect(screen.getByTestId(testid)).toBeInTheDocument();
    }
    // Header persists alongside the sections.
    expect(screen.getByText("داشبورد بازار سرمایه")).toBeInTheDocument();
  });
});
