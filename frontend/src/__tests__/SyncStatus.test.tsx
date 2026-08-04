import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SyncStatus from "@/components/SyncStatus";

// ── Mocks ───────────────────────────────────────────────────────────────────
const mockUseQuery = vi.fn();
const mockInvalidateQueries = vi.fn();
const mockPush = vi.fn();
const mockApiGet = vi.fn();
const mockApiPost = vi.fn();

vi.mock("@tanstack/react-query", () => ({
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
  useQueryClient: () => ({ invalidateQueries: mockInvalidateQueries }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => mockApiGet(...args),
  apiPost: (...args: unknown[]) => mockApiPost(...args),
}));

// Use real sync-settings logic so threshold recalculation is exercised.
vi.mock("@/lib/sync-settings", async () => {
  const actual = await vi.importActual<typeof import("@/lib/sync-settings")>("@/lib/sync-settings");
  return {
    ...actual,
    loadSyncSettings: () => actual.DEFAULT_SYNC_SETTINGS,
  };
});

// ── Fixtures ────────────────────────────────────────────────────────────────

interface TableSyncInfo {
  last_fetched: string | null;
  record_count: number;
  age_minutes: number;
  status: "ok" | "stale" | "outdated" | "missing" | "unknown" | "error";
  max_age_minutes: number;
}

function makeInfo(overrides: Partial<TableSyncInfo>): TableSyncInfo {
  return {
    last_fetched: new Date(Date.now() - 60_000).toISOString(),
    record_count: 100,
    age_minutes: 1,
    status: "ok",
    max_age_minutes: 10,
    ...overrides,
  };
}

const OK_STATUS = {
  symbols: makeInfo({}),
  index: makeInfo({}),
};

const OUTDATED_STATUS = {
  symbols: makeInfo({ age_minutes: 100, status: "outdated", record_count: 150 }),
  index: makeInfo({}),
};

// ── Setup helpers ───────────────────────────────────────────────────────────

function mockQueryData(data: Record<string, TableSyncInfo> | undefined, opts: { isLoading?: boolean; isError?: boolean } = {}) {
  mockUseQuery.mockReturnValue({
    data,
    isLoading: opts.isLoading ?? false,
    isError: opts.isError ?? false,
  });
}

function renderSyncStatus() {
  return render(<SyncStatus />);
}

// ── Tests ───────────────────────────────────────────────────────────────────

describe("SyncStatus", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApiGet.mockResolvedValue({ success: true, data: {} });
    mockApiPost.mockResolvedValue({ success: true, data: { success: true, items_count: 42, duration_ms: 500 } });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the compact pill showing 'به‌روز' when all sections are fresh", () => {
    mockQueryData(OK_STATUS);
    renderSyncStatus();

    expect(screen.getByText("به‌روز")).toBeInTheDocument();
    // Summary shows (2/2)
    expect(screen.getByText("(2/2)")).toBeInTheDocument();
  });

  it("shows loading placeholder while fetching", () => {
    mockQueryData(undefined, { isLoading: true });
    renderSyncStatus();

    expect(screen.getByText("...")).toBeInTheDocument();
  });

  it("shows 'N خیلی قدیمی' in the pill when outdated sections exist", () => {
    mockQueryData(OUTDATED_STATUS);
    renderSyncStatus();

    expect(screen.getByText("1 خیلی قدیمی")).toBeInTheDocument();
  });

  it("renders the outdated warning toast with a link to /sync", async () => {
    mockQueryData(OUTDATED_STATUS);
    renderSyncStatus();

    // Outdated toast appears once per page load
    await waitFor(() => {
      expect(screen.getByText(/قدیمی هستند — لطفاً sync کنید/)).toBeInTheDocument();
    });

    // The warning toast exposes a "رفتن به sync" button
    const syncLink = screen.getByRole("button", { name: /رفتن به sync/ });
    expect(syncLink).toBeInTheDocument();

    // Clicking it navigates to /sync
    fireEvent.click(syncLink);
    expect(mockPush).toHaveBeenCalledWith("/sync");
  });

  it("does not show the outdated toast when all data is fresh", async () => {
    mockQueryData(OK_STATUS);
    renderSyncStatus();

    await waitFor(() => {
      expect(screen.queryByText(/قدیمی هستند/)).not.toBeInTheDocument();
    });
  });

  it("expands to show per-section rows and a Sync Now button", async () => {
    mockQueryData(OK_STATUS);
    renderSyncStatus();

    // Click the pill to expand
    fireEvent.click(screen.getByText("به‌روز"));
    await waitFor(() => {
      expect(screen.getByText("وضعیت همگام‌سازی داده‌ها")).toBeInTheDocument();
    });

    // Both sections rendered
    expect(screen.getByText(/نمادها \(بورس\)/)).toBeInTheDocument();
    expect(screen.getByText(/شاخص‌ها/)).toBeInTheDocument();
  });

  it("calls the sync endpoint and shows a success toast when Sync Now is clicked", async () => {
    mockQueryData(OK_STATUS);
    renderSyncStatus();

    fireEvent.click(screen.getByText("به‌روز"));
    await waitFor(() => expect(screen.getByText("وضعیت همگام‌سازی داده‌ها")).toBeInTheDocument());

    // Click Sync Now for the symbols section
    fireEvent.click(screen.getAllByTitle(/^Sync /)[0]);

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith("/brsapi/manage/sync/all-symbols");
    });

    await waitFor(() => {
      expect(screen.getByText(/42 رکورد/)).toBeInTheDocument();
    });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ["brsapi-sync-status"] });
  });

  it("shows an error toast when the section is not supported", async () => {
    mockQueryData({
      unknown_section: makeInfo({ status: "ok" }),
    });
    renderSyncStatus();

    fireEvent.click(screen.getByText("به‌روز"));
    await waitFor(() => expect(screen.getByText("وضعیت همگام‌سازی داده‌ها")).toBeInTheDocument());

    fireEvent.click(screen.getAllByTitle(/^Sync /)[0]);

    await waitFor(() => {
      expect(screen.getByText(/پشتیبانی نمی‌شود/)).toBeInTheDocument();
    });
    expect(mockApiPost).not.toHaveBeenCalled();
  });

  it("shows an error message when the status fetch fails", async () => {
    mockQueryData(undefined, { isError: true });
    renderSyncStatus();

    // With isLoading=false + isError=true the pill falls through to the
    // "no issues" branch (به‌روز (0/0)) — click it to expand the panel.
    fireEvent.click(screen.getByText("به‌روز"));
    await waitFor(() => {
      expect(screen.getByText("خطا در دریافت وضعیت")).toBeInTheDocument();
    });
  });
});
