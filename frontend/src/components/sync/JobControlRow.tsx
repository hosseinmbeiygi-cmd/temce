"use client";

import type { ReactNode } from "react";
import { formatCron, formatTime, type SchedulerJobInfo } from "@/lib/job-format";

// ── Job Control Row ────────────────────────────────────────────────────────────────────────────────────────────────────
// Shared control (status pill + cron + next run + run/toggle buttons) for the
// four full-market backfill jobs on the sync-manager page. The `highlight`
// variant renders the ⭐ "دسترسی سریع" banner on the Jobs tab and accepts
// children for live backfill progress.

interface JobControlRowProps {
  icon: string;
  label: string;
  jobName: string;
  job: SchedulerJobInfo | undefined;
  /** true while the job's background backfill is running — disables the run button */
  running: boolean;
  onRun: (jobName: string) => void;
  onToggle: (jobName: string) => void;
  /** human-readable schedule, e.g. "اجرای روزانه ۱۳:۰۰" (used in the enable tooltip) */
  scheduleLabel: string;
  /** extra caption shown only in the highlighted banner variant */
  description?: string;
  /** highlighted "⭐ دسترسی سریع" banner variant (Jobs tab) */
  highlight?: boolean;
  /** extra layout classes (e.g. vertical spacing) */
  className?: string;
  /** extra content rendered under the row (e.g. live backfill progress) */
  children?: ReactNode;
}

export default function JobControlRow({
  icon,
  label,
  jobName,
  job,
  running,
  onRun,
  onToggle,
  scheduleLabel,
  description,
  highlight = false,
  className = "",
  children,
}: JobControlRowProps) {
  const statusPill = (
    <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold ${
      job === undefined
        ? "bg-surface-800 text-surface-500"
        : job.enabled
          ? "bg-accent-emerald/15 text-accent-emerald"
          : "bg-surface-800 text-surface-500"
    }`}>
      {job === undefined ? "..." : job.enabled ? "فعال" : "غیرفعال"}
    </span>
  );

  const cronSpan = (
    <span className="text-[9px] text-surface-500 font-mono">
      {job ? formatCron(job.cron) : "—"}
    </span>
  );

  const nextRunSpan = job?.enabled && job.next_run_time ? (
    <span className="text-[9px] text-surface-500">
      اجرای بعدی: {formatTime(job.next_run_time)}
    </span>
  ) : null;

  const runButton = highlight ? (
    <button
      onClick={() => onRun(jobName)}
      disabled={running}
      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10px] font-bold bg-indigo-600/20 text-indigo-200 border border-indigo-500/40 hover:bg-indigo-600/30 hover:border-indigo-400/60 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
      title="اجرای فوری — بکفیل پس‌زمینه با نمایش پیشرفت زنده">
      <span className="material-icons text-sm">{running ? "hourglass_top" : "play_arrow"}</span>
      {running ? "در حال اجرا..." : "اجرای فوری"}
    </button>
  ) : (
    <button
      onClick={() => onRun(jobName)}
      disabled={running}
      className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[10px] font-bold bg-primary-600/15 text-primary-300 border border-primary-600/25 hover:bg-primary-600/25 disabled:opacity-40 transition-all"
      title="اجرای فوری جاب (بکفیل پس‌زمینه با نمایش پیشرفت)">
      <span className="material-icons text-sm">play_arrow</span>
      اجرا
    </button>
  );

  const toggleButton = (
    <button
      onClick={() => onToggle(jobName)}
      disabled={job === undefined}
      className={`inline-flex items-center gap-1 ${highlight ? "px-3 py-1.5" : "px-2.5 py-1.5"} rounded-lg text-[10px] font-bold border transition-all disabled:opacity-40 ${
        job?.enabled
          ? "bg-accent-rose/10 text-accent-rose border-accent-rose/20 hover:bg-accent-rose/20"
          : "bg-accent-emerald/10 text-accent-emerald border-accent-emerald/20 hover:bg-accent-emerald/20"
      }`}
      title={job?.enabled
        ? "غیرفعال کردن جاب (توقف اجرای روزانه)"
        : `فعال کردن جاب (${scheduleLabel})`}>
      <span className="material-icons text-sm">{job?.enabled ? "pause_circle" : "play_circle"}</span>
      {job === undefined ? "..." : job.enabled ? "غیرفعال" : "فعال"}
    </button>
  );

  if (highlight) {
    return (
      <div className={`relative overflow-hidden rounded-2xl mb-5 border border-indigo-500/40 bg-gradient-to-l from-indigo-600/20 via-primary-600/10 to-accent-amber/15 p-px shadow-[0_0_20px_rgba(99,102,241,0.12)] ${className}`}>
        <div className="rounded-2xl bg-surface-800/90 backdrop-blur px-4 py-3.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-bold text-indigo-300">{icon} {label}</span>
            <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">⭐ دسترسی سریع</span>
            {statusPill}
            {cronSpan}
            {nextRunSpan}
            {description && (
              <span className="text-[9px] text-surface-600 hidden md:inline">{description}</span>
            )}
            <div className="mr-auto flex items-center gap-1.5">
              {runButton}
              {toggleButton}
            </div>
          </div>
          {children}
        </div>
      </div>
    );
  }

  return (
    <div className={`w-full flex flex-wrap items-center gap-2 rounded-xl bg-surface-800/40 border border-surface-700/40 px-3 py-2.5 ${className}`}>
      <span className="text-[11px] font-bold text-surface-300">{icon} {label}</span>
      {statusPill}
      {cronSpan}
      {nextRunSpan}
      <div className="mr-auto flex items-center gap-1.5">
        {runButton}
        {toggleButton}
      </div>
    </div>
  );
}
