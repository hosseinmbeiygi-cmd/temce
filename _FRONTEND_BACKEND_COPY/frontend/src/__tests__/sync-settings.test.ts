import { describe, it, expect } from "vitest";
import {
  recalcStatus,
  applyCustomThresholds,
  DEFAULT_SYNC_SETTINGS,
  loadSyncSettings,
  saveSyncSettings,
  resetSyncSettings,
} from "@/lib/sync-settings";

describe("recalcStatus", () => {
  it("passes through missing/error/unknown statuses unchanged", () => {
    expect(recalcStatus("missing", 500, 10)).toBe("missing");
    expect(recalcStatus("error", 500, 10)).toBe("error");
    expect(recalcStatus("unknown", 500, 10)).toBe("unknown");
  });

  it("keeps the backend status when age is unavailable", () => {
    expect(recalcStatus("ok", null, 10)).toBe("ok");
    expect(recalcStatus("stale", undefined, 10)).toBe("stale");
    expect(recalcStatus("ok", -1, 10)).toBe("ok");
  });

  it("returns ok when age is within the custom max age", () => {
    expect(recalcStatus("ok", 5, 10)).toBe("ok");
    expect(recalcStatus("outdated", 10, 10)).toBe("ok"); // boundary inclusive
  });

  it("returns stale when age is up to 3x the custom max age", () => {
    expect(recalcStatus("ok", 25, 10)).toBe("stale");
    expect(recalcStatus("stale", 30, 10)).toBe("stale"); // boundary inclusive
  });

  it("returns outdated when age exceeds 3x the custom max age", () => {
    expect(recalcStatus("ok", 31, 10)).toBe("outdated");
    expect(recalcStatus("ok", 10_000, 10)).toBe("outdated");
  });

  it("recalculates an already-outdated status back to ok when custom threshold is large", () => {
    // Backend said outdated (age 40min) but user set maxAge=60min → ok
    expect(recalcStatus("outdated", 40, 60)).toBe("ok");
  });
});

describe("applyCustomThresholds", () => {
  const apiMap = {
    symbols: {
      last_fetched: "2026-07-29T10:00:00Z",
      record_count: 100,
      age_minutes: 45,
      status: "ok",
      max_age_minutes: 10,
    },
    codal: {
      last_fetched: null,
      record_count: 0,
      age_minutes: 90,
      status: "ok",
      max_age_minutes: 60,
    },
  };

  it("overrides status and max_age_minutes for sections with custom settings", () => {
    const result = applyCustomThresholds(apiMap, DEFAULT_SYNC_SETTINGS);

    // symbols: age 45 vs custom max 10 → 45 > 30 → outdated
    expect(result.symbols.status).toBe("outdated");
    expect(result.symbols.max_age_minutes).toBe(10);

    // codal: age 90 vs custom max 60 → 90 <= 180 → stale
    expect(result.codal.status).toBe("stale");
    expect(result.codal.max_age_minutes).toBe(60);
  });

  it("keeps other fields intact while overriding", () => {
    const result = applyCustomThresholds(apiMap, DEFAULT_SYNC_SETTINGS);
    expect(result.symbols.record_count).toBe(100);
    expect(result.symbols.last_fetched).toBe("2026-07-29T10:00:00Z");
  });

  it("returns a copy and does not mutate the input", () => {
    const original = JSON.parse(JSON.stringify(apiMap));
    applyCustomThresholds(apiMap, DEFAULT_SYNC_SETTINGS);
    expect(apiMap).toEqual(original);
  });

  it("ignores settings with non-positive maxAgeMinutes", () => {
    const settings = {
      ...DEFAULT_SYNC_SETTINGS,
      symbols: { ...DEFAULT_SYNC_SETTINGS.symbols, maxAgeMinutes: 0 },
    };
    const result = applyCustomThresholds(apiMap, settings);
    // Invalid custom threshold → keep backend status
    expect(result.symbols.status).toBe("ok");
  });
});

describe("loadSyncSettings / saveSyncSettings / resetSyncSettings", () => {
  it("returns defaults when nothing is stored", () => {
    localStorage.removeItem("temce_sync_thresholds");
    const loaded = loadSyncSettings();
    expect(loaded.symbols.maxAgeMinutes).toBe(10);
    expect(Object.keys(loaded).length).toBe(Object.keys(DEFAULT_SYNC_SETTINGS).length);
  });

  it("persists and reloads custom thresholds", () => {
    const custom = {
      ...DEFAULT_SYNC_SETTINGS,
      symbols: { ...DEFAULT_SYNC_SETTINGS.symbols, maxAgeMinutes: 45 },
    };
    saveSyncSettings(custom);
    const loaded = loadSyncSettings();
    expect(loaded.symbols.maxAgeMinutes).toBe(45);
    // Other sections keep defaults
    expect(loaded.codal.maxAgeMinutes).toBe(60);
  });

  it("falls back to defaults when stored JSON is corrupt", () => {
    localStorage.setItem("temce_sync_thresholds", "{not valid json");
    const loaded = loadSyncSettings();
    expect(loaded.symbols.maxAgeMinutes).toBe(10);
  });

  it("resetSyncSettings removes stored thresholds", () => {
    saveSyncSettings({ ...DEFAULT_SYNC_SETTINGS, symbols: { ...DEFAULT_SYNC_SETTINGS.symbols, maxAgeMinutes: 99 } });
    resetSyncSettings();
    const loaded = loadSyncSettings();
    expect(loaded.symbols.maxAgeMinutes).toBe(10);
  });
});
