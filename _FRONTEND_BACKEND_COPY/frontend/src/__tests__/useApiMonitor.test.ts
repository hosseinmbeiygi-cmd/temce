import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useApiMonitor } from "@/hooks/useApiMonitor";

// ------ Mock Response Builder ------------------------------------------------------------------------------------------
function mockResponse(overrides: Partial<Response> = {}): Response {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    headers: new Headers(),
    redirected: false,
    type: "basic" as const,
    url: "",
    clone: () => mockResponse(overrides),
    body: null,
    bodyUsed: false,
    arrayBuffer: () => Promise.resolve(new ArrayBuffer(0)),
    blob: () => Promise.resolve(new Blob()),
    bytes: () => Promise.resolve(new Uint8Array(0)),
    formData: () => Promise.resolve(new FormData()),
    json: () => Promise.resolve({}),
    text: () => Promise.resolve(""),
    ...overrides,
  } as Response;
}

// ------ Tests ---------------------------------------------------------------------------------------------------------------------------------------------
describe("useApiMonitor", () => {
  beforeEach(() => {
    // Default: fetch succeeds with ok:true
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ------ Initial State ---------------------------------------------------------------------------------------------------------------
  it("starts with backend='checking', latency=null, lastCheck=null", () => {
    const { result } = renderHook(() => useApiMonitor());
    expect(result.current.health.backend).toBe("checking");
    expect(result.current.health.latency).toBeNull();
    expect(result.current.health.lastCheck).toBeNull();
    expect(result.current.health.endpoints).toEqual({});
  });

  it("starts with isChecking=true after mount (useEffect fires check)", async () => {
    const { result } = renderHook(() => useApiMonitor());
    // The useEffect fires checkBackend immediately on mount,
    // which sets isChecking=true before the first microtask completes.
    await waitFor(() => {
      expect(result.current.isChecking).toBe(true);
    });
    // After the async fetch resolves, isChecking goes back to false
    await waitFor(() => {
      expect(result.current.isChecking).toBe(false);
    });
  });

  // ------ Successful Health Check ---------------------------------------------------------------------------------
  it("sets backend='online' after successful fetch (response.ok=true)", async () => {
    const { result } = renderHook(() => useApiMonitor());

    // The useEffect fires checkBackend on mount.
    // Wait for the async operation to complete.
    await waitFor(() => {
      expect(result.current.health.backend).toBe("online");
    });
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/health",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("records latency after successful check", async () => {
    const { result } = renderHook(() => useApiMonitor());

    await waitFor(() => {
      expect(result.current.health.latency).toEqual(expect.any(Number));
    });
  });

  it("records lastCheck timestamp after successful check", async () => {
    const { result } = renderHook(() => useApiMonitor());

    await waitFor(() => {
      expect(result.current.health.lastCheck).toEqual(expect.any(String));
    });
  });

  // ------ Failed Health Check ---------------------------------------------------------------------------------------------
  it("sets backend='offline' when response.ok=false", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 503 }));

    const { result } = renderHook(() => useApiMonitor());

    await waitFor(() => {
      expect(result.current.health.backend).toBe("offline");
    });
    // latency is still recorded for non-ok responses
    expect(result.current.health.latency).toEqual(expect.any(Number));
  });

  // ------ Network Error ------------------------------------------------------------------------------------------------------
  it("sets backend='offline' when fetch throws (network error)", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    const { result } = renderHook(() => useApiMonitor());

    await waitFor(() => {
      expect(result.current.health.backend).toBe("offline");
    });
    // latency is null when fetch throws
    expect(result.current.health.latency).toBeNull();
  });

  // ------ isChecking flag ------------------------------------------------------------------------------------------------------
  it("sets isChecking=true during fetch and false after", async () => {
    // Use a promise we control to observe the checking state
    let resolveFetch!: (value: Response) => void;
    const fetchPromise = new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    });
    globalThis.fetch = vi.fn().mockReturnValue(fetchPromise);

    const { result } = renderHook(() => useApiMonitor());

    // After mount, useEffect fires checkBackend, which sets isChecking=true
    await waitFor(() => {
      expect(result.current.isChecking).toBe(true);
    });

    // Resolve the fetch
    await act(async () => {
      resolveFetch(mockResponse());
      await fetchPromise;
    });

    await waitFor(() => {
      expect(result.current.isChecking).toBe(false);
    });
  });

  // ------ Concurrent check guard ------------------------------------------------------------------------------------
  it("does not start a new check while one is in progress", async () => {
    let resolveFetch!: (value: Response) => void;
    const fetchPromise = new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    });
    globalThis.fetch = vi.fn().mockReturnValue(fetchPromise);

    const { result } = renderHook(() => useApiMonitor());

    // Wait for checking to start
    await waitFor(() => {
      expect(result.current.isChecking).toBe(true);
    });

    // Try to start another check
    act(() => {
      result.current.checkBackend();
    });

    // fetch should have been called only once (the initial call)
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);

    // Resolve and verify final state
    await act(async () => {
      resolveFetch(mockResponse());
      await fetchPromise;
    });

    await waitFor(() => {
      expect(result.current.health.backend).toBe("online");
    });
  });

  // ------ Manual checkBackend ---------------------------------------------------------------------------------------------
  it("checkBackend can be called manually and updates health", async () => {
    const { result } = renderHook(() => useApiMonitor());

    // Let the initial mount check fully complete (both health + isChecking)
    await waitFor(() => {
      expect(result.current.health.backend).toBe("online");
      expect(result.current.isChecking).toBe(false);
    });

    // Now simulate a failure by replacing fetch with a new mock
    const newFetch = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 500 }));
    globalThis.fetch = newFetch;

    await act(async () => {
      await result.current.checkBackend();
    });

    expect(result.current.health.backend).toBe("offline");
    expect(result.current.health.latency).toEqual(expect.any(Number));
    // The new fetch mock should have been called exactly once (by the manual check)
    expect(newFetch).toHaveBeenCalledTimes(1);
  });

  // ------ Custom baseUrl ------------------------------------------------------------------------------------------------------------
  it("uses custom baseUrl when provided", async () => {
    renderHook(() => useApiMonitor("https://api.example.com"));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "https://api.example.com/health",
        expect.anything(),
      );
    });
  });

  // ------ Interval cleanup on unmount ------------------------------------------------------------------------
  it("clears the interval on unmount", () => {
    vi.useFakeTimers();
    const clearIntervalSpy = vi.spyOn(globalThis, "clearInterval");

    const { unmount } = renderHook(() => useApiMonitor());
    unmount();

    expect(clearIntervalSpy).toHaveBeenCalled();
    clearIntervalSpy.mockRestore();
    vi.useRealTimers();
  });

  it("polls every 30 seconds", async () => {
    vi.useFakeTimers();
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse());

    renderHook(() => useApiMonitor());

    // Initial call on mount (fetch resolves immediately with mock)
    await vi.waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    });

    // Advance 30 seconds
    vi.advanceTimersByTime(30000);

    // Let microtasks resolve
    await vi.waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledTimes(2);
    });

    // Advance another 30 seconds
    vi.advanceTimersByTime(30000);

    await vi.waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledTimes(3);
    });

    vi.useRealTimers();
  });
});
