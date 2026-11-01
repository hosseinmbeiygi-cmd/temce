import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useStaleGuard } from "@/lib/use-stale-guard";

describe("useStaleGuard", () => {
  it("invalidates an older request when a newer one starts", () => {
    const { result } = renderHook(() => useStaleGuard());

    let first!: () => boolean;
    let second!: () => boolean;
    act(() => {
      first = result.current();
      second = result.current();
    });

    expect(first()).toBe(false);
    expect(second()).toBe(true);
  });

  it("invalidates in-flight requests on unmount", () => {
    const { result, unmount } = renderHook(() => useStaleGuard());

    let isCurrent!: () => boolean;
    act(() => {
      isCurrent = result.current();
    });
    expect(isCurrent()).toBe(true);

    unmount();
    expect(isCurrent()).toBe(false);
  });
});
