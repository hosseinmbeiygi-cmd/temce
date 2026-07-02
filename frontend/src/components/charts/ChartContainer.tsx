"use client";

import { useEffect, useState, type ReactNode } from "react";

interface ChartContainerProps {
  children: ReactNode;
  height: number;
  className?: string;
}

/**
 * Wraps a Recharts ResponsiveContainer to prevent the
 * "width/height are less than the minimum" warning that occurs
 * during SSR / first paint when the DOM container isn't laid out yet.
 *
 * Usage:
 *   <ChartContainer height={250}>
 *     <ResponsiveContainer width="100%" height="100%">…</ResponsiveContainer>
 *   </ChartContainer>
 */
export default function ChartContainer({
  children,
  height,
  className = "",
}: ChartContainerProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // RequestAnimationFrame guarantees the parent has been laid out and
    // measurements are available.  A simple `setMounted(true)` in the
    // effect is enough for almost all cases — rAF just adds a safety
    // margin for edge cases where layout is deferred (tabs, modals, …).
    const raf = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div
      className={className}
      style={{ width: "100%", height, position: "relative" }}
    >
      {mounted ? (
        children
      ) : (
        /* Placeholder with same dimensions so layout doesn't shift. */
        <div style={{ width: "100%", height: "100%" }} />
      )}
    </div>
  );
}
