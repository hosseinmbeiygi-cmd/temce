"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Shield, Zap, CheckCircle2, AlertTriangle, Clock, Wifi, WifiOff, Volume2, VolumeX, Loader2, Play } from "lucide-react";
import { cn } from "@/lib/cn";
import { usePrecomputeStatus } from "@/hooks/usePrecomputeStatus";
import { usePrecomputeStore } from "@/stores/precomputeStore";
import { getSoundManager, type SoundVariant } from "@/lib/sound/SoundEffectManager";
import type { JobStatus, SymbolGroup } from "@/stores/precomputeStore";

// ── Status config ──────────────────────────────────────────────
const STATUS_CONFIG: Record<JobStatus, { label: string; color: string; bg: string; icon: typeof Shield }> = {
  PENDING: { label: "در انتظار", color: "text-ink-3", bg: "bg-soft", icon: Clock },
  RUNNING: { label: "در حال پردازش", color: "text-primary-600 dark:text-brand-300", bg: "bg-primary-50 dark:bg-brand-900/30", icon: Zap },
  SUCCESS: { label: "تکمیل شد", color: "text-up", bg: "bg-up/10", icon: CheckCircle2 },
  FAILED: { label: "ناموفق", color: "text-down", bg: "bg-down/10", icon: AlertTriangle },
  RETRYING: { label: "تلاش مجدد", color: "text-warn", bg: "bg-warn/10", icon: Loader2 },
  SKIPPED: { label: "رد شد", color: "text-ink-3", bg: "bg-soft", icon: Shield },
  STALE: { label: "قدیمی", color: "text-warn", bg: "bg-warn/10", icon: Clock },
};

const GROUP_LABEL: Record<SymbolGroup, string> = {
  A: "گروه A — نقدشونده‌ها",
  B: "گروه B — متوسط",
  C: "گروه C — کم‌نقد",
};

