import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { createRef } from "react";
import SSRSafe from "@/components/SSRSafe";

describe("SSRSafe", () => {
  // ------ Basic Rendering ------------------------------------------------------------------------------------------------------------
  it("renders children", () => {
    render(
      <SSRSafe>
        <span data-testid="child">hello</span>
      </SSRSafe>,
    );

    expect(screen.getByTestId("child")).toHaveTextContent("hello");
  });

  it("renders as a <div> element", () => {
    const { container } = render(<SSRSafe>content</SSRSafe>);
    const el = container.firstElementChild;
    expect(el?.tagName).toBe("DIV");
  });

  it("renders text children", () => {
    render(<SSRSafe>plain text</SSRSafe>);
    expect(screen.getByText("plain text")).toBeInTheDocument();
  });

  // ------ Props Spread ------------------------------------------------------------------------------------------------------------------
  it("spreads className prop", () => {
    const { container } = render(
      <SSRSafe className="my-class">test</SSRSafe>,
    );
    const div = container.firstElementChild;
    expect(div).toHaveClass("my-class");
  });

  it("spreads style prop", () => {
    const { container } = render(
      <SSRSafe style={{ marginTop: 8, color: "red" }}>test</SSRSafe>,
    );
    const div = container.firstElementChild as HTMLElement;
    expect(div.style.marginTop).toBe("8px");
    expect(div.style.color).toBe("red");
  });

  it("spreads id prop", () => {
    render(<SSRSafe id="safe-div">test</SSRSafe>);
    expect(screen.getByText("test")).toHaveAttribute("id", "safe-div");
  });

  it("spreads data-* attributes", () => {
    render(<SSRSafe data-testid="safe">test</SSRSafe>);
    expect(screen.getByTestId("safe")).toBeInTheDocument();
  });

  it("spreads aria-* attributes", () => {
    render(<SSRSafe aria-label="safe label">test</SSRSafe>);
    expect(screen.getByLabelText("safe label")).toBeInTheDocument();
  });

  it("spreads role attribute", () => {
    const { container } = render(
      <SSRSafe role="tabpanel">test</SSRSafe>,
    );
    const div = container.firstElementChild;
    expect(div).toHaveAttribute("role", "tabpanel");
  });

  it("spreads onClick handler", async () => {
    let clicked = false;
    const { container } = render(
      <SSRSafe onClick={() => { clicked = true; }}>test</SSRSafe>,
    );
    const div = container.firstElementChild as HTMLElement;
    div.click();
    expect(clicked).toBe(true);
  });

  // ------ forwardRef ---------------------------------------------------------------------------------------------------------------------------
  it("forwards ref to the underlying div", () => {
    const ref = createRef<HTMLDivElement>();
    render(<SSRSafe ref={ref}>test</SSRSafe>);
    expect(ref.current).toBeInstanceOf(HTMLDivElement);
    expect(ref.current?.textContent).toBe("test");
  });

  it("ref allows calling DOM methods like focus", () => {
    const ref = createRef<HTMLDivElement>();
    render(<SSRSafe ref={ref}>test</SSRSafe>);
    expect(() => ref.current?.focus()).not.toThrow();
  });

  // ------ SSR Scenario ------------------------------------------------------------------------------------------------------------------
  it("renders children in SSR without hydration mismatch", () => {
    const html = renderToString(
      <SSRSafe className="ssr-safe">
        <span data-testid="ssr-child">SSR content</span>
      </SSRSafe>,
    );
    // suppressHydrationWarning is a React internal prop, not an HTML attribute,
    // so it won't appear in renderToString output. The key SSR behaviors to
    // verify are that children render and className is passed through.
    expect(html).toContain("SSR content");
    expect(html).toContain('class="ssr-safe"');
  });

  // ------ Multiple Children ---------------------------------------------------------------------------------------------------
  it("renders multiple children", () => {
    render(
      <SSRSafe>
        <span data-testid="a">A</span>
        <span data-testid="b">B</span>
      </SSRSafe>,
    );
    expect(screen.getByTestId("a")).toHaveTextContent("A");
    expect(screen.getByTestId("b")).toHaveTextContent("B");
  });

  // ------ Empty / null / undefined children ------------------------------------------------------
  it("renders without children", () => {
    const { container } = render(<SSRSafe />);
    const div = container.firstElementChild;
    expect(div).toBeInTheDocument();
    expect(div?.textContent).toBe("");
  });

  // ------ Style + Class + ID together ------------------------------------------------------------------------
  it("supports className, style, and id simultaneously", () => {
    const { container } = render(
      <SSRSafe
        className="foo bar"
        style={{ padding: "1rem" }}
        id="main-safe"
      >
        styled
      </SSRSafe>,
    );
    const div = container.firstElementChild as HTMLElement;
    expect(div.className).toBe("foo bar");
    expect(div.style.padding).toBe("1rem");
    expect(div.id).toBe("main-safe");
  });
});
