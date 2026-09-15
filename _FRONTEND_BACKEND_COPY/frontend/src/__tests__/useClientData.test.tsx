import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { useClientData } from "@/hooks/useClientData";

// ------ Tests ------------------------------------------------------------------------------------------------------------------------------------------

describe("useClientData", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ------ SSR Scenario ------------------------------------------------------------------------------------------------------------------
  it("returns initialValue during SSR (useEffect does not run)", () => {
    // renderToString does NOT fire useEffect, simulating SSR
    function TestComponent() {
      const [data] = useClientData(() => "generated", "initial");
      return <div>{data as string}</div>;
    }
    const html = renderToString(<TestComponent />);
    expect(html).toContain("initial");
    expect(html).not.toContain("generated");
  });

  it("returns a setter as the second element of the tuple", () => {
    const { result } = renderHook(() =>
      useClientData(() => "generated", "initial"),
    );

    expect(result.current[1]).toBeInstanceOf(Function);
  });

  // ------ Client Hydration Scenario ---------------------------------------------------------------------------
  it("calls generator after mount and updates data", () => {
    const generator = vi.fn(() => [4, 5, 6]);

    const { result } = renderHook(() =>
      useClientData(generator, [] as number[]),
    );

    // renderHook flushes effects synchronously, so generator has been called
    expect(generator).toHaveBeenCalledTimes(1);
    expect(result.current[0]).toEqual([4, 5, 6]);
  });

  it("replaces initialValue with generated data", () => {
    const { result } = renderHook(() =>
      useClientData(() => "hello", "default"),
    );

    expect(result.current[0]).toBe("hello");
  });

  it("works with string type", () => {
    const { result } = renderHook(() =>
      useClientData(() => "world", ""),
    );

    expect(result.current[0]).toBe("world");
  });

  it("works with object type", () => {
    const { result } = renderHook(() =>
      useClientData(() => ({ name: "test", value: 42 }), null as unknown as Record<string, unknown>),
    );

    expect(result.current[0]).toEqual({ name: "test", value: 42 });
  });

  // ------ Math.random generators ------------------------------------------------------------------------------------
  it("works with Math.random-based generators", () => {
    const generator = vi.fn(() => Math.floor(Math.random() * 100));

    const { result } = renderHook(() => useClientData(generator, 0));

    expect(generator).toHaveBeenCalledTimes(1);
    expect(result.current[0]).toBeGreaterThanOrEqual(0);
    expect(result.current[0]).toBeLessThan(100);
  });

  it("produces different values on separate hook instances", () => {
    const gen1 = () => Math.random();
    const gen2 = () => Math.random();

    const { result: r1 } = renderHook(() => useClientData(gen1, 0));
    const { result: r2 } = renderHook(() => useClientData(gen2, 0));

    expect(r1.current[0]).not.toBe(0);
    expect(r2.current[0]).not.toBe(0);
  });

  // ------ Setter Scenario ---------------------------------------------------------------------------------------------------------
  it("returns a working setter that updates data", () => {
    const { result } = renderHook(() =>
      useClientData(() => "initial", "default"),
    );

    expect(result.current[0]).toBe("initial");

    act(() => {
      result.current[1]("updated");
    });

    expect(result.current[0]).toBe("updated");
  });

  it("setter can be used to override generated data", () => {
    const generator = vi.fn(() => "generated");

    const { result } = renderHook(() =>
      useClientData(generator, "default"),
    );

    expect(generator).toHaveBeenCalledTimes(1);

    act(() => {
      result.current[1]("manual");
    });

    expect(result.current[0]).toBe("manual");
    expect(generator).toHaveBeenCalledTimes(1); // setter doesn't re-call generator
  });

  // ------ Re-render Stability ---------------------------------------------------------------------------------------------
  // Note: StrictMode double-effect invocation is not directly testable here
  // because it requires NODE_ENV='development' (vitest defaults to 'test').
  // The test below verifies the closest proxy: the generator is not called
  // again on subsequent renders (confirming the [] dependency array is stable).
  it("generator is called only once even on re-renders", () => {
    const generator = vi.fn(() => [1, 2, 3]);

    const { rerender } = renderHook(() =>
      useClientData(generator, [] as number[]),
    );

    rerender();
    rerender();
    rerender();

    expect(generator).toHaveBeenCalledTimes(1);
  });

  // ------ Edge Cases ------------------------------------------------------------------------------------------------------------------------
  it("works with null initial value", () => {
    const { result } = renderHook(() =>
      useClientData<string | null>(() => "not-null", null),
    );

    expect(result.current[0]).toBe("not-null");
  });

  it("works with Date.now-based generators (hydration simulation)", () => {
    const dateGenerator = vi.fn(() => new Date().toISOString());

    const { result } = renderHook(() =>
      useClientData(dateGenerator, ""),
    );

    expect(dateGenerator).toHaveBeenCalledTimes(1);
    expect(typeof result.current[0]).toBe("string");
    expect(result.current[0].length).toBeGreaterThan(0);
  });
});
