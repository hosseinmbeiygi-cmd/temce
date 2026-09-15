import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import type { SectorCount } from "@/lib/sectors";

export interface UseSectorCountsResult {
  /** Raw server rows `[{ sector, count }, ...]` (order as returned by the backend). */
  sectors: SectorCount[];
  /** Fast lookup map: `sector -> count`. */
  counts: Record<string, number>;
  /** Sum of all sector counts (total symbols in the catalog). */
  total: number;
  isLoading: boolean;
}

/**
 * Shared hook — fetches the market-sector distribution from
 * `GET /symbols/sectors` in exactly one place.
 *
 * All consumers (SymbolSelector tabs, instruments donut, dashboard donut)
 * share a single React Query cache key (`["symbols-sectors"]`, 5-minute
 * staleTime), so the request is fired once and reused across components.
 *
 * Returns the data in the two shapes the UI needs:
 * - `sectors`: array for chart slices (DonutChart)
 * - `counts`:  map for filter-tab counts
 */
export function useSectorCounts(): UseSectorCountsResult {
  const { data: sectors = [], isLoading } = useQuery<SectorCount[]>({
    queryKey: ["symbols-sectors"],
    queryFn: async () => {
      try {
        const res = await apiGet<{ success: boolean; data: SectorCount[] }>(
          "/symbols/sectors"
        );
        return res?.data ?? [];
      } catch {
        return [];
      }
    },
    staleTime: 5 * 60_000,
  });

  const counts = useMemo(() => {
    const map: Record<string, number> = {};
    for (const row of sectors) map[row.sector] = row.count;
    return map;
  }, [sectors]);

  const total = useMemo(
    () => sectors.reduce((sum, row) => sum + row.count, 0),
    [sectors]
  );

  return { sectors, counts, total, isLoading };
}
