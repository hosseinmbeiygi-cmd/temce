import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import MultiEquityChart from "@/components/charts/MultiEquityChart";
import { cloneElement, type ReactElement } from "react";

// ── Mock ChartContainer to render children synchronously ─────────
vi.mock("@/components/charts/ChartContainer", () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// ── Mock Recharts ResponsiveContainer ────────────────────────────
// ResponsiveContainer normally measures the parent via rAF + ResizeObserver
// and then clones its child with explicit width/height props.
// Our mock does both synchronously.
vi.mock("recharts", async () => {
  const actual = await vi.importActual("recharts");
  const MockResponsiveContainer = ({ children }: { children: ReactElement }) =>
    cloneElement(children, { width: 600, height: 300 });
  return { ...actual, ResponsiveContainer: MockResponsiveContainer };
});

// ── Helpers ──────────────────────────────────────────────────────

interface Series {
  name: string;
  data: { index: number; nav: number }[];
  color: string;
}

function makeSeries(name: string, color: string, points = 10): Series {
  const data = Array.from({ length: points }, (_, i) => ({
    index: i,
    nav: 1000 + i * 10,
  }));
  return { name, data, color };
}

// ── Test suite ───────────────────────────────────────────────────

describe("MultiEquityChart", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders an SVG with multiple series", () => {
    const series = [
      makeSeries("صندوق الف", "#6366f1"),
      makeSeries("صندوق ب", "#22c55e"),
    ];

    const { container } = render(<MultiEquityChart series={series} />);

    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();

    // Each series produces a <path> inside the SVG
    const paths = container.querySelectorAll("svg path");
    expect(paths.length).toBeGreaterThanOrEqual(2);
  });

  it("handles duplicate series names without React key warnings", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    const series = [
      makeSeries("صندوق مشترک", "#6366f1"),
      makeSeries("صندوق مشترک", "#22c55e"),
    ];

    render(<MultiEquityChart series={series} />);

    const keyWarnings = warnSpy.mock.calls.filter(
      ([msg]) => typeof msg === "string" && msg.includes("the same key"),
    );
    expect(keyWarnings).toHaveLength(0);

    warnSpy.mockRestore();
  });

  it("renders with a single series", () => {
    const series = [makeSeries("تنها صندوق", "#6366f1")];

    const { container } = render(<MultiEquityChart series={series} />);

    expect(container.querySelector("svg")).toBeInTheDocument();
    expect(container.querySelectorAll("svg path").length).toBeGreaterThanOrEqual(1);
  });

  it("renders gracefully with empty series array", () => {
    const { container } = render(<MultiEquityChart series={[]} />);

    // Recharts renders an SVG shell even without data
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("accepts the height prop without crashing", () => {
    const series = [makeSeries("هر صندوق", "#6366f1")];

    const { container } = render(
      <MultiEquityChart series={series} height={500} />,
    );

    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("aligns series with different data lengths", () => {
    const short = makeSeries("کوتاه", "#6366f1", 5);
    const long = makeSeries("بلند", "#22c55e", 20);

    const { container } = render(
      <MultiEquityChart series={[short, long]} />,
    );

    expect(container.querySelector("svg")).toBeInTheDocument();
    expect(container.querySelectorAll("svg path").length).toBeGreaterThanOrEqual(2);
  });
});
