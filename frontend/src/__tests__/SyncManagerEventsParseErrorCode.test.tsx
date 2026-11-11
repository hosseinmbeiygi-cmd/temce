import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import SyncManagerPage from "@/app/sync-manager/page";

// ── Mocks ───────────────────────────────────────────────────────────────────
// The sync-manager is a large dashboard; only the "آخرین رویدادهای Sync" card
// on the default tab is under test, so layout, chart and settings plumbing are
// stubbed and useQuery is answered per query key.

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

vi.mock("next/dynamic", () => ({
  default: () => () => <div data-testid="area-chart" />,
}));

// ── Fixtures ────────────────────────────────────────────────────────────────

const PARSE_MESSAGE = "ParseError[missing_payload]: Transaction: payload is None, not a JSON document";

const HISTORY = [
  {
    time: new Date().toISOString(),
    endpoint: "/Tsetmc/Transaction.php",
    category: "tsetmc",
    status: "error",
    outcome: "parse_error",
    error_message: PARSE_MESSAGE,
    items_count: 0,
    duration_ms: 9,
    completed_at: new Date().toISOString(),
  },
  {
    time: new Date().toISOString(),
    endpoint: "/Tsetmc/AllSymbols.php",
    category: "tsetmc",
    status: "success",
    outcome: "success",
    error_message: null,
    items_count: 5,
    duration_ms: 30,
    completed_at: new Date().toISOString(),
  },
];

describe("sync-manager recent events parse-error detail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseQuery.mockImplementation(({ queryKey }: { queryKey: unknown[] }) => {
      if (queryKey[0] === "sync-manager-history") {
        return { data: HISTORY, isLoading: false };
      }
      return { data: undefined, isLoading: false };
    });
  });

  it("shows the structured parse code next to the failure outcome", () => {
    render(<SyncManagerPage />);

    expect(screen.getByText("parse_error")).toBeInTheDocument();
    expect(screen.getByText("missing_payload")).toBeInTheDocument();
  });

  it("exposes the full parse message as the failure detail title", () => {
    render(<SyncManagerPage />);

    const detail = screen.getByText("parse_error").closest("[title]");
    expect(detail?.getAttribute("title")).toBe(PARSE_MESSAGE);
  });

  it("does not render a code badge for a successful row", () => {
    render(<SyncManagerPage />);

    expect(screen.getByText("5 آیتم")).toBeInTheDocument();
    expect(document.querySelectorAll("code")).toHaveLength(1);
  });
});
