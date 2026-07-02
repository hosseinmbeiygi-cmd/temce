import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTheme } from "@/hooks/useTheme";

// ------ Tests ---------------------------------------------------------------------------------------------------------------------------------------------
describe("useTheme", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
    // jsdom doesn't provide window.matchMedia; mock it for useEffect
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query === "(prefers-color-scheme: dark)",
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  // ------ Initial State ---------------------------------------------------------------------------------------------------------------
  it("starts with default theme = 'dark'", () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("dark");
  });

  // ------ localStorage theme loading ------------------------------------------------------------------------
  it("loads saved theme from localStorage after mount", () => {
    localStorage.setItem("theme", "light");
    const { result } = renderHook(() => useTheme());
    // useEffect runs after mount, so after renderHook flushes effects
    expect(result.current.theme).toBe("light");
  });

  it("persists theme choice to localStorage", () => {
    const { result } = renderHook(() => useTheme());
    act(() => {
      result.current.toggleTheme();
    });
    expect(localStorage.getItem("theme")).toBe("light");
  });

  // ------ system preference fallback ---------------------------------------------------------------------------
  it("falls back to system preference when no saved theme", () => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query === "(prefers-color-scheme: light)",
        media: query,
      })),
    });

    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("light");
  });

  it("uses 'dark' when system prefers dark and no saved theme", () => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query === "(prefers-color-scheme: dark)",
        media: query,
      })),
    });

    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("dark");
  });

  // ------ toggleTheme ---------------------------------------------------------------------------------------------------------------------
  it("toggleTheme switches from dark to light", () => {
    const { result } = renderHook(() => useTheme());
    act(() => {
      result.current.toggleTheme();
    });
    expect(result.current.theme).toBe("light");
  });

  it("toggleTheme switches back from light to dark", () => {
    localStorage.setItem("theme", "light");
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("light");
    act(() => {
      result.current.toggleTheme();
    });
    expect(result.current.theme).toBe("dark");
  });

  // ------ document.documentElement class toggling ------------------------------------
  it("toggleTheme adds 'dark' class to <html> when switching to dark", () => {
    localStorage.setItem("theme", "light");
    const { result } = renderHook(() => useTheme());
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    act(() => {
      result.current.toggleTheme();
    });
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("toggleTheme removes 'dark' class from <html> when switching to light", () => {
    const { result } = renderHook(() => useTheme());
    act(() => {
      result.current.toggleTheme();
    });
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  // ------ toggleTheme creates a new reference each render ------
  it("toggleTheme creates a new reference on re-render (no useCallback)", () => {
    const { result, rerender } = renderHook(() => useTheme());
    const firstRef = result.current.toggleTheme;
    rerender();
    // toggleTheme is a plain function inside the hook (no useCallback),
    // so it gets a new reference on every render
    expect(result.current.toggleTheme).not.toBe(firstRef);
  });
});
