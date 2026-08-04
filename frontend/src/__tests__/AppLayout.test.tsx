import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import AppLayout from "@/components/layout/AppLayout";

// ── Mock heavy children so we can test the layout shell in isolation ─────────
vi.mock("@/components/Sidebar", () => ({ default: () => <aside data-testid="sidebar" /> }));
vi.mock("@/components/FloatingAssistant", () => ({ default: () => <div data-testid="floating" /> }));
vi.mock("@/components/SyncStatus", () => ({ default: () => <div data-testid="sync-status" /> }));
vi.mock("@/hooks/useTheme", () => ({ useTheme: () => ({ toggleTheme: vi.fn(), isDark: false }) }));

// The layout lazily imports these; mock them so Suspense resolves immediately.
vi.mock("@/components/layout/TickerTape", () => ({ default: () => <div data-testid="ticker" /> }));
vi.mock("@/components/layout/MarketIndices", () => ({ default: () => <div data-testid="indices" /> }));

describe("AppLayout", () => {
  it("renders children and title/subtitle", () => {
    render(
      <AppLayout title="عنوان تست" subtitle="زیرعنوان تست">
        <p>محتوای صفحه</p>
      </AppLayout>
    );
    expect(screen.getByText("عنوان تست")).toBeInTheDocument();
    expect(screen.getByText("زیرعنوان تست")).toBeInTheDocument();
    expect(screen.getByText("محتوای صفحه")).toBeInTheDocument();
  });

  it("renders the optional header prop when provided", () => {
    render(
      <AppLayout header={<div data-testid="custom-header">هدر سفارشی</div>}>
        <p>محتوا</p>
      </AppLayout>
    );
    expect(screen.getByTestId("custom-header")).toBeInTheDocument();
    expect(screen.getByText("هدر سفارشی")).toBeInTheDocument();
  });

  it("does not render a header when the prop is omitted", () => {
    render(
      <AppLayout>
        <p>محتوا</p>
      </AppLayout>
    );
    expect(screen.queryByTestId("custom-header")).not.toBeInTheDocument();
  });

  it("renders header above the page title", () => {
    render(
      <AppLayout header={<div data-testid="custom-header">هدر</div>} title="عنوان">
        <p>محتوا</p>
      </AppLayout>
    );
    const header = screen.getByTestId("custom-header");
    const title = screen.getByText("عنوان");
    // header appears before title in the DOM (rendered first)
    expect(header.compareDocumentPosition(title) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
