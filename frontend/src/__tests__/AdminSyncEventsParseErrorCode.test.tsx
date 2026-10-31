import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { ReactNode } from "react";
import AdminUnifiedPage from "@/app/admin/page";

// ── Mocks ───────────────────────────────────────────────────────────────────
// The admin page is a tabbed shell with several admin queries. Only the sync
// tab's recent-events list is under test here, so layout, charts and the
// settings hook are stubbed and useQuery is answered per query key.

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

vi.mock("next/dynamic", () => ({
  default: () => () => <div data-testid="area-chart" />,
}));

// ── Fixtures ────────────────────────────────────────────────────────────────

const PARSE_MESSAGE =
  "ParseError[unrecognised_envelope]: IME: unrecognised envelope keys ['foo']";

const EVENTS = [
  {
    time: new Date().toISOString(),
    endpoint: "/IME/Futures.php",
    category: "ime",
    status: "error",
    outcome: "parse_error",
    error_message: PARSE_MESSAGE,
    items_count: 0,
    duration_ms: 8,
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

const JOB_MESSAGE =
  "ParseError[unexpected_shape]: Candlestick: 'candles' must be a list, got str";

const DASHBOARD = {
  metrics: { total_db_records: 1200, total_users: 3, active_users: 2 },
  job_stats: { total_runs: 4, successful: 3, failed: 1, running: 0, avg_duration: 2.4 },
  daily_records: {},
  recent_jobs: [
    {
      id: "job-1",
      job_type: "brsapi_candlesticks",
      status: "failed",
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      duration_seconds: 1.2,
      error_message: JOB_MESSAGE,
    },
  ],
};

describe("admin sync events parse-error detail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseQuery.mockImplementation(({ queryKey }: { queryKey: unknown[] }) => {
      if (queryKey[0] === "admin-sync-events") {
        return { data: EVENTS, isLoading: false };
      }
      if (queryKey[0] === "admin-dash") {
        return { data: DASHBOARD, isLoading: false };
      }
      return { data: undefined, isLoading: false };
    });
  });

  function renderSyncTab() {
    render(<AdminUnifiedPage />);
    fireEvent.click(screen.getByRole("button", { name: /همگام‌سازی/ }));
  }

  it("shows the structured parse code next to the failure outcome", () => {
    renderSyncTab();

    expect(screen.getByText("parse_error")).toBeInTheDocument();
    expect(screen.getByText("unrecognised_envelope")).toBeInTheDocument();
  });

  it("exposes the full parse message as the failure detail title", () => {
    renderSyncTab();

    const detail = screen.getByText("parse_error").closest("[title]");
    expect(detail?.getAttribute("title")).toBe(PARSE_MESSAGE);
  });

  it("does not render a code badge for a successful row", () => {
    renderSyncTab();

    expect(screen.getByText("5 آیتم")).toBeInTheDocument();
    expect(document.querySelectorAll("code")).toHaveLength(1);
  });
});

describe("admin overview recent jobs parse-error detail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseQuery.mockImplementation(({ queryKey }: { queryKey: unknown[] }) => {
      if (queryKey[0] === "admin-dash") {
        return { data: DASHBOARD, isLoading: false };
      }
      return { data: undefined, isLoading: false };
    });
  });

  it("shows the parse code and keeps the message readable", () => {
    render(<AdminUnifiedPage />);

    // Default tab is the overview, which lists recent jobs.
    expect(screen.getByText("unexpected_shape")).toBeInTheDocument();
    // The code is shown once, as a badge — not repeated in the message text.
    expect(
      screen.getByText("Candlestick: 'candles' must be a list, got str"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/ParseError\[/)).not.toBeInTheDocument();
  });

  it("keeps the full parser message as the cell title", () => {
    render(<AdminUnifiedPage />);

    const detail = screen.getByText("unexpected_shape").closest("td");
    expect(detail?.getAttribute("title")).toBe(JOB_MESSAGE);
  });
});
