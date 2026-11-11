import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import SyncStatusPage from "@/app/sync/page";

// ── Mocks ───────────────────────────────────────────────────────────────────
// The page is a composition shell: two queries (status + history) and a layout
// wrapper. Those are stubbed so the test covers the page's own rendering of a
// failed history row, not react-query or navigation.

const mockUseQuery = vi.fn();

vi.mock("@tanstack/react-query", () => ({
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

vi.mock("@/components/layout/AppLayout", () => ({
  default: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/hooks/useSyncSettings", () => ({
  useSyncSettings: () => [{}, vi.fn()],
}));

vi.mock("@/lib/sync-settings", () => ({
  applyCustomThresholds: (status: unknown) => status,
}));

// Recharts is loaded through next/dynamic with ssr:false; it is irrelevant here.
vi.mock("next/dynamic", () => ({
  default: () => () => <div data-testid="area-chart" />,
}));

// ── Fixtures ────────────────────────────────────────────────────────────────

const PARSE_MESSAGE =
  "ParseError[unexpected_shape]: Candlestick: 'candles' must be a list, got str";

const HISTORY = [
  {
    time: new Date().toISOString(),
    endpoint: "/Tsetmc/Candlestick.php",
    category: "tsetmc",
    status: "error",
    outcome: "parse_error",
    error_message: PARSE_MESSAGE,
    items_count: 0,
    duration_ms: 12,
    completed_at: new Date().toISOString(),
  },
  {
    time: new Date().toISOString(),
    endpoint: "/Market/Commodity.php",
    category: "commodity",
    status: "success",
    outcome: "success",
    error_message: null,
    items_count: 5,
    duration_ms: 30,
    completed_at: new Date().toISOString(),
  },
];

function mockQueries() {
  mockUseQuery.mockImplementation(({ queryKey }: { queryKey: unknown[] }) => {
    if (queryKey[0] === "brsapi-sync-history") {
      return { data: HISTORY, isLoading: false };
    }
    return { data: {}, isLoading: false, isError: false };
  });
}

describe("sync dashboard parse-error detail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockQueries();
  });

  it("shows the structured parse code next to the failure outcome", () => {
    render(<SyncStatusPage />);

    expect(screen.getByText("parse_error")).toBeInTheDocument();
    // The code is the actionable part of the message.
    expect(screen.getByText("unexpected_shape")).toBeInTheDocument();
  });

  it("exposes the full parse message as the failure detail title", () => {
    render(<SyncStatusPage />);

    const failure = screen.getByText("parse_error");
    const detail = failure.closest("[title]");

    expect(detail?.getAttribute("title")).toBe(PARSE_MESSAGE);
  });

  it("does not render a code badge for a successful row", () => {
    render(<SyncStatusPage />);

    // The success row reports its item count instead.
    expect(screen.getByText("5 آیتم")).toBeInTheDocument();
    expect(document.querySelectorAll("code")).toHaveLength(1);
  });
});
