"use client";

import { useEffect, useState } from "react";
import {
  getGoldWSManager,
  type GoldHotPayload,
  type GoldWSInfo,
  type WSState,
} from "@/lib/goldApi";

/**
 * C10: بازهٔ پیام `hot` روی سیم. مبنای نمایش کهنگی است — اگر بیش از دو برابر
 * این مقدار پیامی نیاید، اتصال «کهنه» حساب می‌شود (حتی اگر سوکت باز باشد).
 */
export const GOLD_HOT_INTERVAL_MS = 10_000;

/** C10: بازهٔ پیام `snapshot` کامل. */
export const GOLD_SNAPSHOT_INTERVAL_MS = 300_000;

/** F6: وقتی WebSocket قطع است، polling همین بازه جایش را می‌گیرد. */
export const GOLD_FALLBACK_POLL_MS = 10_000;

/** آستانهٔ کهنگی = ۲× بازهٔ hot (F6). */
export const GOLD_STALE_AFTER_MS = GOLD_HOT_INTERVAL_MS * 2;

/** snapshot کامل هر ۵ دقیقه می‌آید؛ ۲× آن (۶۰۰ ثانیه) آستانهٔ کهنگی snapshot است. */
export const GOLD_SNAPSHOT_STALE_AFTER_MS = GOLD_SNAPSHOT_INTERVAL_MS * 2;

export interface GoldWSStatus {
  state: WSState;
  /** سوکت باز است — pages می‌توانند polling را خاموش کنند. */
  connected: boolean;
  /** epoch ms آخرین پیام معتبر. */
  lastMessageAt: number | null;
  /** ثانیه از آخرین پیام؛ null یعنی هرگز پیامی نگرفته‌ایم. */
  ageSeconds: number | null;
  /** اتصال وصل است ولی داده تازه نمی‌آید (> ۲× بازه). */
  stale: boolean;
  lastHot: GoldHotPayload | null;
}

const IDLE: GoldWSStatus = {
  state: "closed",
  connected: false,
  lastMessageAt: null,
  ageSeconds: null,
  stale: false,
  lastHot: null,
};

function toStatus(state: WSState, info: GoldWSInfo, now: number): GoldWSStatus {
  const connected = state === "open";
  // سن از زمان واقعی داده (`as_of`) می‌آید؛ اگر پیام as_of نداشت، زمان رسیدن.
  const freshnessAt = info.lastAsOfAt ?? info.lastMessageAt;
  const ageSeconds =
    freshnessAt === null ? null : Math.max(0, Math.round((now - freshnessAt) / 1000));
  const hotStale =
    info.lastHotAsOfAt === null ? null : now - info.lastHotAsOfAt > GOLD_STALE_AFTER_MS;
  const snapshotStale =
    info.lastSnapshotAsOfAt === null
      ? null
      : now - info.lastSnapshotAsOfAt > GOLD_SNAPSHOT_STALE_AFTER_MS;
  return {
    state,
    connected,
    lastMessageAt: info.lastMessageAt,
    ageSeconds,
    // «کهنه» فقط وقتی معنا دارد که خط وصل است؛ قطع بودن خودش معلوم است.
    // اگر hot می‌آید، آستانهٔ آن (۲۰s) حاکم است؛ در جریان فقط-snapshot، ۶۰۰s.
    stale:
      connected &&
      (hotStale ?? snapshotStale ?? (ageSeconds === null || ageSeconds * 1000 > GOLD_STALE_AFTER_MS)),
    lastHot: info.lastHot,
  };
}

/**
 * وضعیت زندهٔ WebSocket طلا.
 *
 * هر ثانیه فقط سنِ پیام را بازمحاسبه می‌کند (نه درخواست جدید)، تا «آخرین
 * به‌روزرسانی: X ثانیه پیش» در صفحه زنده حرکت کند.
 */
export function useGoldWS(): GoldWSStatus {
  const [status, setStatus] = useState<GoldWSStatus>(IDLE);

  useEffect(() => {
    const manager = getGoldWSManager();
    let info: GoldWSInfo | null = null;
    let state: WSState = "closed";
    const publish = () => setStatus(toStatus(state, info ?? EMPTY_INFO, Date.now()));

    const unsubscribe = manager.subscribe((nextState, _snap, nextInfo) => {
      state = nextState;
      info = nextInfo;
      publish();
    });

    const ticker = window.setInterval(publish, 1000);
    return () => {
      unsubscribe();
      window.clearInterval(ticker);
    };
  }, []);

  return status;
}

const EMPTY_INFO: GoldWSInfo = {
  state: "closed",
  lastMessageAt: null,
  lastSnapshotAt: null,
  lastHotAt: null,
  lastAsOfAt: null,
  lastHotAsOfAt: null,
  lastSnapshotAsOfAt: null,
  lastHot: null,
};

/** «۱۲ ثانیه پیش» / «۳ دقیقه پیش» — برای برچسب تازگی. */
export function formatAge(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return "بدون داده";
  if (seconds < 60) return `${seconds.toLocaleString("fa-IR")} ثانیه پیش`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes.toLocaleString("fa-IR")} دقیقه پیش`;
  return `${Math.floor(minutes / 60).toLocaleString("fa-IR")} ساعت پیش`;
}
