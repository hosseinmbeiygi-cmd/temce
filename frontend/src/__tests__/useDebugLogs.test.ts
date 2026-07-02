import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDebugLogs } from "@/hooks/useDebugLogs";

// ------ Helpers ---------------------------------------------------------------------------------------------------------------------------------------
function getSavedLogs(): unknown[] {
  try {
    return JSON.parse(localStorage.getItem("debug_logs") || "[]");
  } catch {
    return [];
  }
}

// ------ Tests ---------------------------------------------------------------------------------------------------------------------------------------------
describe("useDebugLogs", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  // ------ Initial State ---------------------------------------------------------------------------------------------------------------
  it("starts with empty logs", () => {
    const { result } = renderHook(() => useDebugLogs());
    expect(result.current.logs).toEqual([]);
  });

  it("starts with isEnabled = true", () => {
    const { result } = renderHook(() => useDebugLogs());
    expect(result.current.isEnabled).toBe(true);
  });

  it("starts with zero stats", () => {
    const { result } = renderHook(() => useDebugLogs());
    expect(result.current.stats).toEqual({
      total: 0,
      loading: 0,
      success: 0,
      error: 0,
      info: 0,
      averageDuration: 0,
    });
  });

  // ------ addLog ------------------------------------------------------------------------------------------------------------------------------------
  it("addLog adds a new log entry", () => {
    const { result } = renderHook(() => useDebugLogs());
    act(() => {
      result.current.addLog("/api/test", "success", { data: 42 });
    });
    expect(result.current.logs).toHaveLength(1);
    expect(result.current.logs[0].endpoint).toBe("/api/test");
    expect(result.current.logs[0].status).toBe("success");
  });

  it("addLog prepends new logs (most recent first)", () => {
    const { result } = renderHook(() => useDebugLogs());
    act(() => {
      result.current.addLog("/first", "info");
    });
    act(() => {
      result.current.addLog("/second", "success");
    });
    expect(result.current.logs[0].endpoint).toBe("/second");
    expect(result.current.logs[1].endpoint).toBe("/first");
  });

  it("addLog assigns a unique id to each log", () => {
    const { result } = renderHook(() => useDebugLogs());
    act(() => {
      result.current.addLog("/a", "info");
      result.current.addLog("/b", "info");
    });
    expect(result.current.logs[0].id).not.toBe(result.current.logs[1].id);
  });

  it("addLog stores method (default GET)", () => {
    const { result } = renderHook(() => useDebugLogs());
    act(() => {
      result.current.addLog("/api", "success");
    });
    expect(result.current.logs[0].method).toBe("GET");
  });

  it("addLog accepts custom method", () => {
    const { result } = renderHook(() => useDebugLogs());
    act(() => {
      result.current.addLog("/api", "success", undefined, undefined, "POST");
    });
    expect(result.current.logs[0].method).toBe("POST");
  });

  it("addLog captures error string", () => {
    const { result } = renderHook(() => useDebugLogs());
    act(() => {
      result.current.addLog("/api", "error", undefined, "Not found");
    });
    expect(result.current.logs[0].error).toBe("Not found");
  });

  // ------ addLog when disabled ------------------------------------------------------------------------------------------
  it("addLog does not add when isEnabled is false", () => {
    const { result } = renderHook(() => useDebugLogs());
    act(() => {
      result.current.toggleEnabled();
    });
    act(() => {
      result.current.addLog("/api", "success");
    });
    expect(result.current.logs).toHaveLength(0);
  });

  // ------ maxLogs ---------------------------------------------------------------------------------------------------------------------------------
  it("respects maxLogs limit, keeping newest", () => {
    const { result } = renderHook(() => useDebugLogs(3));
    act(() => {
      result.current.addLog("/1", "info");
      result.current.addLog("/2", "info");
      result.current.addLog("/3", "info");
      result.current.addLog("/4", "info");
    });
    expect(result.current.logs).toHaveLength(3);
    expect(result.current.logs[0].endpoint).toBe("/4");
    expect(result.current.logs[2].endpoint).toBe("/2");
  });

  // ------ clearLogs ---------------------------------------------------------------------------------------------------------------------------
  it("clearLogs empties the log list", () => {
    const { result } = renderHook(() => useDebugLogs());
    act(() => {
      result.current.addLog("/api", "info");
      result.current.addLog("/api2", "success");
    });
    expect(result.current.logs).toHaveLength(2);
    act(() => {
      result.current.clearLogs();
    });
    expect(result.current.logs).toHaveLength(0);
  });

  // ------ toggleEnabled ---------------------------------------------------------------------------------------------------------------
  it("toggleEnabled flips isEnabled", () => {
    const { result } = renderHook(() => useDebugLogs());
    expect(result.current.isEnabled).toBe(true);
    act(() => {
      result.current.toggleEnabled();
    });
    expect(result.current.isEnabled).toBe(false);
    act(() => {
      result.current.toggleEnabled();
    });
    expect(result.current.isEnabled).toBe(true);
  });

  // ------ stats ---------------------------------------------------------------------------------------------------------------------------------------
  it("stats counts by status correctly", () => {
    const { result } = renderHook(() => useDebugLogs());
    act(() => {
      result.current.addLog("/a", "success");
      result.current.addLog("/b", "error");
      result.current.addLog("/c", "loading");
      result.current.addLog("/d", "info");
      result.current.addLog("/e", "success");
    });
    expect(result.current.stats.total).toBe(5);
    expect(result.current.stats.success).toBe(2);
    expect(result.current.stats.error).toBe(1);
    expect(result.current.stats.loading).toBe(1);
    expect(result.current.stats.info).toBe(1);
  });

  it("stats.averageDuration calculates correctly", () => {
    const { result } = renderHook(() => useDebugLogs());
    act(() => {
      result.current.addLog("/a", "success", { __duration: 100 });
      result.current.addLog("/b", "success", { __duration: 200 });
      result.current.addLog("/c", "error", { __duration: 999 }); // error, not counted
    });
    expect(result.current.stats.averageDuration).toBe(150);
  });

  it("stats.averageDuration is 0 when no successful logs with duration", () => {
    const { result } = renderHook(() => useDebugLogs());
    act(() => {
      result.current.addLog("/a", "info");
      result.current.addLog("/b", "error");
    });
    expect(result.current.stats.averageDuration).toBe(0);
  });

  // ------ getLogsByEndpoint ---------------------------------------------------------------------------------------------------
  it("getLogsByEndpoint filters by endpoint", () => {
    const { result } = renderHook(() => useDebugLogs());
    act(() => {
      result.current.addLog("/api/users", "success");
      result.current.addLog("/api/posts", "success");
      result.current.addLog("/api/users", "error");
    });
    const userLogs = result.current.getLogsByEndpoint("/api/users");
    expect(userLogs).toHaveLength(2);
  });

  // ------ getErrors ---------------------------------------------------------------------------------------------------------------------------
  it("getErrors returns only error logs", () => {
    const { result } = renderHook(() => useDebugLogs());
    act(() => {
      result.current.addLog("/a", "success");
      result.current.addLog("/b", "error");
      result.current.addLog("/c", "error");
      result.current.addLog("/d", "info");
    });
    const errors = result.current.getErrors();
    expect(errors).toHaveLength(2);
    expect(errors.every((l) => l.status === "error")).toBe(true);
  });

  // ------ localStorage Persistence ------------------------------------------------------------------------------
  it("persists logs to localStorage", () => {
    const { result } = renderHook(() => useDebugLogs());
    act(() => {
      result.current.addLog("/api", "success", { key: "val" });
    });
    const saved = getSavedLogs();
    expect(saved).toHaveLength(1);
    expect((saved[0] as Record<string, unknown>).endpoint).toBe("/api");
  });

  it("loads saved logs from localStorage on init", () => {
    // Pre-populate localStorage
    const existingLog = {
      id: "pre-existing",
      endpoint: "/cached",
      status: "info",
      timestamp: "12:00:00",
    };
    localStorage.setItem("debug_logs", JSON.stringify([existingLog]));

    const { result } = renderHook(() => useDebugLogs());
    expect(result.current.logs).toHaveLength(1);
    expect(result.current.logs[0].endpoint).toBe("/cached");
  });

  it("does not crash if localStorage has invalid JSON", () => {
    localStorage.setItem("debug_logs", "not-valid-json{{{");
    const { result } = renderHook(() => useDebugLogs());
    expect(result.current.logs).toEqual([]);
  });

  it("does not crash if localStorage value is not an array", () => {
    localStorage.setItem("debug_logs", JSON.stringify({ not: "array" }));
    const { result } = renderHook(() => useDebugLogs());
    expect(result.current.logs).toEqual([]);
  });

  // ------ SSR Safety ------------------------------------------------------------------------------------------------------------------------
  it("returns empty logs when localStorage is empty", () => {
    const { result } = renderHook(() => useDebugLogs());
    expect(result.current.logs).toEqual([]);
  });

  it("does not call console.warn when localStorage is available", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { result } = renderHook(() => useDebugLogs());
    act(() => {
      result.current.addLog("/api", "success");
    });
    expect(warnSpy).not.toHaveBeenCalled();
    warnSpy.mockRestore();
  });

  // ------ Reference Stability ---------------------------------------------------------------------------------------------
  it("addLog reference is stable across renders", () => {
    const { result, rerender } = renderHook(() => useDebugLogs());
    const firstRef = result.current.addLog;
    rerender();
    expect(result.current.addLog).toBe(firstRef);
  });

  it("clearLogs reference is stable across renders", () => {
    const { result, rerender } = renderHook(() => useDebugLogs());
    const firstRef = result.current.clearLogs;
    rerender();
    expect(result.current.clearLogs).toBe(firstRef);
  });
});
