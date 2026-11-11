// Stage 05 — بنر تازگی/خطا. سه حالت باید از هم جدا بمانند:
//   * دادهٔ تازه            → هیچ بنری
//   * داده هست ولی کهنه     → هشدار کهنگی با ساعت `data_as_of`
//   * خطای درخواست          → بنر خطای ارتباط

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import LiveDataBanner from "@/components/dashboard/LiveDataBanner";

const minutesAgo = (minutes: number): string =>
  new Date(Date.now() - minutes * 60_000).toISOString();

describe("LiveDataBanner", () => {
  it("renders nothing while the first load is running", () => {
    const { container } = render(
      <LiveDataBanner state={{ isLive: false, isError: false, isLoading: true }} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing for fresh live data", () => {
    const { container } = render(
      <LiveDataBanner
        state={{ isLive: true, isError: false, isLoading: false, dataAsOf: minutesAgo(1) }}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("stays silent for live widgets that pass no data_as_of (unchanged callers)", () => {
    const { container } = render(
      <LiveDataBanner state={{ isLive: true, isError: false, isLoading: false }} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("warns when live data is older than the freshness window", () => {
    render(
      <LiveDataBanner
        state={{ isLive: true, isError: false, isLoading: false, dataAsOf: minutesAgo(30) }}
      />,
    );
    const banner = screen.getByRole("status");
    expect(banner.textContent).toMatch(/قدیمی است/);
  });

  it("formats a naive backend timestamp as UTC, not as browser-local time", () => {
    // Backend `data_as_of` is naive UTC; raw `new Date("...")` would shift the
    // clock label by the browser's timezone offset.
    const naiveUtc = "2020-01-01T09:30:00";
    const expected = new Date(Date.UTC(2020, 0, 1, 9, 30)).toLocaleTimeString("fa-IR", {
      hour: "2-digit",
      minute: "2-digit",
    });
    render(
      <LiveDataBanner
        state={{ isLive: true, isError: false, isLoading: false, dataAsOf: naiveUtc }}
      />,
    );
    expect(screen.getByRole("status").textContent).toContain(expected);
  });

  it("shows the connection error when the request failed", () => {
    render(<LiveDataBanner state={{ isLive: false, isError: true, isLoading: false }} />);
    expect(screen.getByRole("status").textContent).toMatch(/ارتباط با سرور برقرار نشد/);
  });

  it("separates an empty successful answer from a failure", () => {
    render(<LiveDataBanner state={{ isLive: false, isError: false, isLoading: false }} />);
    const banner = screen.getByRole("status");
    expect(banner.textContent).toMatch(/داده زنده‌ای از سرور دریافت نشد/);
    expect(banner.textContent).not.toMatch(/ارتباط با سرور برقرار نشد/);
  });

  it("shows an explicit unknown-freshness state when a timestamp exists but neither flag is set", () => {
    render(
      <LiveDataBanner
        state={{
          isLive: true,
          hasData: true,
          dataAsOf: minutesAgo(1),
          isFresh: false,
          isStale: false,
          isError: false,
          isLoading: false,
        }}
      />,
    );
    expect(screen.getByRole("status").textContent).toMatch(/زمان به‌روزرسانی آن از سرور مشخص نیست/);
  });

  it("stays silent when the feed carries no timestamp at all (FE-04)", () => {
    const { container } = render(
      <LiveDataBanner
        state={{
          isLive: true,
          hasData: true,
          isFresh: false,
          isStale: false,
          isError: false,
          isLoading: false,
        }}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("uses explicit isStale even when the data_as_of fallback would look fresh", () => {
    render(
      <LiveDataBanner
        state={{
          isLive: true,
          hasData: true,
          isFresh: false,
          isStale: true,
          isError: false,
          isLoading: false,
          dataAsOf: new Date().toISOString(),
        }}
      />,
    );
    expect(screen.getByRole("status").textContent).toMatch(/قدیمی است/);
  });
});
