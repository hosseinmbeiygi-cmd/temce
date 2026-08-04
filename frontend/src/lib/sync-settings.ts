/**
 * Sync Freshness Settings
 * =========================
 *
 * Persisted in localStorage so each user (browser) can configure
 * the max‑age thresholds that determine "ok" ↔ "stale" ↔ "outdated"
 * for every sync section independently.
 */

// ── Types ────────────────────────────────────────────────────────────────────

export interface SyncSectionSetting {
  /** Human‑friendly label shown in the settings panel (Persian). */
  label: string;
  /** Emoji icon for the section. */
  icon: string;
  /** Max age in minutes before the data is considered stale. */
  maxAgeMinutes: number;
}

/** Keyed by the same section keys the /brsapi/sync-status endpoint returns. */
export type SyncSettingsMap = Record<string, SyncSectionSetting>;

// ── Defaults (match backend `query_service.py` thresholds) ────────────────────

export const DEFAULT_SYNC_SETTINGS: SyncSettingsMap = {
  symbols:     { label: "نمادها (بورس)",       icon: "📊", maxAgeMinutes: 10 },
  commodities: { label: "کامودیتی‌ها",          icon: "🌍", maxAgeMinutes: 10 },
  crypto:      { label: "ارز دیجیتال",           icon: "₿",  maxAgeMinutes: 10 },
  gold_coin:   { label: "طلا و سکه",            icon: "🥇", maxAgeMinutes: 10 },
  currency:    { label: "نرخ ارز",              icon: "💵", maxAgeMinutes: 10 },
  index:       { label: "شاخص‌ها",              icon: "📈", maxAgeMinutes: 10 },
  ime_futures: { label: "آتی کالا",              icon: "🛢️", maxAgeMinutes: 30 },
  ime_options: { label: "اختیار کالا",           icon: "📋", maxAgeMinutes: 30 },
  options:     { label: "آپشن‌ها",               icon: "🎯", maxAgeMinutes: 30 },
  codal:       { label: "کدال",                 icon: "🏢", maxAgeMinutes: 60 },
};

/** Additional sections that the backend doesn't report but we keep for UI consistency. */
export const ALL_SECTION_KEYS = Object.keys(DEFAULT_SYNC_SETTINGS);

// ── localStorage helpers ─────────────────────────────────────────────────────

const STORAGE_KEY = "temce_sync_thresholds";

export function loadSyncSettings(): SyncSettingsMap {
  if (typeof window === "undefined") return { ...DEFAULT_SYNC_SETTINGS };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_SYNC_SETTINGS };
    const parsed = JSON.parse(raw) as Partial<SyncSettingsMap>;
    // Merge with defaults so new sections always have a fallback
    const merged: SyncSettingsMap = { ...DEFAULT_SYNC_SETTINGS };
    for (const key of ALL_SECTION_KEYS) {
      const setting = parsed[key];
      if (setting?.maxAgeMinutes != null && setting.maxAgeMinutes > 0) {
        merged[key] = {
          ...merged[key],
          maxAgeMinutes: setting.maxAgeMinutes,
        };
      }
    }
    return merged;
  } catch {
    return { ...DEFAULT_SYNC_SETTINGS };
  }
}

export function saveSyncSettings(settings: SyncSettingsMap): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // Storage full or unavailable — silently ignore
  }
}

export function resetSyncSettings(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore
  }
}

// ── Status recalculation helpers ──────────────────────────────────────────────

export type RecalcStatus = "ok" | "stale" | "outdated" | "missing" | "unknown" | "error";

/**
 * Recalculate a section's freshness status based on custom thresholds.
 *
 * @param apiStatus - The original status from the backend ("ok", "stale", etc.)
 * @param ageMinutes - The data age in minutes (from API)
 * @param customMaxAge - The user's custom max‑age threshold (minutes)
 * @returns The recalculated status
 */
export function recalcStatus(
  apiStatus: string,
  ageMinutes: number | null | undefined,
  customMaxAge: number,
): RecalcStatus {
  // If data is missing or errored, keep the backend status
  if (apiStatus === "missing" || apiStatus === "error" || apiStatus === "unknown") {
    return apiStatus as RecalcStatus;
  }
  if (ageMinutes == null || ageMinutes < 0) return apiStatus as RecalcStatus;

  if (ageMinutes <= customMaxAge) return "ok";
  if (ageMinutes <= customMaxAge * 3) return "stale";
  return "outdated";
}

/**
 * Apply all user custom thresholds to an API sync-status map.
 * Returns a new map with overridden statuses.
 */
/** Minimal shape of a sync-status entry (subset of the backend response). */
export interface SyncStatusInfo {
  last_fetched?: string | null;
  record_count?: number;
  age_minutes?: number | null;
  status?: string;
  max_age_minutes?: number;
  error?: string;
}

export function applyCustomThresholds<T extends SyncStatusInfo>(
  apiStatusMap: Record<string, T>,
  settings: SyncSettingsMap,
): Record<string, T> {
  const result: Record<string, T> = {};
  for (const [key, info] of Object.entries(apiStatusMap)) {
    const custom = settings[key];
    const overridden: T = { ...info };
    if (custom && custom.maxAgeMinutes > 0) {
      overridden.max_age_minutes = custom.maxAgeMinutes;
      overridden.status = recalcStatus(info.status ?? "unknown", info.age_minutes, custom.maxAgeMinutes) as T["status"];
    }
    result[key] = overridden;
  }
  return result;
}