function formatEta(seconds: number | null | undefined): string {
  if (seconds == null || seconds <= 0) return "—";
  if (seconds < 60) return `${Math.round(seconds)} ثانیه`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// ── Small sub-components ───────────────────────────────────────
function GroupMini({ group, gKey }: { group: { total: number; completed: number; failed: number; status: JobStatus }; gKey: SymbolGroup }) {
  const cfg = STATUS_CONFIG[group.status] ?? STATUS_CONFIG.PENDING;
  const Icon = cfg.icon;
  const pct = group.total > 0 ? Math.round((group.completed / group.total) * 100) : 0;
  return (
    <div className="flex items-center gap-2 rounded-xl border border-line bg-card px-3 py-2">
      <span className={cn("grid size-7 place-items-center rounded-lg", cfg.bg, cfg.color)}>
        <Icon className={cn("size-3.5", group.status === "RUNNING" && "animate-pulse")} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-bold text-ink leading-none">{GROUP_LABEL[gKey]}</p>
        <p className="text-[10px] text-ink-3 tabular-nums">
          {group.completed}/{group.total} · {pct}% {group.failed > 0 && `· ${group.failed} خطا`}
        </p>
      </div>
      <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-bold", cfg.bg, cfg.color)}>{cfg.label}</span>
    </div>
  );
}

// ── Main banner ────────────────────────────────────────────────
export function PrecomputeProgressBanner() {
  const { status, wsConnected, isPolling, error, triggerStart } = usePrecomputeStatus();
  const visibleGroups = usePrecomputeStore((s) => s.visibleGroups ?? []);
  const [soundState, setSoundState] = useState(() => getSoundManager().getState());
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    const mgr = getSoundManager();
    setSoundState(mgr.getState());
    const unsub = mgr.subscribe(setSoundState);
    return unsub;
  }, []);

  const overall: JobStatus = status?.overall_status ?? "PENDING";
  const cfg = STATUS_CONFIG[overall] ?? STATUS_CONFIG.PENDING;
  const Icon = cfg.icon;
  const isRunning = overall === "RUNNING" || overall === "RETRYING";
  const isDone = overall === "SUCCESS";
  const isFailed = overall === "FAILED";
  const pct = status ? Math.round(status.progress_percent ?? 0) : 0;

  const handleStart = async () => {
    setStarting(true);
    try {
      // Unlock sound on the same user gesture (Autoplay Policy)
      getSoundManager().unlock();
      await triggerStart();
    } catch {
      // error is in hook state
    } finally {
      setStarting(false);
    }
  };

  // Hide banner completely when STALE/PENDING and no data yet? Keep minimal when no status
  if (!status && !isPolling && !wsConnected && !error) {
    return (
      <div className="rounded-2xl border border-dashed border-line-strong bg-card px-4 py-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 text-ink-3">
          <Shield className="size-4" />
          <span className="text-[12px] font-bold">داشبورد زرهی آماده است</span>
          <span className="hidden sm:inline text-[11px] text-ink-3">برای محاسبه امتیاز زرهی بازار، پردازش را آغاز کنید</span>
        </div>
        <button
          onClick={handleStart}
          disabled={starting}
          className="inline-flex items-center gap-1.5 rounded-xl bg-primary-700 px-4 py-2 text-[12px] font-bold text-white shadow hover:bg-primary-800 disabled:opacity-60"
        >
          {starting ? <Loader2 className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
          شروع محاسبه
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* ── Main progress bar card ───────────────────────────── */}
      <div className="overflow-hidden rounded-2xl border border-line bg-card shadow-[var(--shadow-card)]">
        {/* top accent bar */}
        <div className="h-1 w-full bg-soft relative overflow-hidden">
          <motion.div
            className={cn("absolute inset-y-0 right-0", isRunning ? "bg-primary-600 dark:bg-brand-400" : isDone ? "bg-up" : isFailed ? "bg-down" : "bg-ink-3")}
            initial={{ width: 0 }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          />
          {isRunning && (
            <motion.div
              className="absolute inset-y-0 w-24 bg-white/30"
              animate={{ x: ["-100%", "500%"] }}
              transition={{ duration: 1.6, repeat: Infinity, ease: "linear" }}
            />
          )}
        </div>

        <div className="px-4 py-3 sm:px-5 sm:py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <span className={cn("grid size-9 place-items-center rounded-xl border", cfg.bg, cfg.color, "border-line")}>
                <Icon className={cn("size-4.5", isRunning && "animate-pulse")} />
              </span>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-[13px] font-black text-ink">داشبورد زرهی</h2>
                  <span className={cn("rounded-full px-2.5 py-0.5 text-[11px] font-bold", cfg.bg, cfg.color)}>{cfg.label}</span>
                  {status?.current_group && (
                    <span className="rounded-full bg-soft px-2 py-0.5 text-[11px] font-medium text-ink-2">
                      {GROUP_LABEL[status.current_group]}
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-[11px] text-ink-3 truncate">
                  {isRunning && status?.current_symbol ? (
                    <>در حال محاسبه <span className="font-mono font-bold text-ink">{status.current_symbol}</span> · ETA {formatEta(status.estimated_remaining_seconds)} · {status.completed_symbols}/{status.total_symbols}</>
                  ) : isDone ? (
                    <>تکمیل شد · {status?.completed_symbols}/{status?.total_symbols} نماد · {status?.failed_symbols ?? 0} خطا</>
                  ) : isFailed ? (
                    <>پردازش متوقف شد · {error ?? "خطای داخلی"}</>
                  ) : (
                    <>آماده برای شروع · {status?.total_symbols ? `${status.total_symbols} نماد` : "—"}</>
                  )}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* WS / Polling indicator */}
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[10px] font-bold",
                  wsConnected ? "border-up/20 bg-up/10 text-up" : "border-warn/20 bg-warn/10 text-warn"
                )}
                title={wsConnected ? "WebSocket متصل — به‌روزرسانی زنده" : "Polling — هر ۳ ثانیه"}
              >
                {wsConnected ? <Wifi className="size-3" /> : <WifiOff className="size-3" />}
                {wsConnected ? "زنده" : "Polling"}
              </span>

              {/* Sound toggle (Autoplay gate aware) */}
              <button
                onClick={() => {
                  const m = getSoundManager();
                  if (!soundState.hasInteracted) m.unlock();
                  m.toggleMute();
                }}
                className={cn(
                  "grid size-8 place-items-center rounded-xl border text-ink-2 hover:bg-soft transition",
                  soundState.muted ? "bg-soft border-line text-ink-3" : "bg-card border-line"
                )}
                aria-label={soundState.muted ? "صدا قطع است" : "صدا فعال است"}
                title={
                  !soundState.hasInteracted
                    ? "برای فعال‌سازی صدا یک بار کلیک کنید (Autoplay Policy)"
                    : soundState.muted
                      ? "روشن کردن صدا"
                      : "قطع صدا"
                }
              >
                {soundState.muted ? <VolumeX className="size-4" /> : <Volume2 className="size-4" />}
              </button>

              {/* Variant selector */}
              <select
                value={soundState.variant}
                onChange={(e) => getSoundManager().setVariant(e.target.value as SoundVariant)}
                className="rounded-xl border border-line bg-card px-2 py-1.5 text-[11px] font-medium text-ink-2"
                title="نوع صدای پایان"
              >
                {(["shot", "finish", "chime"] as SoundVariant[]).map((v) => (
                  <option key={v} value={v}>
                    {getSoundManager().getVariantLabel(v)}
                  </option>
                ))}
              </select>
              <button
                onClick={() => getSoundManager().preview()}
                className="rounded-xl border border-line bg-soft px-2.5 py-1.5 text-[11px] font-bold text-ink-2 hover:bg-card"
              >
                تست صدا
              </button>

              {/* Start / Refresh */}
              {overall === "PENDING" || overall === "FAILED" || overall === "STALE" ? (
                <button
                  onClick={handleStart}
                  disabled={starting}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-primary-700 px-4 py-2 text-[12px] font-bold text-white hover:bg-primary-800 disabled:opacity-60"
                >
                  {starting ? <Loader2 className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
                  {overall === "FAILED" ? "تلاش مجدد" : "شروع"}
                </button>
              ) : null}
            </div>
          </div>

          {/* progress meta */}
          <div className="mt-3 grid grid-cols-3 gap-2 sm:flex sm:flex-wrap sm:gap-3 text-[11px]">
            <span className="rounded-lg bg-soft px-2.5 py-1.5 font-mono tabular-nums text-ink-2">
              پیشرفت <b className="text-ink">{pct}%</b>
            </span>
            <span className="rounded-lg bg-soft px-2.5 py-1.5 font-mono tabular-nums text-ink-2">
              موفق <b className="text-up">{status?.completed_symbols ?? 0}</b>
            </span>
            <span className="rounded-lg bg-soft px-2.5 py-1.5 font-mono tabular-nums text-ink-2">
              خطا <b className={cn((status?.failed_symbols ?? 0) > 0 ? "text-down" : "text-ink")}>{status?.failed_symbols ?? 0}</b>
            </span>
            {status?.estimated_remaining_seconds != null && isRunning && (
              <span className="rounded-lg bg-soft px-2.5 py-1.5 text-ink-2">باقی‌مانده {formatEta(status.estimated_remaining_seconds)}</span>
            )}
            {status?.last_update && (
              <span className="rounded-lg bg-soft px-2.5 py-1.5 text-ink-3 hidden sm:inline">
                آخرین به‌روزرسانی {new Date(status.last_update).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" })}
              </span>
            )}
          </div>

          {error && <p className="mt-2 rounded-xl bg-down/10 px-3 py-2 text-[11px] font-medium text-down">{error}</p>}
        </div>
      </div>

      {/* ── Group mini cards ─────────────────────────────── */}
      {status && (
        <div className="grid gap-2 sm:grid-cols-3">
          {(["A", "B", "C"] as SymbolGroup[]).map((g) => (
            <AnimatePresence key={g}>
              {visibleGroups.includes(g) || status.groups[g].total > 0 ? (
                <motion.div
                  initial={{ opacity: 0, y: 8, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 8 }}
                  transition={{ duration: 0.35, ease: "easeOut" }}
                >
                  <GroupMini group={status.groups[g]} gKey={g} />
                </motion.div>
              ) : null}
            </AnimatePresence>
          ))}
        </div>
      )}

      {/* Interaction hint for Autoplay Policy */}
      <AnimatePresence>
        {!soundState.hasInteracted && soundState.enabled && !soundState.muted && (
          <motion.p
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="rounded-xl border border-warn/20 bg-warn/10 px-3 py-2 text-center text-[11px] font-medium text-warn"
          >
            برای شنیدن صدای پایان محاسبه، یک بار روی صفحه کلیک کنید (محدودیت Autoplay مرورگر)
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}

export default PrecomputeProgressBanner;
