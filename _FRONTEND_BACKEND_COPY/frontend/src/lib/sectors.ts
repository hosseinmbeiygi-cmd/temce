/**
 * Shared market-sector (بخش بازار) constants used across the app:
 * badge colours, chart hex colours, and the sector badge helper.
 *
 * Single source of truth — components must import these instead of
 * re-declaring their own sector colour maps.
 */

/** One row of `GET /symbols/sectors`. */
export interface SectorCount {
  sector: string;
  count: number;
}

/** Tailwind badge classes for sector chips (lists/tables). */
export const SECTOR_COLORS: Record<string, string> = {
  "سهام": "bg-blue-500/15 text-blue-400",
  "طلا و سکه": "bg-amber-500/15 text-amber-400",
  "ارز": "bg-emerald-500/15 text-emerald-400",
  "رمزارز": "bg-purple-500/15 text-purple-400",
  "کامودیتی": "bg-rose-500/15 text-rose-400",
  "بورس کالا": "bg-orange-500/15 text-orange-400",
  "صندوق": "bg-cyan-500/15 text-cyan-400",
};

/** Solid hex colours for donut/slice charts. */
export const SECTOR_HEX_COLORS: Record<string, string> = {
  "سهام": "#3b82f6",
  "طلا و سکه": "#f59e0b",
  "ارز": "#10b981",
  "رمزارز": "#a855f7",
  "کامودیتی": "#f43f5e",
  "بورس کالا": "#f97316",
  "صندوق": "#06b6d4",
};

/** Default badge style for an unknown/empty sector. */
export const SECTOR_UNKNOWN_BADGE = "bg-surface-700/50 text-surface-500";

/** Badge class for a sector chip, with a safe fallback for unknown sectors. */
export function sectorBadge(sector: string | undefined): string {
  if (!sector) return SECTOR_UNKNOWN_BADGE;
  return SECTOR_COLORS[sector] || SECTOR_UNKNOWN_BADGE;
}
