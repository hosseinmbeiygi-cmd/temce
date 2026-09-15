import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { MiniSparklineSignal as MiniSparkline } from "@/components/MiniSparklineSignal";

describe("MiniSparkline", () => {
  // ── Trend Colors ──────────────────────────────────────────────────────────

  it("renders green (#10b981) stroke for upward trend", () => {
    const points = [10, 20, 30, 40, 50]; // last > first
    const { container } = render(<MiniSparkline points={points} />);
    const polyline = container.querySelector("polyline");
    expect(polyline).not.toBeNull();
    expect(polyline!.getAttribute("stroke")).toBe("#10b981");
  });

  it("renders red (#f43f5e) stroke for downward trend", () => {
    const points = [50, 40, 30, 20, 10]; // last < first
    const { container } = render(<MiniSparkline points={points} />);
    const polyline = container.querySelector("polyline");
    expect(polyline!.getAttribute("stroke")).toBe("#f43f5e");
  });

  it("renders amber (#f59e0b) stroke for flat trend", () => {
    const points = [50, 50, 50, 50, 50]; // last === first
    const { container } = render(<MiniSparkline points={points} />);
    const polyline = container.querySelector("polyline");
    expect(polyline!.getAttribute("stroke")).toBe("#f59e0b");
  });

  it("renders amber for single-interval flat (2 identical values)", () => {
    const points = [42, 42];
    const { container } = render(<MiniSparkline points={points} />);
    const polyline = container.querySelector("polyline");
    expect(polyline!.getAttribute("stroke")).toBe("#f59e0b");
  });

  // ── Custom color override ─────────────────────────────────────────────────

  it("uses custom color prop when provided, ignoring trend", () => {
    const points = [10, 20, 30, 40, 50]; // upward trend would be green
    const { container } = render(<MiniSparkline points={points} color="#38BDF8" />);
    const polyline = container.querySelector("polyline");
    expect(polyline!.getAttribute("stroke")).toBe("#38BDF8");
  });

  it("custom color overrides downward trend", () => {
    const points = [50, 40, 30, 20, 10];
    const { container } = render(<MiniSparkline points={points} color="#A78BFA" />);
    const polyline = container.querySelector("polyline");
    expect(polyline!.getAttribute("stroke")).toBe("#A78BFA");
  });

  // ── Empty / edge cases ────────────────────────────────────────────────────

  it("returns null for empty array", () => {
    const { container } = render(<MiniSparkline points={[]} />);
    expect(container.firstElementChild).toBeNull();
  });

  it("returns null for single point", () => {
    const { container } = render(<MiniSparkline points={[42]} />);
    expect(container.firstElementChild).toBeNull();
  });

  // ── SVG structure ─────────────────────────────────────────────────────────

  it("renders an SVG with correct viewBox", () => {
    const points = [10, 30, 50, 20, 40];
    const { container } = render(<MiniSparkline points={points} />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg!.getAttribute("viewBox")).toMatch(/^0 0 \d+ 22$/);
  });

  it("renders both polygon (area fill) and polyline (stroke line)", () => {
    const points = [10, 30, 50, 20, 40];
    const { container } = render(<MiniSparkline points={points} />);
    const polygon = container.querySelector("polygon");
    const polyline = container.querySelector("polyline");
    expect(polygon).not.toBeNull();
    expect(polyline).not.toBeNull();
    expect(polygon!.getAttribute("fill")).toBe("#10b981");
    expect(polygon!.getAttribute("fill-opacity")).toBe("0.12");
  });

  // ── Tooltip / title ───────────────────────────────────────────────────────

  it("shows accuracy tooltip when no label prop", () => {
    const points = [30, 60]; // up trend, last=60
    const { container } = render(<MiniSparkline points={points} />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    // The tooltip is rendered as an SVG-native <title> child element,
    // not as a `title` attribute on the <svg> element.
    expect(container.querySelector("svg title")?.textContent).toContain("60%");
  });

  it("shows custom label tooltip when label prop provided", () => {
    const points = [100, 200, 300];
    const { container } = render(<MiniSparkline points={points} label="سیگنال‌ها" />);
    const title = container.querySelector("svg title");
    expect(title?.textContent).toContain("سیگنال‌ها:");
    expect(title?.textContent).not.toContain("%");
  });

  // ── Width clamping ────────────────────────────────────────────────────────

  it("clamps width to 120px for many points", () => {
    const points = Array.from({ length: 30 }, (_, i) => i * 3);
    const { container } = render(<MiniSparkline points={points} />);
    const svg = container.querySelector("svg");
    expect(svg!.getAttribute("width")).toBe("120");
  });

  it("scales width by points count for small datasets", () => {
    const points = [10, 20, 30, 40, 50]; // 5 points → 5*8=40
    const { container } = render(<MiniSparkline points={points} />);
    const svg = container.querySelector("svg");
    expect(svg!.getAttribute("width")).toBe("40");
  });

  // ── Custom height ─────────────────────────────────────────────────────────

  it("uses custom height prop", () => {
    const points = [10, 30, 50];
    const { container } = render(<MiniSparkline points={points} height={30} />);
    const svg = container.querySelector("svg");
    expect(svg!.getAttribute("height")).toBe("30");
    expect(svg!.getAttribute("viewBox")).toContain("30");
  });
});
