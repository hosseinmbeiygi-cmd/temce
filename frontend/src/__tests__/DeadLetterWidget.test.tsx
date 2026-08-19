import { describe, it, expect, vi, beforeEach } from "vitest";
import { cloneElement } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DeadLetterWidget from "@/components/admin/DeadLetterWidget";

function renderWidget() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  const utils = render(
    <QueryClientProvider client={qc}>
      <DeadLetterWidget />
    </QueryClientProvider>
  );
  return { ...utils, user: userEvent.setup() };
}

// ── Mocks ────────────────────────────────────────────────────────────
vi.mock("@/components/charts/ChartContainer", () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("recharts", async () => {
  const actual = await vi.importActual("recharts");
  // Recharts needs explicit width/height to render — inject them like the
  // real ResponsiveContainer does after measuring the parent.
  const MockResponsiveContainer = ({ children }: { children: React.ReactElement }) =>
    cloneElement(
      children as React.ReactElement<{ width?: number; height?: number }>,
      { width: 600, height: 300 },
    );
  return { ...actual, ResponsiveContainer: MockResponsiveContainer };
});

vi.mock("@/lib/api", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

import { apiGet, apiPost } from "@/lib/api";

const mockApiGet = vi.mocked(apiGet);
const mockApiPost = vi.mocked(apiPost);

function makeSummary(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    success: true,
    data: {
      total: 6,
      queue: "job:dead",
      malformed: 0,
      job_names: [
        { name: "SyncQuotesJob", count: 2 },
        { name: "SyncCodalJob", count: 2 },
        { name: "NewsFetchJob", count: 1 },
        { name: "BrsapiCandlestickJob", count: 1 },
      ],
      error_categories: [
        { category: "db_error", count: 2 },
        { category: "timeout", count: 2 },
        { category: "parse_error", count: 1 },
        { category: "rate_limit", count: 1 },
      ],
      top_errors: [
        { error: "DBError: SQLAlchemy connection refused", count: 2 },
        { error: "TimeoutError: timed out waiting for codal.ir", count: 2 },
      ],
      repeated: [
        { job_name: "SyncCodalJob", job_id: "demo-c-003", count: 2 },
      ],
      repeated_messages: 1,
    },
    ...overrides,
  };
}

// ── Tests ────────────────────────────────────────────────────────────

describe("DeadLetterWidget", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders summary metrics and the job_names table", async () => {
    mockApiGet.mockResolvedValue(makeSummary());

    renderWidget();

    // Metric chips
    expect(await screen.findByText("۶")).toBeInTheDocument(); // total (fa-IR digits)
    expect(screen.getByText("۴")).toBeInTheDocument();        // distinct jobs

    // job_names table rows (SyncCodalJob also appears in the repeated list)
    expect(await screen.findByText("SyncQuotesJob")).toBeInTheDocument();
    expect(screen.getAllByText("SyncCodalJob").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("NewsFetchJob")).toBeInTheDocument();
    expect(screen.getByText("BrsapiCandlestickJob")).toBeInTheDocument();
  });

  it("renders error category labels on the chart", async () => {
    mockApiGet.mockResolvedValue(makeSummary());

    const { container } = renderWidget();

    // SVG <text> ticks: query the rendered tick values directly (like the
    // MultiEquityChart tests query svg paths).
    await waitFor(() => {
      const tickText = Array.from(
        container.querySelectorAll<SVGTextElement>(".recharts-cartesian-axis-tick-value"),
      ).map((t) => t.textContent ?? "");
      expect(tickText.join(" | ")).toContain("خطای دیتابیس");
      expect(tickText.join(" | ")).toContain("تایم‌اوت");
      expect(tickText.join(" | ")).toContain("خطای پارس");
      expect(tickText.join(" | ")).toContain("محدودیت نرخ");
    });
  });

  it("renders repeated messages with count badge", async () => {
    mockApiGet.mockResolvedValue(makeSummary());

    renderWidget();

    expect(await screen.findByText("demo-c-003")).toBeInTheDocument();
    // The "۲×" badge also appears in top_errors — assert at least one.
    expect(screen.getAllByText("۲×").length).toBeGreaterThanOrEqual(1);
  });

  it("renders top raw errors", async () => {
    mockApiGet.mockResolvedValue(makeSummary());

    renderWidget();

    expect(await screen.findByText(/SQLAlchemy connection refused/)).toBeInTheDocument();
    expect(screen.getByText(/timed out waiting for codal.ir/)).toBeInTheDocument();
  });

  it("shows empty state when the queue is empty", async () => {
    mockApiGet.mockResolvedValue({
      success: true,
      data: {
        total: 0, queue: "job:dead", malformed: 0,
        job_names: [], error_categories: [], top_errors: [], repeated: [], repeated_messages: 0,
      },
    });

    renderWidget();

    expect(await screen.findByText(/صف dead-letter خالی است/)).toBeInTheDocument();
  });

  it("refetches the summary periodically — default window is today", async () => {
    mockApiGet.mockResolvedValue(makeSummary());

    renderWidget();

    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith("/jobs/queue/summary?window=today");
    });
  });

  it("switches the time window on selector click", async () => {
    mockApiGet.mockResolvedValue(makeSummary({ data: { ...makeSummary().data, window: "week" } }));

    const { user } = renderWidget();

    const weekBtn = await screen.findByRole("button", { name: /این هفته/ });
    await user.click(weekBtn);

    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith("/jobs/queue/summary?window=week");
    });
  });

  // ── Replay (POST /jobs/queue/replay) ──────────────────────────────

  it("keeps replay enabled even when the current window is empty", async () => {
    // Replay acts on the WHOLE queue (not just the selected window), so the
    // button must stay enabled when the windowed summary shows zero.
    mockApiGet.mockResolvedValue({
      success: true,
      data: {
        total: 0, queue: "job:dead", malformed: 0,
        job_names: [], error_categories: [], top_errors: [], repeated: [], repeated_messages: 0,
      },
    });
    mockApiPost.mockResolvedValue({
      success: true,
      data: {
        mode: "replay", total: 0, replayed: 0, failed: 0, discarded: 0,
        queue: "job:queue", dead_queue: "job:dead", queue_size: 0, dead_size: 0,
      },
    });

    const { user } = renderWidget();

    const replayBtn = await screen.findByRole("button", { name: /Replay همهٔ پیام‌ها/ });
    expect(replayBtn).not.toBeDisabled();

    await user.click(replayBtn);
    await user.click(screen.getByRole("button", { name: /مطمئنید/ }));

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith("/jobs/queue/replay");
    });
    expect(await screen.findByText(/۰ پیام replay شد/)).toBeInTheDocument();
  });

  it("replays via POST with two-step confirm and shows the result", async () => {
    mockApiGet.mockResolvedValue(makeSummary());
    mockApiPost.mockResolvedValue({
      success: true,
      data: {
        mode: "replay", total: 6, replayed: 6, failed: 0, discarded: 0,
        queue: "job:queue", dead_queue: "job:dead", queue_size: 6, dead_size: 0,
      },
    });

    const { user } = renderWidget();

    const replayBtn = await screen.findByRole("button", { name: /Replay همهٔ پیام‌ها/ });
    await user.click(replayBtn);
    // First click only arms the confirm state — no POST yet.
    expect(mockApiPost).not.toHaveBeenCalled();
    expect(await screen.findByRole("button", { name: /مطمئنید/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /مطمئنید/ }));

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith("/jobs/queue/replay");
    });
    // Result banner: replayed count in fa-IR digits.
    expect(await screen.findByText(/۶ پیام replay شد/)).toBeInTheDocument();
  });

  it("shows an error banner when replay fails", async () => {
    mockApiGet.mockResolvedValue(makeSummary());
    mockApiPost.mockResolvedValue({
      success: false,
      error: { message: "Redis unavailable" },
      data: {},
    });

    const { user } = renderWidget();

    const replayBtn = await screen.findByRole("button", { name: /Replay همهٔ پیام‌ها/ });
    await user.click(replayBtn);
    await user.click(screen.getByRole("button", { name: /مطمئنید/ }));

    expect(await screen.findByText(/Redis unavailable/)).toBeInTheDocument();
  });
});
