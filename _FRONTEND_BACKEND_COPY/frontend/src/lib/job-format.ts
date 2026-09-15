// ── Scheduler job helpers (shared by sync-manager and JobControlRow) ─────────

// The scheduler job shape returned by GET /jobs/scheduler.
export interface SchedulerJobInfo {
  name: string;
  enabled: boolean;
  cron: string;
  description: string;
  endpoint: string;
  category: string;
  next_run_time: string | null;
}

export function formatCron(cron: string): string {
  const n = Number(cron);
  if (Number.isInteger(n)) {
    if (n < 60) return `هر ${n} ثانیه`;
    if (n < 3600) return `هر ${n / 60} دقیقه`;
    return `هر ${n / 3600} ساعت`;
  }
  const parts = cron.split(" ");
  if (parts.length === 5) {
    if (cron === "0 9 * * *") return "روزانه ۹:۰۰";
    if (cron === "0 13 * * *") return "روزانه ۱۳:۰۰ (بعد از بستن بازار)";
    if (cron === "30 13 * * *") return "روزانه ۱۳:۳۰ (بعد از بستن بازار)";
    if (cron === "0 14 * * *") return "روزانه ۱۴:۰۰ (بعد از بستن بازار)";
    if (cron === "30 14 * * *") return "روزانه ۱۴:۳۰ (بعد از بستن بازار)";
    if (cron === "0 18 * * *") return "روزانه ۱۸:۰۰";
    return cron;
  }
  return cron;
}

export function formatTime(isoStr: string | null): string {
  if (!isoStr) return "—";
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" });
  } catch { return "—"; }
}
