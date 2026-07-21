import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import MarketIndices from "@/components/layout/MarketIndices";
import type { MarketIndex } from "@/lib/types";

// ── Mock dependencies ────────────────────────────────────────────

const mockUseQuery = vi.fn();
vi.mock("@tanstack/react-query", () => ({
  useQuery: (...args: unknown[]) => mockUseQuery(...args),
}));

// ── Helpers ──────────────────────────────────────────────────────

function configureUseQuery(data: MarketIndex[] | undefined) {
  mockUseQuery.mockReturnValue({ data });
}

/** Build a MarketIndex with sensible defaults. */
function idx(overrides: Partial<MarketIndex> = {}): MarketIndex {
  return {
    id: overrides.id ?? "",
    name: overrides.name ?? "شاخص",
    value: overrides.value ?? 0,
    isUp: overrides.isUp ?? true,
    changePercent: overrides.changePercent ?? 0,
    icon: overrides.icon ?? "📈",
  };
}

// ── Test suite ───────────────────────────────────────────────────

describe("MarketIndices", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders indices returned from the API", () => {
    const indices: MarketIndex[] = [
      idx({ id: "1", name: "شاخص کل", value: 2145000, changePercent: 1.2, isUp: true }),
      idx({ id: "2", name: "شاخص هم‌وزن", value: 456000, changePercent: 0.8, isUp: true }),
    ];
    configureUseQuery(indices);

    render(<MarketIndices />);

    expect(screen.getAllByTestId("index-card")).toHaveLength(2);
    expect(screen.getByText("شاخص کل")).toBeInTheDocument();
    expect(screen.getByText("شاخص هم‌وزن")).toBeInTheDocument();
  });

  it("renders indices with correct value and change percentage", () => {
    const indices: MarketIndex[] = [
      idx({ id: "1", name: "شاخص کل", value: 2145000, changePercent: 1.23, isUp: true }),
    ];
    configureUseQuery(indices);

    render(<MarketIndices />);

    expect(screen.getByTestId("index-name")).toHaveTextContent("شاخص کل");
    expect(screen.getByTestId("index-value")).toHaveTextContent(/2145000/);
    expect(screen.getByTestId("index-change")).toHaveTextContent(/1\.23%/);
  });

  it("renders fallback mock data when the API fails and fallback is used", () => {
    const fallback: MarketIndex[] = [
      idx({ id: "mock-1", name: "شاخص کل", value: 2145678, changePercent: 1.2, isUp: true, icon: "trending_up" }),
      idx({ id: "mock-2", name: "شاخص هم‌وزن", value: 456789, changePercent: 0.8, isUp: true, icon: "bar_chart" }),
      idx({ id: "mock-3", name: "شاخص صنعت", value: 123456, changePercent: 2.1, isUp: true, icon: "analytics" }),
    ];
    configureUseQuery(fallback);

    render(<MarketIndices />);

    expect(screen.getAllByTestId("index-card")).toHaveLength(3);
  });

  it("does NOT emit duplicate-key warnings when IDs are empty and names collide", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    const withDuplicates: MarketIndex[] = [
      idx({ name: "شاخص آزاد شناور", value: 125000, changePercent: 0.5 }),
      idx({ name: "شاخص آزاد شناور", value: 125100, changePercent: 0.6 }),
      idx({ name: "شاخص کل", value: 2145000, changePercent: 1.2 }),
    ];
    configureUseQuery(withDuplicates);

    render(<MarketIndices />);

    expect(screen.getAllByTestId("index-card")).toHaveLength(3);

    const keyWarnings = warnSpy.mock.calls.filter(
      ([msg]) => typeof msg === "string" && msg.includes("two children with the same key"),
    );
    expect(keyWarnings).toHaveLength(0);

    warnSpy.mockRestore();
  });

  it("does NOT emit duplicate-key warnings with 4 copies of the same index name", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    const worstCase: MarketIndex[] = Array.from({ length: 4 }, (_, i) =>
      idx({
        name: "شاخص آزاد شناور",
        value: 125000 + i * 50,
        changePercent: 0.5 + i * 0.1,
      }),
    );
    configureUseQuery(worstCase);

    render(<MarketIndices />);

    expect(screen.getAllByTestId("index-card")).toHaveLength(4);

    const keyWarnings = warnSpy.mock.calls.filter(
      ([msg]) => typeof msg === "string" && msg.includes("two children with the same key"),
    );
    expect(keyWarnings).toHaveLength(0);

    warnSpy.mockRestore();
  });

  it("does NOT emit duplicate-key warnings when IDs are unique", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    const unique: MarketIndex[] = [
      idx({ id: "a", name: "شاخص کل", value: 2145000 }),
      idx({ id: "b", name: "شاخص هم‌وزن", value: 456000 }),
    ];
    configureUseQuery(unique);

    render(<MarketIndices />);

    expect(screen.getAllByTestId("index-card")).toHaveLength(2);

    const keyWarnings = warnSpy.mock.calls.filter(
      ([msg]) => typeof msg === "string" && msg.includes("two children with the same key"),
    );
    expect(keyWarnings).toHaveLength(0);

    warnSpy.mockRestore();
  });

  it("renders an empty container when indices is undefined", () => {
    configureUseQuery(undefined);

    const { container } = render(<MarketIndices />);
    const div = container.querySelector(".market-indices");
    expect(div).toBeInTheDocument();
    expect(div?.children).toHaveLength(0);
  });

  it("renders an empty container when indices is an empty array", () => {
    configureUseQuery([]);

    const { container } = render(<MarketIndices />);
    const div = container.querySelector(".market-indices");
    expect(div).toBeInTheDocument();
    expect(div?.children).toHaveLength(0);
  });
});
