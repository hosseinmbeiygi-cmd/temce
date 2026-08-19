import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTheme } from "@/hooks/useTheme";

// ------ Tests ---------------------------------------------------------------------------------------------------------------------------------------------
describe("useTheme", () => {
  function resetDom() {
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.classList.remove("dark");
    document.body.classList.remove("dark-theme", "light-theme");
  }

  beforeEach(() => {
    localStorage.clear();
    resetDom();
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
    resetDom();
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

  // ------ no flash on load: respect the theme the <head> script painted ------
  it("adopts the theme already painted on <html> (no flip on load)", () => {
    document.documentElement.setAttribute("data-theme", "light");
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("light");
  });

  // ------ setThemeMode / 'system' mode ---------------------------------------------------------
  it("setThemeMode persists the choice to localStorage", () => {
    const { result } = renderHook(() => useTheme());
    act(() => {
      result.current.setThemeMode("light");
    });
    expect(localStorage.getItem("theme")).toBe("light");
    expect(result.current.theme).toBe("light");
  });

  it("setThemeMode('system') resolves from the system preference", () => {
    const { result } = renderHook(() => useTheme());
    act(() => {
      result.current.setThemeMode("system");
    });
    // matchMedia is mocked to prefer dark
    expect(localStorage.getItem("theme")).toBe("system");
    expect(result.current.theme).toBe("dark");
  });

  // ------ multiple mounted instances stay in sync -----------------------------------------------
  it("keeps multiple mounted instances in sync", () => {
    const a = renderHook(() => useTheme());
    const b = renderHook(() => useTheme());
    expect(a.result.current.theme).toBe("dark");
    expect(b.result.current.theme).toBe("dark");

    act(() => {
      a.result.current.toggleTheme();
    });

    expect(a.result.current.theme).toBe("light");
    expect(b.result.current.theme).toBe("light");
  });

  // ------ cross-tab sync via the storage event --------------------------------------------------
  it("updates when the theme changes in another tab (storage event)", () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("dark");

    act(() => {
      // Simulate another tab writing 'theme' to localStorage.
      localStorage.setItem("theme", "light");
      window.dispatchEvent(new StorageEvent("storage", { key: "theme", newValue: "light" }));
    });

    expect(result.current.theme).toBe("light");
  });
});
