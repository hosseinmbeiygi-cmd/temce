"use client";

import { useState, useEffect } from "react";
import {
  DEFAULT_SYNC_SETTINGS,
  loadSyncSettings,
  type SyncSettingsMap,
} from "@/lib/sync-settings";

/**
 * SSR-safe wrapper around the localStorage-backed sync-freshness settings.
 *
 * The naive `useState(() => loadSyncSettings())` pattern is a hydration hazard:
 * on the server the initializer returns the defaults (no localStorage), while
 * on the client it returns the user's stored thresholds. If those differ, the
 * server HTML and the client's first render disagree → React discards the whole
 * tree and regenerates it on every load (page visibly blinks off/on).
 *
 * Instead we start from deterministic defaults (identical on server & client)
 * and adopt the stored settings after mount — the same pattern used by the
 * theme hook. A `storage` listener keeps every mounted instance in sync when
 * the settings change in another tab.
 */
export function useSyncSettings(): [
  SyncSettingsMap,
  React.Dispatch<React.SetStateAction<SyncSettingsMap>>,
] {
  // Deterministic SSR-safe initial state — same on server and first client render.
  const [settings, setSettings] = useState<SyncSettingsMap>(() => ({
    ...DEFAULT_SYNC_SETTINGS,
  }));

  // Adopt stored thresholds after hydration (no visual flip: the rendered
  // output only depends on `settings` once async data has arrived anyway).
  useEffect(() => {
    setSettings(loadSyncSettings());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep tabs in sync when the settings change in another tab.
  useEffect(() => {
    const handler = () => setSettings(loadSyncSettings());
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, []);

  return [settings, setSettings];
}
