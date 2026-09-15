import { useState, useEffect } from "react";

/**
 * Hook that initializes data client-side to prevent hydration mismatches.
 *
 * During SSR: returns `initialValue` (safe empty/default state).
 * After hydration: calls `generator` once and updates state with the result.
 *
 * The returned setter can be used to regenerate data (e.g., chart period switching).
 *
 * @example
 * ```tsx
 * // Simple usage (no setter needed)
 * const [cells] = useClientData(() => generateMockHeatmap(), [] as HeatmapCell[]);
 *
 * // With setter for data that can be regenerated
 * const [chartData, setChartData] = useClientData(() => generateIndexHistory(90), []);
 * ```
 */
export function useClientData<T>(
  generator: () => T,
  initialValue: T,
): [T, React.Dispatch<React.SetStateAction<T>>] {
  const [data, setData] = useState<T>(initialValue);

  useEffect(() => {
    // Intentional mount-only client-side initialization to avoid hydration mismatches.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setData(generator());
  }, []);

  return [data, setData];
}
